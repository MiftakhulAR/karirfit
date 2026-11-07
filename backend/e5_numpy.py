"""Lightweight multilingual-e5-base query encoder in NumPy (no torch, no sentence-transformers).

Why: Render Free has 512 MB RAM; torch + the fp32 model needs about 1.5 GB. The knowledge-base passages are
already embedded offline (Colab Tahap 11, kb/public_emb.npy), so at run time only short queries must be
encoded. This module runs the same XLM-RoBERTa forward pass as sentence-transformers
(Transformer -> mean pooling -> L2 normalise) with weights stored as float16 and computed in float32.
All weight files are memory-mapped, so only the rows/tensors that are used are paged into RAM.

Weights: tools/unduh_e5.py downloads intfloat/multilingual-e5-base (model.safetensors, tokenizer.json) from
Hugging Face at build time and writes E5_DIR (default backend/e5_numpy/).
Check: GET /api/health -> rag_selftest compares a re-encoded passage with its stored Colab embedding.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import numpy as np

E5_DIR = Path(os.getenv("E5_DIR", Path(__file__).resolve().parent / "e5_numpy"))
MAX_LEN = 512


def _erf(x: np.ndarray) -> np.ndarray:
    # Abramowitz & Stegun 7.1.26, |error| < 1.5e-7 (exact-erf GELU as in BERT/XLM-R)
    s = np.sign(x)
    a = np.abs(x)
    t = 1.0 / (1.0 + 0.3275911 * a)
    y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * np.exp(-a * a)
    return s * y


def _gelu(x: np.ndarray) -> np.ndarray:
    return 0.5 * x * (1.0 + _erf(x / np.float32(np.sqrt(2.0))))


def _ln(x: np.ndarray, g: np.ndarray, b: np.ndarray, eps: float) -> np.ndarray:
    mu = x.mean(-1, keepdims=True)
    var = ((x - mu) ** 2).mean(-1, keepdims=True)
    return (x - mu) / np.sqrt(var + eps) * g + b


class E5Numpy:
    def __init__(self, folder: Path | str = E5_DIR):
        self.dir = Path(folder)
        cfg = json.loads((self.dir / "config.json").read_text(encoding="utf-8"))
        self.h, self.n_heads, self.n_layers = cfg["hidden_size"], cfg["num_attention_heads"], cfg["num_hidden_layers"]
        self.eps, self.pad = float(cfg["layer_norm_eps"]), int(cfg["pad_token_id"])
        self._w: dict[str, np.ndarray] = {}
        self._lock = threading.Lock()
        from tokenizers import Tokenizer
        self.tok = Tokenizer.from_file(str(self.dir / "tokenizer.json"))
        self.tok.enable_truncation(MAX_LEN)
        self.tok.no_padding()

    def w(self, name: str, f32: bool = True) -> np.ndarray:
        if name not in self._w:
            self._w[name] = np.load(self.dir / f"{name}.npy", mmap_mode="r")
        a = self._w[name]
        return a.astype(np.float32) if f32 else a

    def _lin(self, x, name):
        return x @ self.w(name + ".weight").T + self.w(name + ".bias")

    def forward(self, ids: list[int]) -> np.ndarray:
        """Hidden states [L, H] of one sequence (no padding)."""
        ids = np.asarray(ids, dtype=np.int64)
        pos = np.arange(len(ids)) + self.pad + 1                      # RoBERTa positions start at padding_idx + 1
        x = (self.w("embeddings.word_embeddings.weight", f32=False)[ids].astype(np.float32)
             + self.w("embeddings.position_embeddings.weight", f32=False)[pos].astype(np.float32)
             + self.w("embeddings.token_type_embeddings.weight")[0])
        x = _ln(x, self.w("embeddings.LayerNorm.weight"), self.w("embeddings.LayerNorm.bias"), self.eps)
        L, H, nh = len(ids), self.h, self.n_heads
        hd = H // nh
        for i in range(self.n_layers):
            p = f"encoder.layer.{i}."
            q = self._lin(x, p + "attention.self.query").reshape(L, nh, hd).transpose(1, 0, 2)
            k = self._lin(x, p + "attention.self.key").reshape(L, nh, hd).transpose(1, 0, 2)
            v = self._lin(x, p + "attention.self.value").reshape(L, nh, hd).transpose(1, 0, 2)
            s = q @ k.transpose(0, 2, 1) / np.float32(np.sqrt(hd))
            s = np.exp(s - s.max(-1, keepdims=True))
            s /= s.sum(-1, keepdims=True)
            ctx = (s @ v).transpose(1, 0, 2).reshape(L, H)
            x = _ln(self._lin(ctx, p + "attention.output.dense") + x,
                    self.w(p + "attention.output.LayerNorm.weight"), self.w(p + "attention.output.LayerNorm.bias"), self.eps)
            hmid = _gelu(self._lin(x, p + "intermediate.dense"))
            x = _ln(self._lin(hmid, p + "output.dense") + x,
                    self.w(p + "output.LayerNorm.weight"), self.w(p + "output.LayerNorm.bias"), self.eps)
        return x

    def encode(self, texts: list[str], prefix: str = "query: ") -> np.ndarray:
        out = np.zeros((len(texts), self.h), dtype=np.float32)
        with self._lock:                                             # one forward pass at a time (memory)
            for j, t in enumerate(texts):
                ids = self.tok.encode(prefix + t).ids
                v = self.forward(ids).mean(0)                         # mean pooling (single sequence, no padding)
                out[j] = v / max(np.linalg.norm(v), 1e-12)
        return out


def available(folder: Path | str = E5_DIR) -> bool:
    f = Path(folder)
    return (f / "config.json").exists() and (f / "tokenizer.json").exists() and (f / "embeddings.word_embeddings.weight.npy").exists()
