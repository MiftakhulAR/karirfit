# pipeline-data — Alur pipeline Colab AR

`AR_Pipeline_Skripsi_Induk.ipynb` menggabungkan 19 notebook final secara berurutan (kode sel tidak diubah, keluaran dihapus). **Jangan Run All**; jalankan per tahap. Belum diuji utuh.

| Tahap | Isi | Masukan → Keluaran (folder Drive `Skripsi_RAG`) |
|---|---|---|
| 0 | Penyiapan proyek | struktur folder |
| 1 | Inventaris dokumen | 00_raw → 01_interim |
| 2, 2b, 2c | Ekstraksi teks (3 batch) | 00_raw → 01_interim/tables |
| 3 | Demand industri dari iklan lowongan | 01_interim → 02_processed |
| 4 | Pemetaan kompetensi ke profesi | 02_processed |
| 5, 6 | Knowledge base dan indeks | 02_processed → 03_index |
| 7 | Evaluasi LLM awal | 04_eval |
| 8 | Pemisahan demand (v4) | 02_processed |
| 9 | Triangulasi | 02_processed |
| 10 | Evaluasi ranking hold-out (Hit@3 0.915, MRR 0.798) | 04_eval |
| 11, 11b | KB dan indeks v3; penentuan tau | 03_index |
| 12 | LLM RAG vs non-RAG (v2) | 04_eval |
| 12b | Rating manual tersamar + LLM penilai | 04_eval |
| 13b | Soft skill (O*NET v2) | 02_processed |
| 14 | Pembekuan model, sensitivitas, manifest | 05_artifacts |

Modul `src/` (salin ke `Skripsi_RAG/src/`): `tahap12b_rating.py`, `tahap13_softskill.py`, `tahap14_freeze.py`. Modul `retrieval.py` dan `io_utils.py` dibuat otomatis oleh `%%writefile` di tahap 2 dan 7.

Notebook yang digantikan (tidak disertakan): 08 v1, 12 (Groq), 12 (Gemini), 13.
Kunci API dibaca dari Colab Secrets.
