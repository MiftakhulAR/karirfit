# KarirFit_Web — Sistem Rekomendasi Karier (satu paket)

Satu folder berisi seluruh sistem: web (frontend), API (backend), dan pipeline data/model (Colab).

```
KarirFit_Web/
├─ backend/        FastAPI (...) — scoring, LLM, RAG, klaim, evaluasi
├─ frontend/       Next.js (versi ...) — wizard, hasil, riwayat, admin
├─ pipeline-data/  Notebook induk Colab AR + modul src/ (sumber model.json, demand, KB)
└─ docs/           Menjalankan lokal, hosting, mengganti data/model, catatan audit
```

Status: salinan lokal dari repositori `.../backend-karirfit` dan `.../frontend-karirfit` (tanpa `.git`, `.env`, `karirfit.db`, `__pycache__`). Belum di-commit atau di-push.
Panduan lengkap: `docs/PANDUAN.md`.
