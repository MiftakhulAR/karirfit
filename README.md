# KarirFit — Rekomendasi Karier IT Berbasis Kompetensi

KarirFit membantu mahasiswa D4 Teknik Informatika PNJ melihat karier IT yang paling cocok dengan **mata kuliah, keterampilan, pengalaman, dan minat** mereka. Bobot setiap keterampilan diambil dari iklan lowongan kerja di Indonesia. Penjelasan AI mengutip sumber dari basis pengetahuan (RAG).

> ⚠️ **Bukan keputusan final.** Hasil adalah bahan pertimbangan karier, bukan penilaian resmi. Profil O*NET adalah rujukan dari Amerika Serikat dan belum divalidasi untuk Indonesia.

- Web: https://karirfit.vercel.app
- API: https://karirfit.onrender.com (cek status: `/api/health`)

Proyek ini dibuat sebagai skripsi (Bachelor in Computer Science, MSU – PNJ).

---

## Fitur

- **Akun dan persetujuan data.** Daftar dengan e-mail, baca cara data diproses, lalu beri persetujuan. Setiap tab browser punya sesi sendiri.
- **Tes bertahap:**
  - minat (bisa memilih lebih dari satu bidang);
  - keterampilan teknis dan soft skill dengan tingkat kemampuan;
  - teks pengalaman dengan **saran keterampilan** dari kamus, yang hanya ditambahkan setelah kamu konfirmasi;
  - mata kuliah dan nilai, atau mata kuliah sendiri dengan kategori dan SKS (1–8);
  - target karier (bisa dicari di seluruh katalog).
- **Hasil:**
  - skor kecocokan kompetensi dan minat untuk 15 karier IT;
  - filter jenjang pendidikan (SMA/SMK sampai S2) untuk karier rujukan O*NET;
  - setiap kebutuhan ditampilkan dengan persentase iklan yang memintanya, sumber bukti, dan statusnya;
  - keterampilan yang perlu ditingkatkan beserta saran.
- **Penjelasan AI dengan sumber.** Jika tidak ada sumber yang cukup relevan, sistem menyatakan bukti tidak cukup dan tidak mengarang.
- **Asisten karier.** Tanya jawab bebas tentang karier; jawabannya tidak mengubah peringkat.
- **Riwayat** tes sebelumnya dan **penilaian relevansi** (1–5) untuk setiap karier.
- **Panel admin:** ringkasan evaluasi, katalog (karier, keterampilan, minat, mata kuliah), dokumen basis pengetahuan dan indeks ulang, log aktivitas, serta status sistem.
- **Dua bahasa:** Indonesia dan Inggris.

## Cara Pakai

1. Buka https://karirfit.vercel.app, lalu **daftar** atau **masuk**.
2. Tekan **Mulai tes** dan isi setiap langkah. Langkah yang belum lengkap akan diberi tahu.
3. Di ringkasan, periksa kembali isianmu, lalu tekan **Lihat hasil**.
4. Di halaman hasil:
   - pilih jenjang pendidikanmu;
   - buka sebuah karier untuk melihat rincian dan penjelasan AI;
   - beri nilai relevansi.
5. Buka **Riwayat** untuk melihat tes sebelumnya.

**Permintaan pertama bisa memakan waktu sekitar 1 menit.** Server gratis akan "tidur" kalau lama tidak dipakai. Setelah aktif, penjelasan muncul dalam sekitar 4 detik.

## Masalah Umum

| Masalah | Solusi |
|---|---|
| Hasil lama muncul atau ada pesan server sibuk | Tunggu sekitar 1 menit (server sedang bangun), lalu muat ulang halaman. |
| Penjelasan berbunyi "bukti tidak cukup" | Normal untuk karier tanpa dokumen di basis pengetahuan, misalnya karier O*NET atau karier baru dari admin. |
| Ingin keluar di satu tab saja | Sesi berlaku per tab; tab lain tidak ikut keluar. |

## Struktur

```
KarirFit_Web/
├─ backend/        FastAPI: skor, LLM, RAG, cek klaim, katalog, evaluasi (tes: backend/tests)
├─ frontend/       Next.js: tes bertahap, hasil, riwayat, admin
├─ pipeline-data/  Notebook Colab dan modul sumber model.json, demand, basis pengetahuan
└─ docs/           Panduan lokal, hosting, penggantian data, catatan perbaikan
```

## Menjalankan Secara Lokal

Backend (Python 3.12):

```
cd backend
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --reload --port 8000
```

Instal `requirements-rag.txt` untuk mengaktifkan RAG. Butuh lebih dari 512 MB RAM.

Frontend (Node.js):

```
cd frontend
copy .env.local.example .env.local
npm install
npm run dev
```

Buka http://localhost:3000. Daftar variabel lingkungan dan cara hosting ada di [docs/PANDUAN.md](docs/PANDUAN.md). Jangan pernah meng-commit `.env`.

Unit test backend:

```
cd backend
python -m unittest discover -s tests
```
