"""Tahap 12b (20 Okt 2026) — rating manual tersamar RAG vs non-RAG + LLM sebagai penilai kedua.

Dipanggil dari notebook 12b_rating_manual.ipynb. Data: 30 pasangan penjelasan Tahap 12 (penjelasan_sampel_manual.csv,
versi A/B acak per pid). Kunci A/B -> kondisi (logs/penjelasan_sampel_manual_kunci.csv) HANYA dibuka di analisis(),
setelah lembar Rating dan Ulangan lengkap.

Desain (disetujui AR, 20 Okt 2026):
  - Penilai manusia tunggal (AR), tersamar. Uji ulang (intra-rater) pada 10 pasangan, diisi >= 3 hari setelah Rating.
  - Penilai kedua: LLM dari keluarga berbeda dengan pembuat penjelasan (pembuat: Groq openai/gpt-oss-120b),
    rubrik dan Fakta Sistem yang sama; preferensi berpasangan dinilai dua kali dengan urutan ditukar (bias posisi).
  - Kriteria K1–K4 skala 1–5, jumlah kesalahan fakta, preferensi A/B/Seri.
  - Uji: Wilcoxon bertanda (dua sisi) per kriteria dan skor total, uji tanda untuk preferensi,
    weighted kappa kuadratik untuk konsistensi (AR vs AR ulang, AR vs LLM).
"""
import datetime
import hashlib
import json
import os
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest, spearmanr, wilcoxon

SEED, N_ULANG = 42, 10
NAMA_SHEET = "rating_manual_rag_v1"
KRITERIA = ["K1", "K2", "K3", "K4"]
NAMA_KRITERIA = {"K1": "Ketepatan fakta", "K2": "Relevansi profil & karier", "K3": "Kualitas saran pengembangan",
                 "K4": "Kejelasan"}
GENERATOR = "openai/gpt-oss-120b"
PILIHAN_JUDGE = {"gemini": ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-flash-latest", "gemini-2.0-flash"],
                 # 21 Okt: Groq jadi default (kuota harian Gemini gratis terlalu kecil, ±13 penilaian/hari).
                 # Urutan: kuota token harian terbesar dulu; semuanya keluarga berbeda dari generator (OpenAI gpt-oss).
                 "groq": ["moonshotai/kimi-k2-instruct-0905", "moonshotai/kimi-k2-instruct", "qwen/qwen3.8-27b", "qwen/qwen3-32b",
                          "llama-3.3-70b-versatile", "meta-llama/llama-4-maverick-17b-128e-instruct"]}
# 21 Okt: daftar model Groq berubah-ubah; bila tidak ada yang cocok, pakai model chat lain dari keluarga berbeda (bukan OpenAI).
KELUARGA_JUDGE = ("moonshotai/", "qwen/", "meta-llama/llama-4", "llama-3", "mistral", "deepseek")
BUKAN_CHAT = ("guard", "whisper", "orpheus", "tts", "safeguard")
TANDA_KUOTA_HARIAN = ("per day", "perday", "tpd", "rpd")

RUBRIK = [
    ["Kolom", "Arti", "5", "4", "3", "2", "1"],
    ["K1", "Ketepatan fakta: isi penjelasan sesuai Fakta Sistem (skill cocok, gap, % iklan, cakupan kurikulum, MK yang mengajarkan skill)",
     "Semua klaim sesuai", "1 ketidaksesuaian kecil (angka sedikit beda, 1 MK kurang tepat)",
     "2–3 ketidaksesuaian kecil ATAU 1 kesalahan penting (skill gap disebut sudah dimiliki, atau sebaliknya)",
     "Beberapa kesalahan penting", "Sebagian besar tidak sesuai atau saling bertentangan"],
    ["K2", "Relevansi: membahas profil dan karier ini secara spesifik, bukan nasihat umum",
     "Seluruhnya spesifik", "Hampir seluruhnya spesifik", "Campuran spesifik dan umum", "Sebagian besar umum", "Umum/tidak relevan"],
    ["K3", "Kualitas saran pengembangan: konkret, sesuai gap, MK PNJ yang disebut memang mengajarkan skill itu; bila tidak ada MK, menyarankan sumber di luar kurikulum",
     "Semua saran konkret dan tepat", "Hampir semua konkret dan tepat", "Sebagian konkret/tepat", "Sedikit yang berguna",
     "Tidak ada saran berguna atau salah arah"],
    ["K4", "Kejelasan: mudah dipahami mahasiswa, terstruktur, tidak bertele-tele, tanpa pengulangan atau kontradiksi",
     "Sangat jelas", "Jelas", "Cukup jelas", "Kurang jelas", "Membingungkan"],
    ["kesalahan", "Jumlah klaim yang BERTENTANGAN dengan Fakta Sistem (bilangan bulat >= 0). Klaim yang tidak bisa dicek dari Fakta (info umum industri) tidak dihitung.", "", "", "", "", ""],
    ["preferensi", "A / B / Seri: penjelasan mana yang lebih Anda pilih untuk diberikan kepada mahasiswa", "", "", "", "", ""],
]
PETUNJUK = [
    "Cara mengisi (penilai: AR).",
    "1. Isi tab Rating untuk 30 pasangan. Baca Fakta Sistem dulu, lalu penjelasan A dan B. Isi K1–K4 (1–5), kesalahan, preferensi, tanggal_isi.",
    "2. Jangan membuka logs/penjelasan_sampel_manual_kunci.csv dan jangan menjalankan analisis sebelum Rating dan Ulangan lengkap.",
    "3. Minimal 3 hari setelah Rating selesai, isi tab Ulangan (10 pasangan, urutan diacak) TANPA melihat tab Rating.",
    "4. Nilai setiap penjelasan berdasarkan isinya, bukan panjangnya. Bila ragu antara dua skor, pilih yang lebih rendah hanya jika ada bukti di Fakta Sistem.",
    "5. Setelah kedua tab lengkap, jalankan ulang notebook 12b (Run all) untuk analisis.",
]
SKOR_KOLOM = [f"{v}_{k}" for v in "AB" for k in KRITERIA + ["kesalahan"]]
KOLOM = (["no", "pid", "karier", "fakta_sistem", "penjelasan_A"] + [f"A_{k}" for k in KRITERIA + ["kesalahan"]]
         + ["penjelasan_B"] + [f"B_{k}" for k in KRITERIA + ["kesalahan"]] + ["preferensi", "tanggal_isi", "catatan"])


