# Perbaikan KarirFit — 22 November 2026

## Isi commit ini
1. Kandidat performa encoder (dibuat 12 Nov, belum di-push):
   - `backend/e5_numpy.py`: thread BLAS dibatasi sesuai kuota CPU kontainer (`E5_BLAS_THREADS`, default `auto`) dan metrik encode.
   - `backend/rag.py`: `encoder_runtime` ditampilkan di health.
   - `backend/requirements.txt`: `threadpoolctl`.
   - `backend/tests/test_encoder_cpu.py`
   - `docs/ENCODER_CPU_2026-11-12.md` dan `docs/encoder_validation_2026-11-12.json`: cosine 1.0, retrieval identik.
2. Pemisahan sesi per tab dan per akun (dibuat 12 Nov, belum di-push):
   - Kode: `frontend/lib/tab-auth.ts`, `AppProvider`, `supabase.ts` (filter `user_id`), `Results`, `Wizard`, `ChatWidget`, `EvalPanel`, `riwayat`, `admin`.
   - Login Supabase disimpan per tab (sessionStorage). Jawaban, chat, dan rating disimpan dengan kunci per akun.
3. Perbaikan 22 Nov:
   - `frontend/app/page.tsx` (dasbor) belum ikut perubahan nomor 2. Sebelumnya `listAssessments()` dipanggil tanpa argumen sehingga `tsc` gagal. Sekarang memakai `user.id` dan kunci `submit` per akun.
   - Penanda sitasi rekaan seperti `[FACT-SQL]`:
     - `llm.strip_unknown_citations()` menghapus penanda yang bukan id passage hasil retrieval, hanya dari teks yang ditampilkan (explain dan chat).
     - Teks mentah tetap diperiksa `claims.py` dan disimpan di log beserta `removed_citations`, sehingga metrik evidence support tidak berubah atau menjadi bias.
     - Prompt tidak diubah (tetap v1.2).
   - `backend/tests/test_citations.py`

## Verifikasi (22 Nov)
- `python -m unittest discover -s tests`: 8 lulus.
- `tools/cek_skor.py`: 500 profil identik dengan rumus.
- `npx tsc --noEmit`: lulus.
- `next build`: lulus. Saat pengecekan, font Google diganti stub karena jaringan sandbox; file asli tidak diubah.
- Encoder tidak diuji ulang di sini karena unduhan bobot HF diblokir sandbox. Rujukan validasi tetap `encoder_validation_2026-11-12.json`.

## Setelah deploy
- Cek `/api/health`:
  - `rag_status.selftest.cosine_vs_colab` ≥ 0.999
  - `encoder_runtime.requested_blas_threads` (Render Free biasanya 1)
- Login di tab baru perlu masuk ulang karena sesi per tab; ini perilaku yang disengaja.
- Saat uji pengguna, set `EVAL_MODE=1` di Render.
