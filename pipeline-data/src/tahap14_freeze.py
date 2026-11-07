"""Tahap 14 (20 Okt 2026) — kunci model LLM, uji sensitivitas ambang, pemeriksaan integritas, cek sampel label, manifest.

Dipanggil dari notebook 14_freeze_sensitivitas.ipynb. Tidak mengubah keluaran Tahap 8–13; hanya menulis:
  logs/model_final.json, 04_eval/sensitivitas_ambang.csv, logs/integritas_data.json,
  Google Sheet 04_eval/cek_label_claude_v1 (+ logs/cek_label_log.json bila sudah diisi),
  logs/manifest_data_final.json dan .csv (sidik SHA-256 seluruh artefak).
"""
import datetime
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
AMBANG_UJI = (5.0, 7.5, 10.0, 12.5, 15.0, 20.0)
N_CEK_SOFT, N_CEK_TAU = 40, 30
NAMA_SHEET_CEK = "cek_label_claude_v1"
NAMA_SHEET_TAU2 = "cek_label_tau_v2"     # 20 Okt: v1 tidak menampilkan skill kueri sehingga kriterianya tidak setara dengan pelabelan Tahap 11
FILE_WEB_BOLEH = {"bobot_skill_karier.csv", "kamus_skill_v4.csv"}          # 05_artifacts/web hanya data publik
GOOGLE_NATIVE = {".gsheet", ".gdoc", ".gslides", ".gform", ".gdraw", ".gmap", ".gsite", ".gjam", ".gscript"}