def rapikan(teks):
    """Bagian 'nama: a | b' menjadi daftar berbutir agar mudah dibaca di sel."""
    out = []
    for baris in str(teks).split("\n"):
        if ":" in baris:
            kepala, isi = baris.split(":", 1)
            butir = [b.strip() for b in isi.split(" | ") if b.strip()]
            out.append(kepala.strip().upper().replace("_", " ") + "\n" + "\n".join("• " + b for b in butir))
        elif baris.strip():
            out.append(baris.strip())
    return "\n\n".join(out)


# ---------------- penyimpanan lembar: Google Sheets (Colab) atau CSV lokal (uji) ----------------
class LembarGoogle:
    def __init__(self, folder_id, nama=NAMA_SHEET):
        from google.colab import auth
        import gspread
        from google.auth import default
        auth.authenticate_user()
        creds, _ = default()
        self.gc, self.folder_id, self.nama = gspread.authorize(creds), folder_id, nama
        daftar = self.gc.list_spreadsheet_files(title=nama, folder_id=folder_id)
        self.sh = self.gc.open_by_key(daftar[0]["id"]) if daftar else None

    def ada(self):
        return self.sh is not None

    def url(self):
        return f"https://docs.google.com/spreadsheets/d/{self.sh.id}" if self.sh else None

    def buat(self, tabs):
        self.sh = self.gc.create(self.nama, folder_id=self.folder_id)
        pertama = self.sh.sheet1
        for i, (judul, df_or_rows) in enumerate(tabs.items()):
            rows = df_or_rows if isinstance(df_or_rows, list) else [list(df_or_rows.columns)] + df_or_rows.fillna("").values.tolist()
            rows = [[x.item() if hasattr(x, "item") else x for x in r] for r in rows]
            ws = pertama if i == 0 else self.sh.add_worksheet(title=judul, rows=max(len(rows) + 5, 20), cols=max(len(rows[0]), 8))
            if i == 0:
                ws.update_title(judul)
                ws.resize(rows=max(len(rows) + 5, 20), cols=max(len(rows[0]), 8))
            ws.update(range_name="A1", values=rows)
            try:
                self._format(ws, judul, rows)
            except Exception as e:                                # format hanya kenyamanan; data tetap tersimpan
                print(f"Peringatan format tab {judul}: {e}")

    def _format(self, ws, judul, rows):
        sid, n = ws.id, len(rows)
        req = [{"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1}},
                                          "fields": "gridProperties.frozenRowCount"}},
               {"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": n},
                               "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}},
                               "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)"}}]
        if judul in ("Rating", "Ulangan"):
            lebar = {"fakta_sistem": 340, "penjelasan_A": 420, "penjelasan_B": 420, "catatan": 200, "karier": 130}
            for j, k in enumerate(rows[0]):
                req.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": j, "endIndex": j + 1},
                                                          "properties": {"pixelSize": lebar.get(k, 70)}, "fields": "pixelSize"}})

            def valid(kolom, aturan):
                j = rows[0].index(kolom)
                return {"setDataValidation": {"range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": n,
                                                        "startColumnIndex": j, "endColumnIndex": j + 1}, "rule": aturan}}
            skala = {"condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": str(i)} for i in range(1, 6)]},
                     "strict": True, "showCustomUi": True}
            for k in rows[0]:
                if re.fullmatch(r"[AB]_K\d", k):
                    req.append(valid(k, skala))
                elif k.endswith("_kesalahan"):
                    req.append(valid(k, {"condition": {"type": "NUMBER_GREATER_THAN_EQ", "values": [{"userEnteredValue": "0"}]}, "strict": True}))
            req.append(valid("preferensi", {"condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": v} for v in ["A", "B", "Seri"]]},
                                            "strict": True, "showCustomUi": True}))
        else:
            req.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 7},
                                                      "properties": {"pixelSize": 220}, "fields": "pixelSize"}})
        self.sh.batch_update({"requests": req})

    def baca(self, tab):
        nilai = self.sh.worksheet(tab).get_all_values()
        return pd.DataFrame(nilai[1:], columns=nilai[0])


