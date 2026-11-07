"""Downloads intfloat/multilingual-e5-base from Hugging Face and converts it for e5_numpy.py.

Run at build time (Render build command):
    pip install -r requirements.txt && python tools/unduh_e5.py
Writes backend/e5_numpy/: config.json, tokenizer.json and one float16 .npy per tensor (~0.56 GB on disk).
The 1.1 GB safetensors file is read tensor by tensor through a memory map (low RAM) and deleted afterwards.
Only numpy and the Python standard library are used. Re-running skips the work when the folder is complete.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path

import numpy as np

REPO = os.getenv("E5_REPO", "intfloat/multilingual-e5-base")
REVISION = os.getenv("E5_REVISION", "main")
BASE = f"https://huggingface.co/{REPO}/resolve/{REVISION}/"
HERE = Path(__file__).resolve().parent.parent
OUT = Path(os.getenv("E5_DIR", HERE / "e5_numpy"))
SAFETENSORS_SIZE = 1112201288          # size listed on the Hub for model.safetensors (integrity check)
DTYPES = {"F32": np.float32, "F16": np.float16, "BF16": None, "I64": np.int64}


def fetch(name: str, dest: Path):
    print(f"[e5] downloading {name} ...", flush=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(BASE + name, timeout=120) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f, length=8 << 20)
    tmp.rename(dest)


def convert(st: Path, out: Path) -> int:
    with open(st, "rb") as f:
        n = int.from_bytes(f.read(8), "little")
        header = json.loads(f.read(n))
    data = np.memmap(st, dtype=np.uint8, mode="r", offset=8 + n)
    count = 0
    for name, meta in header.items():
        if name == "__metadata__":
            continue
        clean = name.split("roberta.", 1)[-1]
        if not clean.startswith(("embeddings.", "encoder.")):        # pooler is not used by sentence-transformers
            continue
        dt = DTYPES[meta["dtype"]]
        a, b = meta["data_offsets"]
        arr = np.frombuffer(data[a:b], dtype=dt).reshape(meta["shape"])
        target = np.float16 if arr.dtype.kind == "f" else arr.dtype
        dst = np.lib.format.open_memmap(out / f"{clean}.npy", mode="w+", dtype=target, shape=arr.shape)
        step = 4096                                              # rows per chunk: keeps build RAM small
        for r in range(0, arr.shape[0] if arr.ndim else 1, step):
            dst[r:r + step] = arr[r:r + step]
        dst.flush()
        del dst, arr
        count += 1
    del data
    return count


def main():
    marker = OUT / "DONE.json"
    if marker.exists():
        print(f"[e5] {OUT} already complete: {marker.read_text()}")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    for f in ("config.json", "tokenizer.json"):
        fetch(f, OUT / f)
    st = OUT / "model.safetensors"
    fetch("model.safetensors", st)
    size = st.stat().st_size
    if size != SAFETENSORS_SIZE and REPO == "intfloat/multilingual-e5-base" and REVISION == "main":
        print(f"[e5] WARNING: model.safetensors has {size} bytes, expected {SAFETENSORS_SIZE} (model updated on the Hub?)")
    h = hashlib.sha256()
    with open(st, "rb") as f:
        for chunk in iter(lambda: f.read(8 << 20), b""):
            h.update(chunk)
    n = convert(st, OUT)
    st.unlink()
    info = {"repo": REPO, "revision": REVISION, "safetensors_sha256": h.hexdigest(), "safetensors_bytes": size, "tensors": n}
    marker.write_text(json.dumps(info))
    print(f"[e5] converted {n} tensors to float16 in {OUT}: {info}")


if __name__ == "__main__":
    sys.exit(main())
