# Panduan KarirFit_Web

## 1. Menjalankan lokal
**Backend** (Python 3.10+)
```
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt            # tanpa RAG
# pip install -r requirements-rag.txt      # dengan RAG (embedder besar, >512 MB RAM)
copy .env.example .env                     # isi kunci, lihat bagian 2
uvicorn main:app --reload --port 8000
```
**Frontend** (Node 20+)
```
cd frontend
copy .env.local.example .env.local         # isi URL API dan kunci Supabase
npm install
npm run dev                                # http://localhost:3000
```

## 2. Variabel lingkungan
| Berkas | Variabel penting |
|---|---|
| backend/.env | `GROQ_API_KEY`, `GROQ_MODEL`, `GEMINI_API_KEY` (opsional), `ALLOWED_ORIGINS`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `REQUIRE_AUTH`, `DATABASE_URL`, `ADMIN_TOKEN`, `PUBLIC_MODE`, `RAG_TOP_K`, `RAG_THRESHOLD`, `EVAL_MODE` |
| frontend/.env.local | `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` |

Jangan pernah commit `.env`. Kunci dibuat sendiri; jangan salin dari chat.

## 3. Hosting (sudah berjalan versi Rizqi)
- Frontend: Vercel (`karirfit-ecru.vercel.app`) — lihat `frontend/SETUP_SUPABASE.md`.
- Backend: Render Free (`backend-karirfit.onrender.com`) — lihat `backend/DEPLOY_RENDER.md`. Cold start sekitar 1 menit.
- Database dan auth: Supabase — skema di `frontend/supabase/schema.sql`, panduan di `backend/SETUP_SUPABASE.md`.
- Hosting memakai akun/proyek milik Rizqi. Untuk memindahkan ke akun AR, buat proyek baru dan isi ulang variabel lingkungan di atas.

## 4. Mengganti data dengan milik AR
Data bawaan Rizqi berasal dari templat Colab generik (lowongan global, kamus contoh), **bukan** data demand Indonesia milik AR, sehingga tidak dapat dipakai untuk mendukung klaim skripsi.
1. Jalankan pipeline AR (`pipeline-data/AR_Pipeline_Skripsi_Induk.ipynb`) sampai artefak model.
2. Ganti `backend/model.json` (dan `requirements.csv`) dengan keluaran AR; pastikan format kunci sama (cek `backend/career_model/scoring.py`).
3. Ganti `backend/kb/chunks.jsonl` dan indeks RAG (`build_rag.py`) dengan KB AR (970 chunk publik).
4. Samakan parameter: α=0.5, ambang 10%, bobot nilai (v8.2 menunggu persetujuan pembimbing).
5. Uji ulang `/api/recommend` dan ulangi evaluasi.

## 5. Hal yang belum selesai / perlu keputusan
- Embedder `multilingual-e5-base` terlalu besar untuk Render 512 MB; Patch 15 (embedder NumPy ringan, sekitar 271 MB RAM) belum diterapkan.
- Hasil RAG vs non-RAG tidak berbeda signifikan (dukungan bukti 0.985 vs 0.990, p=0.110; rating manual p=0.672) — laporkan apa adanya.
- Notebook induk belum diuji berjalan utuh.
- v8.2 menunggu persetujuan pembimbing (6 butir).
- Rizqi perlu dicantumkan di ucapan terima kasih.
- Ada entri uji pada Riwayat di web Rizqi.
- Artefak di laptop (`careerai`) dapat lebih baru daripada Drive (25 Okt); bandingkan sebelum memakai.

## 6. Push ke GitHub (nanti, dengan Codex)
Belum ada repositori git di folder ini. Tentukan dulu: satu monorepo, atau dua repositori (backend dan frontend) seperti milik Rizqi.
