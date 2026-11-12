"""Retrieval module (thesis Sections 3.2.4 / 3.5.4) - same retriever as notebook Tahap 11/12.

Knowledge base v2 (Colab Tahap 11, public layer, 970 passages: SKKNI units, KOMDIGI occupation map,
career profiles), copied from the thesis pipeline:
  kb/public_chunks.jsonl    chunk_id, jenis, judul, teks, karier [career names], akses, sumber
  kb/public_emb.npy         passage embeddings ("passage: " + teks), multilingual-e5-base, normalised
  kb/retrieval_config.json  model, prefixes, top_k = 5, tau = 0.8401 (30 development queries)
Optional extra layer from the admin page (rebuild): kb/extra_chunks.jsonl + kb/extra_emb.npy.

Query  "query: {career}. Kompetensi yang dimiliki: {matched}. Kompetensi yang perlu ditingkatkan: {gap[:3]}."
Search candidates = passages tagged with the career; cosine (dot product of normalised vectors),
       top_k after removing duplicate titles, then only passages with score >= tau.
Encoder e5_numpy.E5Numpy (NumPy, float16 weights, no torch) so the backend fits in Render Free (512 MB).
       Without the weights (tools/unduh_e5.py not run) the app runs without retrieval (NFR6).
"""
from __future__ import annotations

import json
import hashlib
from collections import OrderedDict
import os
import sys
import threading
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
KB_DIR = Path(os.getenv("KB_DIR", HERE / "kb"))
CFG = json.loads((KB_DIR / "retrieval_config.json").read_text(encoding="utf-8")) if (KB_DIR / "retrieval_config.json").exists() else {}
EMBED_MODEL = CFG.get("model_embedding", "intfloat/multilingual-e5-base")
TOP_K = int(os.getenv("RAG_TOP_K") or CFG.get("top_k", 5))
TAU = float(os.getenv("RAG_THRESHOLD") or CFG.get("tau", 0.8401))
Q_PREFIX, P_PREFIX = CFG.get("prefix_query", "query: "), CFG.get("prefix_passage", "passage: ")
SKIP_TYPES = set(CFG.get("jenis_tidak_diambil", ["roadmap"]))
PUBLIC_MODE = os.getenv("PUBLIC_MODE", "1") == "1"


def _log(msg):
    print(f"[rag] {msg}", flush=True)


def _career_ids() -> dict[str, str]:
    """career name (as used in the KB) -> career id of model.json"""
    model = json.load(open(HERE / "model.json", encoding="utf-8"))
    return {c["name_en"]: c["id"] for c in model["careers"]} | {c["id"]: c["id"] for c in model["careers"]}


def _load_layer(name: str, ids: dict[str, str]) -> tuple[list[dict], np.ndarray | None]:
    cp, ep = KB_DIR / f"{name}_chunks.jsonl", KB_DIR / f"{name}_emb.npy"
    if not cp.exists():
        return [], None
    chunks = []
    for line in open(cp, encoding="utf-8"):
        if not line.strip():
            continue
        c = json.loads(line)
        chunks.append({"id": c.get("chunk_id") or c["id"], "title": c.get("judul") or c.get("title") or c.get("id"),
                       "text": c.get("teks") or c["text"], "source": c.get("sumber") or c.get("source", ""),
                       "doc_type": c.get("jenis") or c.get("doc_type", ""),
                       "careers": [ids[k] for k in (c.get("karier") or c.get("careers") or []) if k in ids],
                       "access": "public" if (c.get("akses") or c.get("access", "public")) in ("publik", "public") else "private",
                       "retrievable": c.get("retrievable", True)})
    emb = np.load(ep).astype(np.float32) if ep.exists() else None
    if emb is not None and len(emb) != len(chunks):
        raise ValueError(f"{ep.name}: {len(emb)} vectors for {len(chunks)} passages - rebuild the layer")
    return chunks, emb


