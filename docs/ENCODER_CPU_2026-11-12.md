# Kandidat optimasi CPU encoder — lokal, belum deploy

## Perubahan
E5_BLAS_THREADS=auto (default) membaca batas CPU cgroup v2/v1. Kuota pecahan CPU memakai satu thread, kuota lainnya dibulatkan ke atas. Tanpa kuota, default native BLAS dipertahankan. E5_BLAS_THREADS=native atau 0 mempertahankan default pustaka; angka 1–64 menjadi override eksplisit. threadpoolctl diperlukan dan tercantum dalam requirements.txt.

Batas BLAS bersifat seluruh proses dan diatur saat encoder dibuat. Semua encode tetap serial melalui lock yang sama. Arsitektur, bobot fp16, operasi forward, pooling, normalisasi, batas token, prefix query/passage, top-k dan tau tidak berubah.

Health rag_status.encoder_runtime memuat batas thread, BLAS aktif, serta waktu antre, komputasi, CPU, dan jumlah token encode terakhir. Log query cache miss memuat metrik encoder. Nilai ini tidak memuat teks pengguna. cpu_ms adalah CPU seluruh proses, sehingga dapat mencakup pekerjaan lain yang berlangsung bersamaan; bukan pengukuran CPU eksklusif satu request. Waktu antre cache belum termasuk queue_ms encoder dan tetap tercakup waktu query/retrieval.

## Validasi lokal
5 tes unit/cache/kuota CPU dan pemeriksaan sintaks lolos. Bobot asli multilingual-e5-base diunduh dari Hugging Face, 198 tensor; bobot tersimpan di backend/e5_numpy dan diabaikan Git.

20 query dibandingkan terhadap implementasi sebelum perubahan: selisih absolut embedding maksimum 0, hasil passage dan skor retrieval identik. 10 passage mencakup beberapa panjang teks (46–333 token), kosinus terhadap Colab sekitar 1,0. Ini uji kesetaraan sampel, bukan pengukuran akurasi ulang seluruh model.

Laptop Windows: median warm 12 thread 0,2677 detik; 1 thread 0,3274 detik. Satu thread lebih lambat pada laptop multicore. Percepatan Render belum terbukti. Default auto dipilih untuk mengikuti kuota container; hasil Windows tidak boleh dipakai sebagai klaim waktu Render. Angka rinci ada di encoder_validation_2026-11-12.json.

## Verifikasi server setelah persetujuan deploy
1. Rekam health sebelum/sesudah, versi commit, konfigurasi thread, RAM, dan selftest.
2. Jalankan beberapa profil sintetis, satu request pada satu waktu; pisahkan waktu bangun server dan encode pertama dari warm cache miss dan cache hit.
3. Bandingkan encoder queue_ms, compute_ms, cpu_ms, retrieval_ms dan generation_ms dengan baseline produksi sebelumnya (~72,9 detik retrieval, ~2,2 detik Groq untuk satu kasus).
4. Pertahankan hasil retrieval dan skor. Bila lambat tetap terjadi, gunakan data CPU/RAM untuk memilih langkah lanjutan. ONNX/kuantisasi memerlukan persetujuan serta benchmark/evaluasi tersendiri.

Sitasi dan klaim AI tidak diubah sesuai arahan pengguna. Tidak ada push/deploy pada tahap lokal ini.