class KuotaHabis(RuntimeError):
    """Kuota API penilai habis; hasil yang sudah ada aman di cache."""


class LembarLokal:
    """Pengganti Google Sheets untuk uji lokal: satu CSV per tab."""
    def __init__(self, folder, nama=NAMA_SHEET):
        self.dir = Path(folder) / nama

    def ada(self):
        return (self.dir / "Rating.csv").exists()

    def url(self):
        return str(self.dir)

    def buat(self, tabs):
        self.dir.mkdir(parents=True, exist_ok=True)
        for judul, isi in tabs.items():
            (pd.DataFrame(isi[1:], columns=isi[0]) if isinstance(isi, list) else isi).to_csv(self.dir / f"{judul}.csv", index=False)

    def baca(self, tab):
        return pd.read_csv(self.dir / f"{tab}.csv", dtype=str, keep_default_na=False)


class Tahap12b:
    def __init__(self, project_dir, folder_id_eval=None, lokal=False):
        P = Path(project_dir)
        self.EVAL, self.LOG, self.OUT = P / "04_eval", P / "logs", P / "02_processed"
        self.folder_id, self.lokal = folder_id_eval, lokal
        self.lembar = None

    # ---------- Langkah 1: data tersamar ----------
    def muat(self):
        self.sampel = pd.read_csv(self.EVAL / "penjelasan_sampel_manual.csv")
        self.profil = pd.read_csv(self.EVAL / "penjelasan_profil_uji.csv", keep_default_na=False).set_index("pid")
        self.bobot = pd.read_csv(self.OUT / "bobot_skill_karier.csv")                     # Tahap 8 (dipakai Tahap 12)
        mk = pd.read_csv(self.OUT / "mk_skill_terverifikasi.csv", keep_default_na=False)
        mk = mk[mk["valid"].astype(str) == "1"]
        self.mk = mk.groupby("skill")["nama_mata_kuliah"].apply(lambda s: sorted(set(s))).to_dict()
        cak = pd.read_csv(self.OUT / "cakupan_kurikulum_karier_v2.csv")
        self.cakupan = dict(zip(cak["karier"], cak["cakupan_%"]))
        self.pids = sorted(self.sampel["pid"].unique())
        assert (self.sampel.groupby("pid")["versi"].apply(lambda s: sorted(s) == ["A", "B"])).all(), "Setiap pid harus punya versi A dan B"
        return {"pasangan": len(self.pids), "penjelasan": len(self.sampel)}

    def fakta(self, pid):
        p, karier = self.profil.loc[pid], self.sampel.loc[self.sampel["pid"] == pid, "karier"].iloc[0]
        sp = lambda s: [x for x in str(s).split(";") if x]
        cocok, gap = sp(p["cocok"]), sp(p["gap"])
        R = self.bobot[self.bobot["karier"] == karier].sort_values("persen", ascending=False)
        persen = "; ".join(f"{s} {v:g}%" for s, v in zip(R["skill"], R["persen"]))
        mk = "\n".join(f"• {s}: {', '.join(self.mk.get(s, [])) or 'tidak ada MK'}" for s in cocok + gap)
        return (f"Karier: {karier}\nSkor fit: {p['fit']}\nCakupan kurikulum karier ini: {self.cakupan.get(karier, '?')}%\n\n"
                f"Skill profil mahasiswa: {', '.join(sp(p['skill_profil']))}\n\n"
                f"COCOK (dimiliki dan dibutuhkan): {', '.join(cocok) or '-'}\n\n"
                f"GAP (dibutuhkan, belum dimiliki): {', '.join(gap) or '-'}\n\n"
                f"% iklan yang meminta skill (karier ini): {persen}\n\n"
                f"MK PNJ yang mengajarkan skill (terverifikasi RPS/kurikulum):\n{mk}")

    def _tabel(self, pids):
        S = self.sampel.set_index(["pid", "versi"])
        rows = []
        for i, pid in enumerate(pids, 1):
            r = {"no": i, "pid": pid, "karier": S.loc[(pid, "A"), "karier"], "fakta_sistem": self.fakta(pid),
                 "penjelasan_A": rapikan(S.loc[(pid, "A"), "penjelasan"]), "penjelasan_B": rapikan(S.loc[(pid, "B"), "penjelasan"])}
            rows.append({k: r.get(k, "") for k in KOLOM})
        return pd.DataFrame(rows, columns=KOLOM)

    # ---------- Langkah 2: lembar rating ----------
    def buat_lembar(self):
        self.lembar = LembarLokal(self.EVAL) if self.lokal else LembarGoogle(self.folder_id)
        if self.lembar.ada():
            print("Lembar sudah ada, TIDAK ditimpa (isian Anda aman):", self.lembar.url())
            return self.status()
        rng = np.random.default_rng(SEED)
        urut = [str(x) for x in rng.permutation(self.pids)]
        ulang = [str(x) for x in rng.permutation(rng.choice(self.pids, size=N_ULANG, replace=False))]
        self.lembar.buat({"Petunjuk": [[t] + [""] * 6 for t in PETUNJUK] + [[""] * 7] + RUBRIK,
                          "Rating": self._tabel(urut), "Ulangan": self._tabel(ulang)})
        print("Lembar dibuat:", self.lembar.url())
        return self.status()

    def _baca(self, tab):
        df = self.lembar.baca(tab)
        for k in SKOR_KOLOM:
            df[k] = pd.to_numeric(df[k].astype(str).str.strip(), errors="coerce")
        df["preferensi"] = df["preferensi"].astype(str).str.strip().map(lambda x: x.upper() if x.upper() in ("A", "B") else
                                                                           "Seri" if x.lower() == "seri" else x)
        return df

    def _lengkap(self, df):
        ok_skor = df[SKOR_KOLOM].notna().all(axis=1)
        ok_rentang = df[[c for c in SKOR_KOLOM if "_K" in c]].isin([1, 2, 3, 4, 5]).all(axis=1)
        ok_pref = df["preferensi"].isin(["A", "B", "Seri"])
        return ok_skor & ok_rentang & ok_pref

    def status(self):
        if self.lembar is None:
            self.lembar = LembarLokal(self.EVAL) if self.lokal else LembarGoogle(self.folder_id)
        st = {}
        for tab in ["Rating", "Ulangan"]:
            df = self._baca(tab)
            kosong = {k: int(df[k].isna().sum()) for k in SKOR_KOLOM if df[k].isna().any()}
            if (~df["preferensi"].isin(["A", "B", "Seri"])).any():
                kosong["preferensi"] = int((~df["preferensi"].isin(["A", "B", "Seri"])).sum())
            st[tab] = {"lengkap": int(self._lengkap(df).sum()), "total": len(df), "kolom_kosong": kosong}
        return st

    # ---------- Langkah 3: LLM sebagai penilai kedua ----------
    def _klien(self, penyedia, ganti_model=None):
        mock = os.environ.get("LLM_MOCK") == "1"
        model_file = self.LOG / "tahap12b_model_judge.json"
        if mock:
            self.penyedia, self.model = "mock", "mock-judge"
            return
        try:
            from google.colab import userdata
            rahasia = userdata.get
        except ImportError:
            rahasia = os.environ.__getitem__
        if penyedia == "gemini":
            from google import genai
            from google.genai import types
            self._types, self.client = types, genai.Client(api_key=rahasia("GEMINI_API_KEY"))
            tersedia = [m.name.split("/")[-1] for m in self.client.models.list() if "generateContent" in (m.supported_actions or [])]
        else:
            from groq import Groq
            self.client = Groq(api_key=rahasia("GROQ_API_KEY"))
            tersedia = [m.id for m in self.client.models.list().data]
        self.penyedia = penyedia
        kunci = json.load(open(model_file)) if model_file.exists() else None
        if ganti_model and kunci and kunci["model"] == ganti_model:
            self.model = ganti_model                              # sudah diganti pada run sebelumnya
            return
        if ganti_model:
            # Ganti model penilai secara eksplisit: hasil model lama TIDAK dipakai (dicatat di file kunci).
            assert ganti_model in tersedia and ganti_model != GENERATOR, f"Model {ganti_model} tidak tersedia. Model di akun: {tersedia}"
            lama = kunci["model"] if kunci else None
            self.model = ganti_model
            json.dump({"penyedia": penyedia, "model": self.model, "generator": GENERATOR, "menggantikan": lama,
                       "hasil_model_lama_dibuang": self._n_cache(lama) if lama else 0,
                       "dipilih": datetime.datetime.now().isoformat(timespec="seconds")}, open(model_file, "w"), indent=2)
            print("Model penilai diganti dan dikunci:", penyedia, self.model, "| menggantikan:", lama)
            return
        if kunci and kunci["penyedia"] == penyedia and self._n_cache(kunci["model"]) > 0:
            # Sudah ada hasil penilaian: model tidak diganti agar semua penjelasan dinilai model yang sama.
            self.model = kunci["model"]
            return
        # Penyedia berganti (mis. gemini -> groq): hasil model lama tidak dipakai; semua dinilai ulang oleh model baru.
        lama = kunci["model"] if kunci and kunci["penyedia"] != penyedia else None
        # Belum ada hasil: pilih model pertama yang tersedia DAN merespons (model sibuk/503 dilewati), lalu kunci.
        pilih = [m for m in PILIHAN_JUDGE[penyedia] if m in tersedia and m != GENERATOR]
        if not pilih and penyedia == "groq":
            pilih = sorted(m for m in tersedia if m.startswith(KELUARGA_JUDGE) and not any(b in m for b in BUKAN_CHAT))
        assert pilih, f"Tidak ada model penilai yang tersedia. Model di akun: {tersedia}"
        for m in pilih:
            self.model = m
            if self._ping():
                break
            print(f"  model {m} sedang sibuk/tidak merespons, mencoba model berikutnya")
        else:
            raise RuntimeError("Semua model penilai sibuk. Coba lagi nanti, atau set PENYEDIA_JUDGE = 'groq' lalu jalankan ulang.")
        catat = {"penyedia": penyedia, "model": self.model, "generator": GENERATOR,
                 "dipilih": datetime.datetime.now().isoformat(timespec="seconds")}
        if lama:
            catat |= {"menggantikan": f"{kunci['penyedia']}/{lama}", "hasil_model_lama_dibuang": self._n_cache(lama),
                      "alasan_ganti": "kuota harian penyedia lama terlalu kecil"}
        json.dump(catat, open(model_file, "w"), indent=2)
        print("Model penilai dikunci:", penyedia, self.model, f"| menggantikan: {catat['menggantikan']}" if lama else "")

    @staticmethod
    def _json_dari(teks):
        """JSON dari jawaban model; buang blok <think> (Qwen3) dan teks di luar objek JSON."""
        teks = re.sub(r"<think>.*?</think>", "", str(teks), flags=re.S).strip()
        try:
            return json.loads(teks)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", teks, flags=re.S)
            if not m:
                raise
            return json.loads(m.group(0))

    def _n_cache(self, model):
        f = self.EVAL / "rating_llm_cache.jsonl"
        if not f.exists():
            return 0
        return sum(1 for line in open(f, encoding="utf-8") if json.loads(line).get("model") == model)

    def _ping(self, coba=3):
        for i in range(coba):
            try:
                if self.penyedia == "gemini":
                    self.client.models.generate_content(model=self.model, contents="Reply with the word ok.",
                                                        config=self._types.GenerateContentConfig(temperature=0, max_output_tokens=5))
                else:
                    self.client.chat.completions.create(model=self.model, max_tokens=5,
                                                        messages=[{"role": "user", "content": "Reply with the word ok."}])
                return True
            except Exception as e:
                print(f"  ping {self.model} gagal ({type(e).__name__}: {str(e)[:80]})")
                time.sleep(15 * (i + 1))
        return False

    def _panggil(self, sistem, pengguna, skema, kunci):
        if kunci in self._cache:
            return self._cache[kunci]["hasil"]
        if self.penyedia == "mock":
            h = int(hashlib.md5(kunci.encode()).hexdigest(), 16) % 1000
            hasil = ({"K1": 1 + h % 5, "K2": 1 + (h // 5) % 5, "K3": 1 + (h // 25) % 5, "K4": 1 + (h // 125) % 5,
                      "kesalahan": h % 4, "alasan": "mock"} if "K1" in skema["properties"] else
                     {"pilihan": ["1", "2", "seri"][h % 3], "alasan": "mock"})
        else:
            for coba in range(10):
                try:
                    if self.penyedia == "gemini":
                        T = self._types
                        resp = self.client.models.generate_content(model=self.model, contents=pengguna, config=T.GenerateContentConfig(
                            system_instruction=sistem, temperature=0, seed=SEED, response_mime_type="application/json",
                            response_json_schema=skema))
                        hasil = json.loads(resp.text)
                    else:
                        args = dict(model=self.model, temperature=0, seed=SEED, response_format={"type": "json_object"},
                                    messages=[{"role": "system", "content": sistem + " Reply with one JSON object that follows this JSON schema: " + json.dumps(skema)},
                                              {"role": "user", "content": pengguna}])
                        if self.model.startswith("qwen/") and getattr(self, "_rf_ok", True):
                            args["reasoning_format"] = "hidden"     # model penalaran: jawaban JSON tanpa blok <think>
                        try:
                            resp = self.client.chat.completions.create(**args)
                        except Exception as e:
                            if "reasoning_format" in args and "reasoning" in str(e).lower() and "429" not in str(e):
                                self._rf_ok = False
                                args.pop("reasoning_format")
                                resp = self.client.chat.completions.create(**args)
                            else:
                                raise
                        hasil = self._json_dari(resp.choices[0].message.content)
                    self._n_kuota = 0
                    break
                except KuotaHabis:
                    raise
                except Exception as e:
                    pesan = str(e)
                    if "429" in pesan or "RESOURCE_EXHAUSTED" in pesan or "rate_limit" in pesan.lower():
                        self._n_kuota = getattr(self, "_n_kuota", 0) + 1
                        harian = any(t in pesan.lower() for t in TANDA_KUOTA_HARIAN)
                        if harian or self._n_kuota >= 6:              # batas per menit cukup ditunggu; batas harian -> berhenti
                            selesai = sum(1 for k in self._cache if k.startswith(("tunggal|", "pasang|")))
                            raise KuotaHabis(f"Kuota harian {self.penyedia}/{self.model} habis. Tersimpan {selesai}/120 penilaian. "
                                             "Run all lagi besok; penilaian berlanjut dari titik ini (tidak mulai dari nol).")
                    tunggu = min(30 * 2 ** coba, 300)                 # 30, 60, 120, 240, 300 ... detik
                    print(f"  coba ulang {coba + 1}/10 dalam {tunggu} dtk ({type(e).__name__}: {str(e)[:100]})")
                    time.sleep(tunggu)
            else:
                raise RuntimeError("Panggilan LLM gagal 10 kali (server sibuk). Jalankan ulang sel ini nanti; hasil yang sudah ada tersimpan di cache.")
            time.sleep(self.jeda)
        rec = {"kunci": kunci, "model": self.model, "hasil": hasil, "waktu": datetime.datetime.now().isoformat(timespec="seconds")}
        with open(self.CACHE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._cache[kunci] = rec
        return hasil

    SISTEM_JUDGE = ("You are an impartial evaluator of career-recommendation explanations written for Indonesian IT students "
                    "(Politeknik Negeri Jakarta). Judge ONLY against the provided 'Fakta Sistem' (system facts) and the rubric. "
                    "Do not reward length. Claims that cannot be checked against the facts (general industry knowledge) are not errors. "
                    "Use integers only.")

    def penilai_llm(self, penyedia="groq", ganti_model=None):
        self._klien(penyedia, ganti_model)
        self.CACHE = self.EVAL / "rating_llm_cache.jsonl"
        self._cache = {}
        if self.CACHE.exists():
            for line in open(self.CACHE, encoding="utf-8"):
                r = json.loads(line)
                if r["model"] == self.model:
                    self._cache[r["kunci"]] = r
        self.jeda = 6.5 if penyedia == "gemini" else 3.0
        rubrik = "\n".join(" | ".join(x for x in r if x) for r in RUBRIK)
        sk_tunggal = {"type": "object", "properties": {k: {"type": "integer", "minimum": 1, "maximum": 5} for k in KRITERIA}
                      | {"kesalahan": {"type": "integer", "minimum": 0}, "alasan": {"type": "string"}},
                      "required": KRITERIA + ["kesalahan", "alasan"]}
        sk_pasang = {"type": "object", "properties": {"pilihan": {"type": "string", "enum": ["1", "2", "seri"]}, "alasan": {"type": "string"}},
                     "required": ["pilihan", "alasan"]}
        S = self.sampel.set_index(["pid", "versi"])
        tunggal, pasang = [], []
        for n, pid in enumerate(self.pids, 1):
            fakta = self.fakta(pid)
            teks = {v: rapikan(S.loc[(pid, v), "penjelasan"]) for v in "AB"}
            for v in "AB":
                u = (f"RUBRIC (score 5..1, columns: criterion | meaning | 5 | 4 | 3 | 2 | 1):\n{rubrik}\n\n"
                     f"FAKTA SISTEM:\n{fakta}\n\nEXPLANATION TO RATE:\n{teks[v]}\n\n"
                     "Return K1, K2, K3, K4 (1-5), kesalahan (number of claims contradicting the facts) and a one-sentence alasan.")
                h = self._panggil(self.SISTEM_JUDGE, u, sk_tunggal, f"tunggal|{pid}|{v}")
                tunggal.append({"pid": pid, "versi": v, **{k: int(h[k]) for k in KRITERIA}, "kesalahan": int(h["kesalahan"])})
            pil = []
            for urut in ("AB", "BA"):                                   # dua urutan untuk menetralkan bias posisi
                u = (f"RUBRIC:\n{rubrik}\n\nFAKTA SISTEM:\n{fakta}\n\nEXPLANATION 1:\n{teks[urut[0]]}\n\nEXPLANATION 2:\n{teks[urut[1]]}\n\n"
                     "Which explanation would you rather give to the student, considering all criteria? Answer '1', '2' or 'seri' (tie).")
                h = self._panggil(self.SISTEM_JUDGE, u, sk_pasang, f"pasang|{pid}|{urut}")
                pil.append({"1": urut[0], "2": urut[1]}.get(str(h["pilihan"]).strip().lower(), "Seri"))
            pasang.append({"pid": pid, "pilihan_AB": pil[0], "pilihan_BA": pil[1],
                           "preferensi": pil[0] if pil[0] == pil[1] else "Seri"})
            if n % 5 == 0:
                print(f"  {n}/{len(self.pids)} pasangan dinilai")
        self.llm_tunggal, self.llm_pasang = pd.DataFrame(tunggal), pd.DataFrame(pasang)
        self.llm_tunggal.to_csv(self.EVAL / "rating_llm_tunggal.csv", index=False)
        self.llm_pasang.to_csv(self.EVAL / "rating_llm_pasang.csv", index=False)
        konsisten = float((self.llm_pasang["pilihan_AB"] == self.llm_pasang["pilihan_BA"]).mean())
        # Sengaja tidak menampilkan skor per versi agar penilaian AR tetap tersamar.
        return {"penyedia": self.penyedia, "model": self.model, "penjelasan_dinilai": len(tunggal),
                "pasangan_dinilai": len(pasang), "konsistensi_urutan": round(konsisten, 3)}

    # ---------- Langkah 4: analisis (membuka kunci) ----------
    @staticmethod
    def _wilcoxon(rag, non):
        d = np.asarray(rag, float) - np.asarray(non, float)
        nz = d[d != 0]
        if len(nz) == 0:
            return {"n": len(d), "rerata_RAG": float(np.mean(rag)), "rerata_nonRAG": float(np.mean(non)),
                    "median_selisih": 0.0, "p": 1.0, "r_rank_biserial": 0.0}
        rk = pd.Series(np.abs(nz)).rank().values
        wp, wm = rk[nz > 0].sum(), rk[nz < 0].sum()
        return {"n": len(d), "n_beda": int(len(nz)), "rerata_RAG": round(float(np.mean(rag)), 3),
                "rerata_nonRAG": round(float(np.mean(non)), 3), "median_selisih": float(np.median(d)),
                "p": float(wilcoxon(rag, non, zero_method="wilcox").pvalue), "r_rank_biserial": round(float((wp - wm) / (wp + wm)), 3)}

    @staticmethod
    def _kappa(a, b):
        from sklearn.metrics import cohen_kappa_score
        a, b = np.asarray(a), np.asarray(b)
        if len(set(a) | set(b)) < 2:
            return {"kappa_w": None, "setuju_persis": float((a == b).mean()), "n": len(a)}
        return {"kappa_w": round(float(cohen_kappa_score(a, b, weights="quadratic", labels=[1, 2, 3, 4, 5])), 3),
                "setuju_persis": round(float((a == b).mean()), 3), "setuju_pm1": round(float((np.abs(a - b) <= 1).mean()), 3), "n": len(a)}

    @staticmethod
    def _panjang(df):
        rows = []
        for _, r in df.iterrows():
            for v in "AB":
                rows.append({"pid": r["pid"], "versi": v, **{k: r[f"{v}_{k}"] for k in KRITERIA + ["kesalahan"]}})
        out = pd.DataFrame(rows)
        out["total"] = out[KRITERIA].sum(axis=1)
        return out

    def analisis(self, paksa=False):
        if self.lembar is None:
            self.lembar = LembarLokal(self.EVAL) if self.lokal else LembarGoogle(self.folder_id)
        R, U = self._baca("Rating"), self._baca("Ulangan")
        okR, okU = self._lengkap(R), self._lengkap(U)
        if not okR.all() or (not okU.all() and not paksa):
            print(f"Analisis BELUM dijalankan (kunci tidak dibuka). Lengkap: Rating {int(okR.sum())}/{len(R)}, Ulangan {int(okU.sum())}/{len(U)}.")
            for tab, df, ok in (("Rating", R, okR), ("Ulangan", U, okU)):
                if 0 < (~ok).sum() <= 10:
                    print(f"  {tab}: baris belum lengkap (kolom no) =", df.loc[~ok, "no"].tolist())
            return None
        R.to_csv(self.EVAL / "rating_manual_isi_Rating.csv", index=False)
        U.to_csv(self.EVAL / "rating_manual_isi_Ulangan.csv", index=False)
        kunci = pd.read_csv(self.LOG / "penjelasan_sampel_manual_kunci.csv")
        kond = {(r.pid, r.versi): r.kondisi for r in kunci.itertuples()}
        H = self._panjang(R[okR])
        H["kondisi"] = [kond[(p, v)] for p, v in zip(H["pid"], H["versi"])]
        H.to_csv(self.EVAL / "rating_manual_hasil.csv", index=False)
        piv = lambda df, k: df.pivot(index="pid", columns="kondisi", values=k)
        hasil = {"manusia": {}}
        for k in KRITERIA + ["total", "kesalahan"]:
            p = piv(H, k)
            hasil["manusia"][k] = self._wilcoxon(p["rag"], p["non_rag"])
        pref = []
        for _, r in R[okR].iterrows():
            pref.append("Seri" if r["preferensi"] == "Seri" else kond[(r["pid"], r["preferensi"])])
        n_rag, n_non, n_seri = pref.count("rag"), pref.count("non_rag"), pref.count("Seri")
        hasil["manusia"]["preferensi"] = {"rag": n_rag, "non_rag": n_non, "seri": n_seri,
                                          "p_uji_tanda": float(binomtest(n_rag, n_rag + n_non, 0.5).pvalue) if n_rag + n_non else 1.0}
        # Konsistensi intra-penilai (Rating vs Ulangan)
        if okU.any():
            UL = self._panjang(U[okU]).set_index(["pid", "versi"])
            RL = self._panjang(R[okR]).set_index(["pid", "versi"]).loc[UL.index]
            hasil["intra_penilai"] = {k: self._kappa(RL[k].astype(int), UL[k].astype(int)) for k in KRITERIA}
            pr = R.set_index("pid").loc[U.loc[okU, "pid"], "preferensi"].values
            hasil["intra_penilai"]["preferensi_setuju"] = round(float((pr == U.loc[okU, "preferensi"].values).mean()), 3)
            tgl = lambda df: pd.to_datetime(df["tanggal_isi"], errors="coerce", dayfirst=True)
            jarak = (tgl(U[okU]).min() - tgl(R[okR]).max())
            hasil["intra_penilai"]["jarak_hari_min"] = None if pd.isna(jarak) else int(jarak.days)
        # Penilai LLM
        f_t, f_p = self.EVAL / "rating_llm_tunggal.csv", self.EVAL / "rating_llm_pasang.csv"
        if f_t.exists() and f_p.exists():
            L, LP = pd.read_csv(f_t), pd.read_csv(f_p)
            L["total"] = L[KRITERIA].sum(axis=1)
            L["kondisi"] = [kond[(p, v)] for p, v in zip(L["pid"], L["versi"])]
            M = H.merge(L, on=["pid", "versi"], suffixes=("_ar", "_llm"))
            hasil["ar_vs_llm"] = {k: self._kappa(M[f"{k}_ar"].astype(int), M[f"{k}_llm"].astype(int)) for k in KRITERIA}
            hasil["ar_vs_llm"]["spearman_total"] = round(float(spearmanr(M["total_ar"], M["total_llm"])[0]), 3)
            lp = LP.set_index("pid")["preferensi"]
            ar_p = R.set_index("pid")["preferensi"]
            hasil["ar_vs_llm"]["preferensi_setuju"] = round(float((ar_p.loc[lp.index] == lp).mean()), 3)
            hasil["llm"] = {k: self._wilcoxon(piv(L, k)["rag"], piv(L, k)["non_rag"]) for k in KRITERIA + ["total", "kesalahan"]}
            lpk = ["Seri" if x == "Seri" else kond[(p, x)] for p, x in zip(LP["pid"], LP["preferensi"])]
            a, b = lpk.count("rag"), lpk.count("non_rag")
            hasil["llm"]["preferensi"] = {"rag": a, "non_rag": b, "seri": lpk.count("Seri"),
                                          "p_uji_tanda": float(binomtest(a, a + b, 0.5).pvalue) if a + b else 1.0,
                                          "konsistensi_urutan": round(float((LP["pilihan_AB"] == LP["pilihan_BA"]).mean()), 3)}
            mf = self.LOG / "tahap12b_model_judge.json"
            hasil["model_judge"] = json.load(open(mf)) if mf.exists() else None
        t = hasil["manusia"]["total"]
        hasil["kesimpulan_utama"] = ("RAG lebih baik (skor total, p < 0,05)" if t["p"] < 0.05 and t["rerata_RAG"] > t["rerata_nonRAG"] else
                                     "non-RAG lebih baik (skor total, p < 0,05)" if t["p"] < 0.05 else
                                     "Tidak ada perbedaan signifikan pada skor total (p >= 0,05)")
        log = {"tanggal": datetime.datetime.now().isoformat(timespec="seconds"), "seed": SEED, "penilai_manusia": 1,
               "pasangan": int(okR.sum()), "ulangan": int(okU.sum()), "analisis_dipaksa": bool(paksa and not okU.all()), **hasil}
        with open(self.LOG / "tahap12b_log.json", "w") as fp:
            json.dump(log, fp, indent=2, ensure_ascii=False, default=float)
        return log