class Retriever:
    def __init__(self, warmup: bool = True):
        self.ready, self.error, self.encoder, self.selftest = False, None, None, None
        # One bounded cache per retriever instance: rebuilt KBs receive a fresh cache.
        # Hash keys avoid retaining profile-derived query text. Never cache AI replies.
        self._query_cache = OrderedDict()
        self._cache_lock = threading.Lock()
        self._cache_limit = max(0, min(1024, int(os.getenv("RAG_CACHE_SIZE", "128"))))
        self._cache_ttl = max(0, float(os.getenv("RAG_CACHE_TTL", "900")))
        self._cache_hits = self._cache_misses = 0
        self.chunks: list[dict] = []
        self.emb = np.zeros((0, 768), dtype=np.float32)
        try:
            ids = _career_ids()
            for layer in ("public", "extra"):
                ch, em = _load_layer(layer, ids)
                if ch and em is not None:
                    self.chunks += ch
                    self.emb = np.vstack([self.emb, em])
            self.careers = [set(c["careers"]) for c in self.chunks]
            import e5_numpy
            if not self.chunks:
                self.error = "knowledge base files missing in kb/"
            elif not e5_numpy.available():
                self.error = f"encoder weights missing in {e5_numpy.E5_DIR} (run: python tools/unduh_e5.py)"
            else:
                self.encoder = e5_numpy.E5Numpy()
                self.ready = True
                _log(f"{len(self.chunks)} passages, tau={TAU}, top_k={TOP_K}, encoder=e5_numpy")
                if warmup:
                    threading.Thread(target=self._self_test, daemon=True).start()
        except Exception as e:  # never break the app: explanations fall back to system data only
            self.error = f"{type(e).__name__}: {e}"
        if self.error:
            _log("retrieval disabled: " + self.error)

    def _self_test(self):
        """Re-encode the shortest passage and compare with its Colab embedding (should be ~1.0).
        The shortest one keeps the start-up check cheap on Render Free (little CPU)."""
        try:
            t = time.time()
            i = min(range(len(self.chunks)), key=lambda j: len(self.chunks[j]["text"]))
            v = self.encoder.encode([self.chunks[i]["text"]], P_PREFIX)[0]
            self.selftest = {"cosine_vs_colab": round(float(v @ self.emb[i]), 6), "passage": self.chunks[i]["id"],
                             "ms": round((time.time() - t) * 1000)}
            _log(f"self-test {self.selftest}")
        except Exception as e:
            self.selftest = {"error": str(e)[:200]}

    @staticmethod
    def career_query(career_name: str, matched: list[str], gaps: list[str]) -> str:
        return (f"{career_name}. Kompetensi yang dimiliki: {', '.join(matched) or '-'}. "
                f"Kompetensi yang perlu ditingkatkan: {', '.join(gaps[:3]) or '-'}.")

    def _rank(self, q: np.ndarray, idx: list[int], k: int) -> list[dict]:
        if not idx:
            return []
        idx = np.asarray(idx)
        score = self.emb[idx] @ q
        out, seen = [], set()
        for j in np.argsort(-score, kind="stable"):
            c = self.chunks[idx[j]]
            if c["title"] in seen:
                continue
            seen.add(c["title"])
            out.append({k2: c[k2] for k2 in ("id", "title", "text", "source", "doc_type")} | {"score": round(float(score[j]), 4)})
            if len(out) == k:
                break
        return [p for p in out if p["score"] >= TAU]

    def _allowed(self, i: int) -> bool:
        c = self.chunks[i]
        return c["retrievable"] and c["doc_type"] not in SKIP_TYPES and not (PUBLIC_MODE and c["access"] == "private")

    def _query_vector(self, text: str) -> np.ndarray:
        key = hashlib.sha256((EMBED_MODEL + "\0" + Q_PREFIX + text).encode()).digest()
        started = time.perf_counter()
        # Serialize misses so simultaneous identical requests encode only once.
        with self._cache_lock:
            now = time.monotonic()
            cached = self._query_cache.pop(key, None)
            hit = cached is not None and now - cached[0] < self._cache_ttl
            if hit:
                self._query_cache[key] = cached
                self._cache_hits += 1
                vector = cached[1]
            else:
                self._cache_misses += 1
                vector = self.encoder.encode([text], Q_PREFIX)[0]
                if self._cache_limit and self._cache_ttl:
                    self._query_cache[key] = (time.monotonic(), vector)
                    while len(self._query_cache) > self._cache_limit:
                        self._query_cache.popitem(last=False)
        _log(f"query cache_hit={hit} ms={1000 * (time.perf_counter() - started):.1f}")
        return vector

    def search(self, career: str, matched: list[str], gaps: list[str], career_name: str) -> list[dict]:
        """Passages for the explanation of one career (notebook Tahap 12, ambil())."""
        if not self.ready:
            return []
        q = self._query_vector(self.career_query(career_name, matched, gaps))
        return self._rank(q, [i for i, s in enumerate(self.careers) if career in s and self._allowed(i)], TOP_K)

    def search_question(self, question: str, careers: list[str] | None = None, k: int = 4) -> list[dict]:
        """Passages for a free question (assistant); same tau. Not part of the Tahap 12 evaluation."""
        if not self.ready:
            return []
        q = self._query_vector(question)
        want = set(careers or [])
        return self._rank(q, [i for i, s in enumerate(self.careers) if (not want or s & want) and self._allowed(i)], k)

    def status(self) -> dict:
        kinds: dict[str, int] = {}
        for c in self.chunks:
            kinds[c["doc_type"]] = kinds.get(c["doc_type"], 0) + 1
        return {"ready": self.ready, "error": self.error, "passages": len(self.chunks), "by_type": kinds,
                "tau": TAU, "top_k": TOP_K, "embedding_model": EMBED_MODEL, "encoder": "e5_numpy (float16)",
                "kb_version": CFG.get("kb_versi"), "selftest": self.selftest,
                "query_cache": {"entries": len(self._query_cache), "limit": self._cache_limit,
                                "ttl_seconds": self._cache_ttl, "hits": self._cache_hits, "misses": self._cache_misses}}


def build_extra(jsonl_path: str) -> int:
    """Embeds admin-uploaded chunks (build_rag.build_chunks format) into kb/extra_* with the NumPy encoder."""
    import e5_numpy
    chunks = [json.loads(line) for line in open(jsonl_path, encoding="utf-8") if line.strip()]
    enc = e5_numpy.E5Numpy()
    vecs = np.vstack([enc.encode([c["text"]], P_PREFIX) for c in chunks]) if chunks else np.zeros((0, 768), np.float32)
    with open(KB_DIR / "extra_chunks.jsonl", "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    np.save(KB_DIR / "extra_emb.npy", vecs.astype(np.float32))
    return len(chunks)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "build":
        print(build_extra(sys.argv[2]), "extra chunks embedded")
    else:
        print(__doc__)
