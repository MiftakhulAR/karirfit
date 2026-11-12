# Perbaikan KarirFit — 12 November 2026

## Data model
Artefak Run All 7 November diunduh dari Skripsi_RAG. Salinan sumber dan SHA-256 ada di pipeline-data/colab_2026-11-07/manifest.json. Bobot v3 (293 pasangan) dan kamus v4 (135 skill) menjadi input backend/tools/build_model.py. Data runtime mencakup 970 passage publik. Sinkronisasi Drive dilakukan secara eksplisit, bukan otomatis pada setiap request.

Index FAISS asli disimpan lokal dan diabaikan Git karena memuat lapisan privat. Hanya passage dan embedding publik dipakai backend. Bobot encoder diunduh saat build Render.

## Petunjuk dan performa
Petunjuk ID/EN dan prompt v1.2 konsisten: soft skill yang masuk kebutuhan karier ikut dihitung. Chat membedakan persentase lowongan dari skala kepentingan O*NET.

Penjelasan AI dibuat melalui tombol pada hasil. Skor dan bukti tersedia terlebih dahulu. Tersedia indikator proses dan tombol coba lagi.

Cache query embedding bersifat lokal dalam proses, kunci SHA-256, LRU maksimum 128 entri dan TTL 900 detik. Variabel opsional RAG_CACHE_SIZE dan RAG_CACHE_TTL; nilai 0 menonaktifkan cache. Penggantian retriever saat rebuild mengosongkan cache. Jawaban AI tidak dicache. Cache membantu profil/karier yang sama, bukan permintaan baru pertama kali.

Respons explain/chat memuat timings (retrieval_ms, generation_ms, total_ms sebelum penyimpanan log). Log [rag] menunjukkan waktu query dan cache hit; log [performance] menunjukkan tahap retrieval dan generasi. Statistik agregat cache tersedia di health.

## Pengujian lanjutan
Jalankan python -m unittest discover -s tests dari backend, lalu npm run typecheck dan npm run build dari frontend.
Setelah deployment, lakukan 10–20 profil sintetis terpisah dari responden; catat p50/p95 cold dan warm, penggunaan RAM, sumber passage dan konsistensi skor. Ulangi penjelasan lalu chat karier yang sama untuk menguji cache. Periksa health, selftest >= 0.999 dan source-specific units pada karier O*NET.

Encoder ONNX/kuantisasi memerlukan benchmark perangkat Render serta evaluasi top-k dan ambang pada beberapa query sebelum diterapkan. Belum diaktifkan pada perubahan ini. Angka waktu produksi baru harus diambil setelah deployment; uji pengguna/SUS dilakukan dengan responden nyata.
