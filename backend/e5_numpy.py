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
import math
import time
from pathlib import Path

import numpy as np

E5_DIR = Path(os.getenv("E5_DIR", Path(__file__).resolve().parent / "e5_numpy"))
MAX_LEN = 512


def cpu_quota_threads(root: Path = Path("/sys/fs/cgroup")) -> int | None:
    """Bound native BLAS threads by the container CPU quota, when present.

    A fractional core still needs one worker. Without a quota, preserve the BLAS
    library default; a many-core development laptop should not be forced to one.
    """
    limits = []
    for quota_path, period_path in ((root / "cpu.max", None),
                                    (root / "cpu/cpu.cfs_quota_us", root / "cpu/cpu.cfs_period_us"),
                                    (root / "cpu.cfs_quota_us", root / "cpu.cfs_period_us")):
        try:
            if period_path is None:
                quota, period = quota_path.read_text().split()[:2]
                if quota == "max":
                    continue
            else:
                quota, period = quota_path.read_text(), period_path.read_text()
            quota, period = int(quota), int(period)
            if quota > 0 and period > 0:
                limits.append(max(1, math.ceil(quota / period)))
        except (OSError, ValueError):
            continue
    return min(limits) if limits else None


def blas_threads() -> int | None:
    raw = os.getenv("E5_BLAS_THREADS", "auto").strip().lower()
    if raw == "auto":
        return cpu_quota_threads()
    if raw in ("native", "0"):
        return None
    try:
        value = int(raw)
        if not 1 <= value <= 64:
            raise ValueError
        return value
    except ValueError:
        raise ValueError("E5_BLAS_THREADS must be auto, native, 0, or an integer from 1 to 64") from None


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
        # Native limits are process-wide; configure once during encoder creation,
        # not with overlapping per-request context managers.
        from threadpoolctl import threadpool_limits, threadpool_info
        self.blas_threads = blas_threads()
        self._blas_limit = (threadpool_limits(limits=self.blas_threads, user_api="blas")
                            if self.blas_threads is not None else None)
        self.blas_runtime = [{k: p.get(k) for k in ("internal_api", "num_threads", "version")}
                             for p in threadpool_info() if p.get("user_api") == "blas"]
        self.last_metrics = None
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
        waiting = time.perf_counter()
        with self._lock:                                             # one forward pass at a time (memory)
            started, cpu_started = time.perf_counter(), time.process_time()
            token_counts = []
            for j, t in enumerate(texts):
                ids = self.tok.encode(prefix + t).ids
                token_counts.append(len(ids))
                v = self.forward(ids).mean(0)                         # mean pooling (single sequence, no padding)
                out[j] = v / max(np.linalg.norm(v), 1e-12)
            self.last_metrics = {"queue_ms": round((started - waiting) * 1000, 1),
                                 "compute_ms": round((time.perf_counter() - started) * 1000, 1),
                                 "cpu_ms": round((time.process_time() - cpu_started) * 1000, 1),
                                 "tokens": token_counts}
        return out

    def runtime_status(self) -> dict:
        return {"requested_blas_threads": self.blas_threads, "blas": self.blas_runtime,
                "last_encode": self.last_metrics}


def available(folder: Path | str = E5_DIR) -> bool:
    f = Path(folder)
    return (f / "config.json").exists() and (f / "tokenizer.json").exists() and (f / "embeddings.word_embeddings.weight.npy").exists()