class Tahap14:
    def __init__(self, project_dir, folder_id_eval=None, lokal=False):
        self.P = Path(project_dir)
        self.OUT, self.LOG, self.EVAL = self.P / "02_processed", self.P / "logs", self.P / "04_eval"
        self.WEB, self.KB = self.P / "05_artifacts" / "web", self.P / "03_kb"
        self.folder_id, self.lokal = folder_id_eval, lokal

    @staticmethod
    def _json(f):
        return json.load(open(f)) if Path(f).exists() else None

    # ---------- 1. Kunci model LLM ----------
    def kunci_model(self):
        gen = self._json(self.LOG / "tahap12_model_groq.json")
        log12 = self._json(self.LOG / "tahap12_log.json") or {}
        judge = self._json(self.LOG / "tahap12b_model_judge.json")
        lama = self._json(self.LOG / "tahap12_model.json")
        assert gen, "logs/tahap12_model_groq.json tidak ditemukan"
        cek = log12.get("model") == gen["model"]
        final = {"tanggal": datetime.datetime.now().isoformat(timespec="seconds"),
                 "generator": {"penyedia": gen["penyedia"], "model": gen["model"], "suhu": 0,
                               "dipakai_di": ["Tahap 12 (120 penjelasan RAG/non-RAG)", "web: penjelasan AI dan Tanya AI"]},
                 "penilai_kedua": judge,
                 "cocok_dengan_tahap12_log": cek, "model_di_tahap12_log": log12.get("model"),
                 "catatan": ("logs/tahap12_model.json (" + str((lama or {}).get("model")) + ") dan tahap12_model_gemini.json berasal dari run uji "
                             "awal 18 Okt dan TIDAK dipakai untuk hasil akhir. Model final dikunci di file ini.")}
        json.dump(final, open(self.LOG / "model_final.json", "w"), indent=2, ensure_ascii=False)
        return final

    # ---------- 2. Sensitivitas ambang ----------
    def _siap13(self):
        if getattr(self, "T13", None) is None:
            import tahap13_softskill as M13
            T = M13.Tahap13(self.P)
            T.muat_data()
            T.deteksi()                                  # menulis ulang kamus_skill_v4.csv dengan isi identik (deterministik)
            u = T.uji_v1[T.uji_v1["layak_uji"].astype(str) == "True"].copy()
            u["S_teknis"] = u["skill_teknis"].str.split(";").map(set)
            det = T.teks.set_index("iid").loc[u["iid"], T.BAHASA + T.SOFT]
            u["S_lengkap"] = [a | set(det.columns[det.loc[i].values]) for a, i in zip(u["S_teknis"], u["iid"])]
            self.T13, self.u, self.M13 = T, u, M13
        return self.T13

    def _bobot(self, ambang, idf=True, teks=None):
        T = self.T13
        SK = T.TEKNIS + T.BAHASA + T.SOFT
        teks = T.teks if teks is None else teks
        b = teks[teks["split"] == "bangun"]
        N = b.groupby("karier").size()
        dem = (b.groupby("karier")[SK].sum().stack().rename("n_lowongan").reset_index().rename(columns={"level_1": "skill"}))
        dem = dem[dem["n_lowongan"] > 0].merge(N.rename("n_total"), left_on="karier", right_index=True)
        dem["persen"] = (dem["n_lowongan"] / dem["n_total"] * 100).round(1)
        dem = dem.merge(T.kamus_v4[["skill", "jenis"]], on="skill")
        R = dem[dem["persen"] >= ambang].copy()
        C = T.split["karier"].nunique()
        R["m_s"] = R["skill"].map(R.groupby("skill")["karier"].nunique())
        R["w"] = (R["n_lowongan"] / R["n_total"] * ((1 + C / R["m_s"]).map(math.log) if idf else 1.0)).round(4)
        return R

    def _ranking(self, R, u=None):
        K = sorted(self.T13.split["karier"].unique())
        W = {c: dict(zip(g["skill"], g["w"])) for c, g in R.groupby("karier")}

        def peringkat(S, benar):
            sk = {c: (sum(w for s, w in W.get(c, {}).items() if s in S) / sum(W[c].values())) if W.get(c) else 0.0 for c in K}
            return sorted(K, key=lambda c: (-sk[c], c)).index(benar) + 1
        u = self.u if u is None else u
        out = {}
        for prof in ("teknis", "lengkap"):
            r = pd.Series([peringkat(S, k) for S, k in zip(u[f"S_{prof}"], u["karier"])], index=u.index)
            g = pd.DataFrame({"karier": u["karier"], "r": r}).groupby("karier")["r"]
            out[prof] = {"Hit@1": round(float(g.apply(lambda x: (x == 1).mean()).mean()), 3),
                         "Hit@3": round(float(g.apply(lambda x: (x <= 3).mean()).mean()), 3),
                         "MRR": round(float(g.apply(lambda x: (1 / x).mean()).mean()), 3)}
        return out

    def sensitivitas(self, ambang=AMBANG_UJI):
        self._siap13()
        rows = []
        for a in list(ambang) + ["10.0 tanpa IDF"]:
            idf = not isinstance(a, str)
            nilai = 10.0 if not idf else a
            R = self._bobot(nilai, idf=idf)
            m = self._ranking(R)
            n_c = R.groupby("karier").size()
            rows.append({"varian": f"ambang {nilai:g}%" + ("" if idf else " tanpa IDF"), "ambang_%": nilai, "idf": idf,
                         "R_c_rata2": round(float(n_c.mean()), 1), "R_c_min": int(n_c.min()),
                         "soft_di_R_rata2": round(float(R[R["jenis"] == "soft"].groupby("karier").size().reindex(n_c.index, fill_value=0).mean()), 1),
                         **{f"teknis_{k}": v for k, v in m["teknis"].items()}, **{f"lengkap_{k}": v for k, v in m["lengkap"].items()}})
        df = pd.DataFrame(rows)
        df.to_csv(self.EVAL / "sensitivitas_ambang.csv", index=False)
        log13 = self._json(self.LOG / "tahap13_log.json")
        acuan = df[(df["ambang_%"] == 10.0) & df["idf"]].iloc[0]
        self.reproduksi = {"teknis": {k: float(acuan[f"teknis_{k}"]) for k in ("Hit@1", "Hit@3", "MRR")},
                           "tahap13_log": log13["makro"]["v3_teknis"] if log13 else None}
        self.reproduksi["sama"] = self.reproduksi["teknis"] == self.reproduksi["tahap13_log"]
        return df, self.reproduksi

    # ---------- 2b. Sensitivitas normalisasi camelCase (21 Okt, keputusan AR: opsi A) ----------
    def sensitivitas_camelcase(self):
        """Tahap 8/13 memecah camelCase ("MySQL" -> "My SQL") sebelum mencocokkan pola. Di sini skill teknis dideteksi
        ulang pada teks asli (soft skill & Bahasa Inggris tetap seperti Tahap 13), bobot dihitung ulang (ambang 10%, IDF),
        profil uji ikut dideteksi ulang, lalu Hit@k dibandingkan. Bobot utama TIDAK diubah; ini hanya uji sensitivitas.
        Himpunan iklan uji tetap sama (layak_uji Tahap 8) agar sebanding."""
        T = self._siap13()
        teks2 = T.teks.copy()
        raw = teks2["teks"].astype(str)
        beda = []
        for s in T.TEKNIS:
            baru = raw.str.contains(T.POLA[s])
            lama = teks2[s]
            if (baru != lama).any():
                beda.append({"skill": s, "iklan_sekarang": int(lama.sum()), "iklan_teks_asli": int(baru.sum()),
                             "hilang": int((baru & ~lama).sum()), "tambahan_salah": int((lama & ~baru).sum())})
            teks2[s] = baru
        beda = pd.DataFrame(beda).sort_values("hilang", ascending=False)
        beda.to_csv(self.EVAL / "sensitivitas_camelcase_skill.csv", index=False)
        u2 = self.u.copy()
        d2 = teks2.set_index("iid").loc[u2["iid"]]
        u2["S_teknis"] = [{s for s in T.TEKNIS if d2.at[i, s]} for i in u2["iid"]]
        u2["S_lengkap"] = [a | {s for s in T.BAHASA + T.SOFT if d2.at[i, s]} for a, i in zip(u2["S_teknis"], u2["iid"])]
        R1, R2 = self._bobot(10.0), self._bobot(10.0, teks=teks2)
        m1, m2 = self._ranking(R1), self._ranking(R2, u2)
        rows = []
        for prof in ("teknis", "lengkap"):
            for k in ("Hit@1", "Hit@3", "MRR"):
                rows.append({"profil": prof, "metrik": k, "dipakai": m1[prof][k], "deteksi_teks_asli": m2[prof][k],
                             "selisih": round(m2[prof][k] - m1[prof][k], 3)})
        hasil = pd.DataFrame(rows)
        hasil.to_csv(self.EVAL / "sensitivitas_camelcase.csv", index=False)
        log = {"tanggal": datetime.datetime.now().isoformat(timespec="seconds"),
               "iklan_berteks": int(len(teks2)), "iklan_uji": int(len(u2)),
               "baris_bobot": {"dipakai": int(len(R1)), "deteksi_teks_asli": int(len(R2))},
               "metrik": rows, "skill_terdampak_top10": beda.head(10).to_dict("records"),
               "catatan": "Uji sensitivitas saja (keputusan AR 21 Okt, opsi A); bobot dan hasil utama tetap memakai deteksi Tahap 8/13."}
        json.dump(log, open(self.LOG / "sensitivitas_camelcase.json", "w"), indent=2, ensure_ascii=False)
        return hasil, beda

    # ---------- 3. Pemeriksaan integritas ----------
    def integritas(self):
        hasil = []

        def cek(nama, kondisi, detail=""):
            hasil.append({"cek": nama, "lulus": bool(kondisi), "detail": str(detail)})
        web = pd.read_csv(self.WEB / "bobot_skill_karier.csv")
        v3 = pd.read_csv(self.OUT / "bobot_skill_karier_v3.csv")
        a = web.set_index(["karier", "skill"])["w"].sort_index()
        b = v3.set_index(["karier", "skill"])["w"].sort_index()
        cek("Bobot web = bobot_skill_karier_v3 (karier, skill, w)", a.index.equals(b.index) and np.allclose(a.values, b.values),
            f"{len(a)} baris")
        cek("15 karier tervalidasi ada di bobot web", web["karier"].nunique() == 15, web["karier"].nunique())
        cek("Bobot tanpa NaN dan w > 0", web["w"].notna().all() and (web["w"] > 0).all())
        k4 = pd.read_csv(self.WEB / "kamus_skill_v4.csv", keep_default_na=False)
        soft = k4[k4["jenis"] == "soft"]
        cek("Kamus v4: 29 soft skill O*NET", len(soft) == 29, len(soft))
        cek("Kamus v4 memuat Social Perceptiveness", "Social Perceptiveness" in set(soft["skill"]))
        cek("Kamus v4: sumber soft skill = O*NET 31.0", soft["sumber"].str.startswith("O*NET 31.0").all())
        log13 = self._json(self.LOG / "tahap13_log.json") or {}
        cek("Log Tahap 13 = versi kamus v2b", str(log13.get("versi_kamus_soft", "")).startswith("v2b"), log13.get("versi_kamus_soft"))
        sp = pd.read_csv(self.OUT / "split_iklan.csv")
        cek("Split 70/30: tidak ada iklan di dua bagian", sp.groupby("iid")["split"].nunique().max() == 1,
            sp["split"].value_counts().to_dict())
        uji = pd.read_csv(self.OUT / "holdout_uji.csv", keep_default_na=False)
        n_uji = int((uji["layak_uji"].astype(str) == "True").sum())
        cek("Data uji hold-out n = 1.766", n_uji == 1766, n_uji)
        sm = pd.read_csv(self.EVAL / "penjelasan_sampel_manual.csv")
        cek("Sampel rating: 30 pid x A/B", sm["pid"].nunique() == 30 and len(sm) == 60, len(sm))
        cek("Kunci A/B tersedia di logs", (self.LOG / "penjelasan_sampel_manual_kunci.csv").exists())
        isi_web = {p.name for p in self.WEB.iterdir() if p.is_file()}
        cek("05_artifacts/web hanya berisi file publik", isi_web <= FILE_WEB_BOLEH, sorted(isi_web))
        mf = self._json(self.LOG / "model_final.json") or {}
        cek("Model generator dikunci (model_final.json) dan cocok dengan log Tahap 12", mf.get("cocok_dengan_tahap12_log") is True,
            (mf.get("generator") or {}).get("model"))
        if getattr(self, "reproduksi", None):
            cek("Uji ulang ambang 10% = hasil Tahap 13 (makro teknis)", self.reproduksi["sama"], self.reproduksi["teknis"])
        df = pd.DataFrame(hasil)
        json.dump({"tanggal": datetime.datetime.now().isoformat(timespec="seconds"), "lulus_semua": bool(df["lulus"].all()),
                   "cek": hasil}, open(self.LOG / "integritas_data.json", "w"), indent=2, ensure_ascii=False)
        return df

    # ---------- 4. Cek sampel label buatan Claude oleh AR ----------
    def _lembar(self, nama=NAMA_SHEET_CEK):
        import tahap12b_rating as M12b
        if self.lokal:
            lem = M12b.LembarLokal(self.EVAL, nama)
            lem.ada = lambda: (lem.dir / "Petunjuk.csv").exists()
            return lem
        return M12b.LembarGoogle(self.folder_id, nama)

    def _indeks_cek(self, soft, tau):
        rng = np.random.default_rng(SEED)
        i_s = sorted(rng.choice(len(soft), size=min(N_CEK_SOFT, len(soft)), replace=False))
        i_t = sorted(rng.choice(len(tau), size=min(N_CEK_TAU, len(tau)), replace=False))
        return i_s, i_t

    def lembar_cek_tau_v2(self):
        """Tab Tau ulang dengan skill kueri (cocok/gap profil uji Tahap 11), sama seperti saat label asli dibuat."""
        lem = self._lembar(NAMA_SHEET_TAU2)
        if lem.ada():
            print("Lembar τ v2 sudah ada, TIDAK ditimpa:", lem.url())
            return lem.url()
        soft, tau = self._sumber_cek()
        _, i_t = self._indeks_cek(soft, tau)
        q = pd.read_csv(self.EVAL / "tau_dev_kueri.csv", keep_default_na=False)
        cocok = q.groupby("karier")["cocok"].apply(lambda s: " | ".join(s)).to_dict()
        gap = q.groupby("karier")["gap"].apply(lambda s: " | ".join(s)).to_dict()
        kb = pd.read_json(self.KB / "kb_v2_chunks.jsonl", lines=True)
        teks, jenis = dict(zip(kb["chunk_id"], kb["teks"].str.slice(0, 1500))), dict(zip(kb["chunk_id"], kb["jenis"]))
        Tt = pd.DataFrame({"no": range(1, len(i_t) + 1), "ref": i_t, "karier": tau.loc[i_t, "karier"].values,
                           "chunk_id": tau.loc[i_t, "chunk_id"].values})
        Tt.insert(3, "skill_kueri_dimiliki", Tt["karier"].map(cocok).fillna(""))
        Tt.insert(4, "skill_kueri_gap", Tt["karier"].map(gap).fillna(""))
        Tt["jenis"] = Tt["chunk_id"].map(jenis).fillna("")
        Tt["teks_passage"] = Tt["chunk_id"].map(teks).fillna("")
        Tt["label_AR"], Tt["catatan"] = "", ""
        Tt = Tt.sample(frac=1, random_state=SEED).assign(no=range(1, len(Tt) + 1))
        petunjuk = [
            ["Cek ulang label τ (versi 2). Sama dengan pelabelan Tahap 11: passage dinilai untuk KUERI profil uji, bukan hanya untuk kariernya."],
            ["Kueri = karier + skill yang dimiliki (kolom skill_kueri_dimiliki) + skill yang perlu ditingkatkan (kolom skill_kueri_gap). Tanda | memisahkan dua profil uji (A dan B)."],
            ["label_AR = 1 bila passage memuat informasi yang membantu menjelaskan rekomendasi karier itu untuk profil tersebut (kompetensi, standar, atau MK yang berkaitan dengan skill dimiliki/gap)."],
            ["label_AR = 0 bila passage hanya terkait karier secara umum tetapi tidak menyentuh skill-skill itu, atau isinya administratif (riwayat rilis, daftar pustaka, CPL umum, jadwal)."],
            ["Isi 1 atau 0, lalu Run all notebook 14."],
        ]
        lem.buat({"Petunjuk": petunjuk, "Tau": Tt})
        print("Lembar τ v2 dibuat:", lem.url())
        return lem.url()

    def _sumber_cek(self):
        soft = pd.read_csv(self.EVAL / "validasi_softskill_sampel_v2_terlabel.csv", keep_default_na=False)
        tau = pd.read_csv(self.EVAL / "tau_dev_label_unik_terlabel.csv")
        return soft, tau

    def lembar_cek_label(self):
        lem = self._lembar()
        if lem.ada():
            print("Lembar cek label sudah ada, TIDAK ditimpa:", lem.url())
            return lem.url()
        soft, tau = self._sumber_cek()
        i_s, i_t = self._indeks_cek(soft, tau)
        S = pd.DataFrame({"no": range(1, len(i_s) + 1), "ref": i_s, "skill": soft.loc[i_s, "skill"].values,
                          "cuplikan": soft.loc[i_s, "cuplikan"].values, "label_AR": "", "catatan": ""})
        S = S.sample(frac=1, random_state=SEED).assign(no=range(1, len(S) + 1))
        teks = {}
        f_kb = self.KB / "kb_v2_chunks.jsonl"
        if f_kb.exists():
            kb = pd.read_json(f_kb, lines=True)
            teks = dict(zip(kb["chunk_id"], kb["teks"].str.slice(0, 1500)))
            jenis = dict(zip(kb["chunk_id"], kb["jenis"]))
        else:
            print("Peringatan: 03_kb/kb_v2_chunks.jsonl tidak ditemukan; kolom teks dikosongkan.")
            jenis = {}
        Tt = pd.DataFrame({"no": range(1, len(i_t) + 1), "ref": i_t, "karier": tau.loc[i_t, "karier"].values,
                           "chunk_id": tau.loc[i_t, "chunk_id"].values})
        Tt["jenis"] = Tt["chunk_id"].map(jenis).fillna("")
        Tt["teks_passage"] = Tt["chunk_id"].map(teks).fillna("")
        Tt["label_AR"], Tt["catatan"] = "", ""
        Tt = Tt.sample(frac=1, random_state=SEED).assign(no=range(1, len(Tt) + 1))
        petunjuk = [
            ["Cek sampel label yang dibuat Claude (diisi AR). Label Claude disembunyikan; kesepakatan dihitung di notebook 14."],
            ["SoftSkill: label_AR = 1 bila cuplikan iklan benar menunjukkan soft skill itu sebagai syarat/sifat KANDIDAT; 0 bila bukan (profil perusahaan, sifat produk, jurusan, gaji, dll.)."],
            ["Tau: label_AR = 1 bila passage berguna untuk menjelaskan kompetensi, standar, atau mata kuliah yang terkait karier di kolom karier; 0 bila tidak."],
            ["Isi kolom label_AR dengan 1 atau 0. Kolom catatan boleh kosong. Setelah selesai, Run all notebook 14."],
        ]
        lem.buat({"Petunjuk": petunjuk, "SoftSkill": S, "Tau": Tt})
        print("Lembar cek label dibuat:", lem.url())
        return lem.url()

    def analisis_cek_label(self):
        from sklearn.metrics import cohen_kappa_score
        lem = self._lembar()
        if not lem.ada():
            print("Lembar cek label belum dibuat.")
            return None
        soft, tau = self._sumber_cek()
        lem2 = self._lembar(NAMA_SHEET_TAU2)
        tau_v2 = lem2.ada()
        hasil = {"lembar_tau": NAMA_SHEET_TAU2 if tau_v2 else NAMA_SHEET_CEK + " (v1: tanpa skill kueri, kriteria tidak setara)"}
        for tab, src in (("SoftSkill", soft), ("Tau", tau)):
            d = (lem2 if (tab == "Tau" and tau_v2) else lem).baca(tab)
            lab = pd.to_numeric(d["label_AR"].astype(str).str.strip(), errors="coerce")
            if not lab.isin([0, 1]).all():
                print(f"{tab}: {int(lab.isin([0, 1]).sum())}/{len(d)} baris terisi. Analisis menunggu lembar lengkap.")
                return None
            ref = d["ref"].astype(int).values
            claude = src.loc[ref, "label" if tab == "SoftSkill" else "relevan_1_0"].astype(float).astype(int).values
            ar = lab.astype(int).values
            setuju = float((ar == claude).mean())
            n = len(ar)
            z = 1.96
            pusat = (setuju + z * z / (2 * n)) / (1 + z * z / n)
            lebar = z * math.sqrt(setuju * (1 - setuju) / n + z * z / (4 * n * n)) / (1 + z * z / n)
            hasil[tab] = {"n": n, "setuju": round(setuju, 3), "CI95_wilson": [round(pusat - lebar, 3), round(pusat + lebar, 3)],
                          "kappa": round(float(cohen_kappa_score(ar, claude)), 3) if len(set(ar) | set(claude)) > 1 else None,
                          "presisi_label_claude_menurut_AR": round(float(ar[claude == 1].mean()), 3) if (claude == 1).any() else None,
                          "beda": [{"ref": int(r), "claude": int(c), "AR": int(a)} for r, c, a in zip(ref, claude, ar) if c != a]}
        if tau_v2:
            d1 = lem.baca("Tau")
            l1 = pd.to_numeric(d1["label_AR"].astype(str).str.strip(), errors="coerce")
            hasil["Tau_v1_AR_kriteria_lama"] = {"n": int(len(l1)), "proporsi_1": round(float(l1.mean()), 3) if l1.notna().all() else None}
        log = {"tanggal": datetime.datetime.now().isoformat(timespec="seconds"), "seed": SEED, **hasil}
        json.dump(log, open(self.LOG / "cek_label_log.json", "w"), indent=2, ensure_ascii=False)
        return log

    # ---------- 5. Manifest (pembekuan) ----------
    def manifest(self, folder=("02_processed", "03_kb", "04_eval", "05_artifacts", "logs", "src")):
        rows = []
        berkas = [p for f in folder if (self.P / f).exists() for p in sorted((self.P / f).rglob("*")) if p.is_file()]
        berkas += sorted(p for p in self.P.glob("*.ipynb") if p.is_file())
        for p in berkas:
            if "__pycache__" in p.parts or p.name.startswith("manifest_data_final"):
                continue
            st = p.stat()
            if p.suffix in GOOGLE_NATIVE:                     # Google Sheets/Docs di Drive bukan berkas biasa: dicatat tanpa hash
                rows.append({"path": str(p.relative_to(self.P)), "bytes": st.st_size, "sha256": "google-native",
                             "diubah": datetime.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")})
                continue
            h = hashlib.sha256()
            try:
                with open(p, "rb") as fp:
                    for blok in iter(lambda: fp.read(1 << 20), b""):
                        h.update(blok)
                sidik = h.hexdigest()
            except OSError as e:
                sidik = f"tidak-terbaca: {e.strerror}"
            rows.append({"path": str(p.relative_to(self.P)), "bytes": st.st_size, "sha256": sidik,
                         "diubah": datetime.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")})
        df = pd.DataFrame(rows)
        df.to_csv(self.LOG / "manifest_data_final.csv", index=False)
        ring = {"tanggal": datetime.datetime.now().isoformat(timespec="seconds"), "jumlah_file": len(df),
                "total_MB": round(df["bytes"].sum() / 1e6, 1),
                "per_folder": df.assign(folder=df["path"].str.split("/").str[0]).groupby("folder")["bytes"].agg(["size", "sum"])
                .rename(columns={"size": "file", "sum": "bytes"}).to_dict("index"),
                "file_google_tanpa_hash": int((df["sha256"] == "google-native").sum()),
                "file_tak_terbaca": int(df["sha256"].astype(str).str.startswith("tidak-terbaca").sum()),
                "catatan": "Sidik SHA-256 untuk memastikan angka di naskah berasal dari berkas ini. Google Sheets/Docs dicatat tanpa hash. Jalankan ulang Tahap 14 bila ada berkas yang berubah."}
        json.dump(ring, open(self.LOG / "manifest_data_final.json", "w"), indent=2, ensure_ascii=False, default=int)
        return ring
