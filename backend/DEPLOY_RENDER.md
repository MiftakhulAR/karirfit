# Deploy backend FastAPI ke Render (Free, 512 MB, RAG aktif)

Layanan `karirfit` (My project → Production) sudah dibuat dari repo `MiftakhulAR/karirfit`, branch `main`, Root Directory `backend`.

## Pengaturan di Render → karirfit → Settings
| Isian | Nilai |
|---|---|
| Root Directory | `backend` |
| Build Command | `pip install -r requirements.txt && python tools/unduh_e5.py` |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/api/health` |

`tools/unduh_e5.py` mengunduh `intfloat/multilingual-e5-base` dari Hugging Face saat build (±1,1 GB, sekali per build),
lalu mengubahnya menjadi bobot float16 (±0,54 GB) untuk `e5_numpy.py`. Tidak memakai torch, jadi RAM saat jalan ±350 MB.

## Environment (Render → karirfit → Environment)
| Variabel | Isi |
|---|---|
| `GROQ_API_KEY` | kunci dari console.groq.com (diisi sendiri, jangan dibagikan) |
| `GROQ_MODEL` | `openai/gpt-oss-120b` |
| `ALLOWED_ORIGINS` | URL Vercel, mis. `https://karirfit.vercel.app` (pisahkan koma bila lebih dari satu) |
| `DATABASE_URL` | Supabase `karirfit` → Connect → Transaction pooler (URI, port 6543), `[YOUR-PASSWORD]` diganti password database |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | Supabase `karirfit` → Project Settings → API |
| `REQUIRE_AUTH` | `1` |
| `ADMIN_TOKEN` | string acak panjang buatan sendiri |
| `PUBLIC_MODE` | `1` |
| `RAG_TOP_K`, `RAG_THRESHOLD` | **hapus atau kosongkan** (default dari KB v2: 5 dan 0,8401). Nilai lama 0.80 akan menimpa tau skripsi. |
| `EVAL_MODE` | `0` (isi `1` hanya saat uji pengguna) |

## Cek setelah deploy
Buka `https://karirfit.onrender.com/api/health`:
- `"rag": true`, `rag_status.passages` = 970, `rag_status.tau` = 0.8401
- `rag_status.selftest.cosine_vs_colab` ≥ 0.999 (passage pertama di-encode ulang dan dibandingkan dengan embedding Colab).
  Kalau jauh di bawah itu, encoder tidak setara dengan Colab: jangan dipakai untuk uji, laporkan.
- `"storage": "postgres"`, `"auth_required": true`, `"chat": true`

## Batasan paket Free
| Batasan | Dampak | Penanganan |
|---|---|---|
| Tidur setelah 15 menit tanpa trafik, bangun ±1 menit | Pengunjung pertama menunggu | Frontend mencoba ulang otomatis ±2 menit |
| Disk hilang saat restart | Dokumen unggahan admin dan SQLite hilang | Log di Supabase (`DATABASE_URL`); KB v2 ada di repo |
| RAM 512 MB | torch tidak muat | Encoder NumPy (`e5_numpy.py`) |
