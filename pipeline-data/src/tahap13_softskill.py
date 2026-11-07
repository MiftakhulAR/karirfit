"""Tahap 13 (v2b, 20 Okt 2026) — soft skill berlabel elemen O*NET 31.0 pada lowongan TI, demand ulang, uji ranking ulang.

Dipanggil dari notebook 13b_softskill_onet_v2.ipynb. Aturan sama dengan Tahap 8–10: split 70/30 (split_iklan.csv),
ambang 10% iklan, w = d * log(1 + C/m_s), K = sum(w*e)/sum(w), data uji holdout_uji.csv (iklan uji dengan >= 3 skill teknis).

Riwayat kamus soft skill (disetujui AR):
  v1 19 Okt  28 soft skill, presisi pola 0,904
  v1b 19 Okt 9 perbaikan pola (SOA, confidential, optimise, adaptive design, data integrity, menempati,
             persistent database, "bertanggung jawab pada ..." sebagai tugas, "tepat waktu"), presisi 0,968
  v2 20 Okt  "interpersonal skills" -> Social Perceptiveness (sebelumnya Social Orientation);
             "cross-functional team" -> Cooperation (sebelumnya Coordination). 29 soft skill, presisi 0,944
  v2b 20 Okt 5 perbaikan pola (reliable and <produk>, security and integrity, outgoing documentation,
             creative/kreatif pada jurusan & nama PT serta "innovative solutions", "dinegosiasikan"), presisi 0,965
File Tahap 8 tidak ditimpa; keluaran memakai akhiran _v3 (bobot/demand) dan _v4 (kamus).
"""
import hashlib
import json
import math
import re
import warnings
import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest, wilcoxon

warnings.filterwarnings("ignore", message="This pattern is interpreted as a regular expression")
SEED, AMBANG, VERSI_KAMUS = 42, 10.0, "v2b (20 Okt 2026)"

# (O*NET element, O*NET domain, regex pola iklan ID/EN)
SOFT_ONET = [
    # (O*NET element, O*NET domain, pattern)
    ("Speaking", "Skill", r"communication skills?|good communicat\w*|excellent communicat\w*|strong communicat\w*|verbal communicat\w*|"
                          r"kemampuan (ber)?komunikasi|komunikasi (yang )?(baik|efektif|lisan)|komunikatif|presentation skills?|"
                          r"kemampuan presentasi|public speaking"),
    ("Writing", "Skill", r"written communicat\w*|writing skills?|kemampuan menulis|komunikasi (tertulis|lisan dan tertulis)|"
                         r"verbal and written|lisan (maupun|dan) tulisan"),
    ("Active Listening", "Skill", r"active listening|good listener|mendengarkan dengan baik|pendengar yang baik"),
    ("Critical Thinking", "Skill", r"critical thinking|berpikir kritis|analytical (thinking|skills?|mind)|kemampuan analis\w*|"
                                   r"logical thinking|berpikir (logis|analitis)|analitis"),
    ("Complex Problem Solving", "Skill", r"problem[ -]solving|solve (complex )?problems?|pemecahan masalah|memecahkan masalah|"
                                         r"menyelesaikan masalah|problem solver"),
    ("Active Learning", "Skill", r"fast learner|quick learner|willing(ness)? to learn|eager to learn|keen to learn|"
                                r"cepat belajar|mau belajar|kemauan (untuk )?belajar|keinginan (untuk )?belajar|senang belajar"),
    ("Time Management", "Skill", r"time management|manajemen waktu|mengatur waktu|tight deadlines?|meet(ing)? deadlines?|multi[- ]?task\w*"),
    ("Coordination", "Skill", r"coordinat\w+ with|berkoordinasi|koordinasi dengan"),
    ("Service Orientation", "Skill", r"customer[- ](oriented|focus\w*|service orient\w*)|service[- ]oriented\b(?! (architectur|soa|programming|design|concept|computing))|service orientation|berorientasi (pada )?pelanggan|orientasi pelayanan"),
    ("Negotiation", "Skill", r"negotiation|negotiating|(?<!di)negosiasi(?!kan)"),
    ("Persuasion", "Skill", r"persuasi\w*|persuasive|influenc\w+ (skills?|stakeholders?)"),
    ("Instructing", "Skill", r"mentor(ing)? (junior|team|other)|coach(ing)? (junior|team)|membimbing (junior|tim)|train(ing)? (junior|new) (staff|members?)"),
    ("Social Perceptiveness", "Skill", r"interpersonal skills?|kemampuan interpersonal|hubungan interpersonal"),
    ("Cooperation", "Work Style", r"team[ -]?work|team player|work(ing)? (well )?(in|as|with) a team|collaborat\w*|kolaborasi|kerja ?sama|bekerja (sama )?dalam (sebuah )?tim|bekerja secara tim|kerja tim|cross[- ]functional (teams?|collaboration)"),
    ("Leadership Orientation", "Work Style", r"leadership|kepemimpinan|jiwa pemimpin|lead (a|the) team|memimpin tim"),
    ("Attention to Detail", "Work Style", r"attention to details?|detail[- ]oriented|keen eye for detail|teliti|ketelitian|cermat"),
    ("Adaptability", "Work Style", r"adaptab\w*|\badaptif\b|\badaptive\b(?! (design|layout|ui|web|streaming|bitrate|learning))|mudah beradaptasi|mampu beradaptasi|flexib\w+ (to|in|with)"),
    ("Initiative", "Work Style", r"proactive|proaktif|self[- ]starter|self[- ]motivated|berinisiatif|inisiatif (tinggi|yang|dan)|take (the )?initiative|(show|showing|with) initiative|motivasi (yang )?tinggi|highly motivated"),
    ("Dependability", "Work Style", r"\bresponsible and (honest|disciplined|reliable|hard)|bertanggung ?jawab(?!\s*(atas|terhadap|untuk|dalam|pada|kepada|penuh atas|mengelola|melakukan|menangani|memastikan|menjaga|membuat))|\bdependable\b|\bdisiplin\b|\bdisciplined\b|\breliable and (honest|responsible|hard[- ]?working|trustworthy|committed|disciplined)|\breliable (person|individual|team)"),
    ("Integrity", "Work Style", r"integritas (yang )?tinggi|berintegritas|high(est)? (level of )?integrity|(?<!data )(?<!consistency )\bintegrity and\b(?! (system|security|availability|confidentiality))|(?<!data )(?<!consistency )(?<!security )\band integrity\b|\bjujur\b|\bhonest\b(?! company)|honesty"),
    ("Stress Tolerance", "Work Style", r"under pressure|bawah tekanan|dalam tekanan|stress tolerance|tahan (terhadap )?tekanan"),
    ("Achievement Orientation", "Work Style", r"result[s]?[- ]oriented|target[- ]oriented|goal[- ]oriented|berorientasi (pada )?(target|hasil)|"
                                              r"achievement[- ]oriented"),
    ("Innovation", "Work Style", r"(?<!/)\bcreative\b(?!/)(?! (suite|cloud|agency|industry|director|team|studio|multimedia|media))|\bcreativity\b|(?<!PT )\bkreatif\b|kreativitas|innovative (thinking|mind|ideas?)|\binovatif\b"),
    ("Intellectual Curiosity", "Work Style", r"curious|curiosity|rasa ingin tahu|passion for (learning|technology)"),
    ("Self-Confidence", "Work Style", r"self[- ]confiden\w*|percaya diri|\bconfident(ly)?\b"),
    ("Perseverance", "Work Style", r"persever\w*|\bpersistent\b(?! (database|storage|volume|data|disk|connection|queue|memory))|pantang menyerah|\bulet\b|\btekun\b|tenacious"),
    ("Social Orientation", "Work Style", r"mudah bergaul|(?<!incoming and )(?<!incoming & )\boutgoing\b(?! (project |the )?(documentation|documents?|calls?|e-?mails?|mail|traffic|goods|shipments?|letters?))|sociable"),
    ("Optimism", "Work Style", r"positive attitude|sikap positif|\boptimis(tic|tik|me)?\b|\boptimist\b"),
    ("Empathy", "Work Style", r"\bempath\w*|\bempati\b"),
]


class Tahap13:
    def __init__(self, project_dir):
        P = Path(project_dir)
        self.OUT, self.LOG, self.EVAL = P / "02_processed", P / "logs", P / "04_eval"
        self.WEB = P / "05_artifacts" / "web"
        self.EVAL.mkdir(exist_ok=True)
        self.WEB.mkdir(parents=True, exist_ok=True)

    # ---------- Langkah 1: data ----------
    def muat_data(self):
        ti = pd.read_csv(self.OUT / "lowongan_ti.csv", low_memory=False)
        ti["iid"] = ti["sumber"].astype(str) + "|" + ti["id_lowongan"].astype(str)
        self.split = pd.read_csv(self.OUT / "split_iklan.csv")
        self.kamus = pd.read_csv(self.OUT / "kamus_skill_v3.csv", keep_default_na=False)
        self.R_v1 = pd.read_csv(self.OUT / "bobot_skill_karier.csv")
        self.uji_v1 = pd.read_csv(self.OUT / "holdout_uji.csv", keep_default_na=False)
        t = ti.merge(self.split, on="iid")
        t["teks_norm"] = t["teks"].astype(str).str.replace(r"([a-z])([A-Z])", r"\1 \2", regex=True)
        self.teks = t
        return {"iklan_berteks_lengkap": len(t), **t["split"].value_counts().to_dict()}

    # ---------- Langkah 2: deteksi skill ----------
    def deteksi(self):
        lama = set(self.kamus.loc[self.kamus["kategori"] == "Soft skill", "skill"])
        self.TEKNIS = [s for s in self.kamus["skill"] if s not in lama]
        self.BAHASA = ["Bahasa Inggris"]
        self.SOFT = [e for e, _, _ in SOFT_ONET]
        self.POLA = {r["skill"]: re.compile(r["pola"], re.I) for _, r in self.kamus.iterrows()
                     if r["skill"] in self.TEKNIS + self.BAHASA}
        self.POLA.update({e: re.compile(p, re.I) for e, _, p in SOFT_ONET})
        for s, pola in self.POLA.items():
            self.teks[s] = self.teks["teks_norm"].str.contains(pola)
        self.kamus_v4 = pd.concat([
            self.kamus[self.kamus["skill"].isin(self.TEKNIS)].assign(jenis="hard", sumber="kamus v3 (Tahap 8)"),
            self.kamus[self.kamus["skill"].isin(self.BAHASA)].assign(kategori="Bahasa", jenis="hard", sumber="kamus v3 (Tahap 8)"),
            pd.DataFrame([{"skill": e, "kategori": "Soft skill", "pola": p, "jenis": "soft", "sumber": f"O*NET 31.0 — {d}"}
                          for e, d, p in SOFT_ONET]),
        ], ignore_index=True)
        self.kamus_v4.to_csv(self.OUT / "kamus_skill_v4.csv", index=False)
        frek = (self.teks[self.SOFT].mean() * 100).round(1).sort_values(ascending=False)
        return {"teknis": len(self.TEKNIS), "bahasa": len(self.BAHASA), "soft": len(self.SOFT)}, frek

    # ---------- Langkah 3: validasi pola ----------
    def sampel_validasi(self):
        rng = np.random.default_rng(SEED)

        def cuplikan(t, pola, lebar=80):
            m = pola.search(t)
            return t[max(0, m.start() - lebar): m.end() + lebar].replace("\n", " ") if m else ""
        rows = []
        for s in self.SOFT:
            idx = self.teks.index[self.teks[s]]
            for i in rng.choice(idx, size=min(10, len(idx)), replace=False):
                rows.append({"skill": s, "iid": self.teks.at[i, "iid"], "karier": self.teks.at[i, "karier"],
                             "cuplikan": cuplikan(self.teks.at[i, "teks_norm"], self.POLA[s])})
        self.sampel = pd.DataFrame(rows)
        self.sampel.to_csv(self.EVAL / "validasi_softskill_sampel_v2.csv", index=False)
        return len(self.sampel)

    def presisi(self, file_label="validasi_softskill_label_v2.csv"):
        """Label (skill, iid, label 1/0, catatan) digabung ke sampel. Cuplikan tanpa label dilaporkan."""
        f = self.EVAL / file_label
        if not f.exists():
            self.PRESISI = None
            return None, None
        lab = pd.read_csv(f, keep_default_na=False)
        kunci = ["skill", "iid"]
        if "h" in lab.columns:                                   # format ringkas: h = 8 karakter awal md5(iid)
            self.sampel["h"] = self.sampel["iid"].map(lambda x: hashlib.md5(str(x).encode()).hexdigest()[:8])
            kunci = ["skill", "h"]
        m = self.sampel.merge(lab[kunci + ["label", "catatan"]], on=kunci, how="left")
        tanpa = m[m["label"].astype(str).isin(["", "nan"])]
        m = m[~m.index.isin(tanpa.index)].copy()
        m["label"] = m["label"].astype(float)
        m.to_csv(self.EVAL / "validasi_softskill_sampel_v2_terlabel.csv", index=False)
        self.PRESISI = {"total": round(float(m["label"].mean()), 3), "n": int(len(m)), "tanpa_label": int(len(tanpa)),
                        "per_skill": m.groupby("skill")["label"].mean().round(2).to_dict()}
        salah = m[m["label"] == 0][["skill", "karier", "catatan", "cuplikan"]]
        return self.PRESISI, salah

    # ---------- Langkah 4: demand dan bobot ----------
    def bobot(self):
        SK = self.TEKNIS + self.BAHASA + self.SOFT
        b = self.teks[self.teks["split"] == "bangun"]
        N = b.groupby("karier").size()
        dem = (b.groupby("karier")[SK].sum().stack().rename("n_lowongan").reset_index().rename(columns={"level_1": "skill"}))
        dem = dem[dem["n_lowongan"] > 0].merge(N.rename("n_total"), left_on="karier", right_index=True)
        dem["persen"] = (dem["n_lowongan"] / dem["n_total"] * 100).round(1)
        dem = dem.merge(self.kamus_v4[["skill", "kategori", "jenis"]], on="skill").sort_values(["karier", "persen"], ascending=[True, False])
        dem.to_csv(self.OUT / "demand_skill_karier_v3.csv", index=False)
        R = dem[dem["persen"] >= AMBANG].copy()
        C = self.split["karier"].nunique()
        R = R.merge(R.groupby("skill")["karier"].nunique().rename("m_s"), left_on="skill", right_index=True)
        R["d"] = R["n_lowongan"] / R["n_total"]
        R["idf"] = (1 + C / R["m_s"]).map(math.log)
        R["w"] = (R["d"] * R["idf"]).round(4)
        R.to_csv(self.OUT / "bobot_skill_karier_v3.csv", index=False)
        self.R = R
        ringkas = pd.DataFrame({"R(c) Tahap 8": self.R_v1.groupby("karier").size(), "R(c) v3": R.groupby("karier").size(),
                                "soft di R(c)": R[R["jenis"] == "soft"].groupby("karier").size()}).fillna(0).astype(int)
        soft_karier = R[R["jenis"] == "soft"].groupby("skill")["karier"].apply(list).to_dict()
        return ringkas, soft_karier

    # ---------- Langkah 5: uji ranking ----------
    def uji_ranking(self):
        u = self.uji_v1[self.uji_v1["layak_uji"].astype(str) == "True"].copy()
        u["S_teknis"] = u["skill_teknis"].str.split(";").map(set)
        det = self.teks.set_index("iid").loc[u["iid"], self.BAHASA + self.SOFT]
        u["S_lengkap"] = [a | set(det.columns[det.loc[i].values]) for a, i in zip(u["S_teknis"], u["iid"])]
        K = sorted(self.split["karier"].unique())
        W1 = {c: dict(zip(g["skill"], g["w"])) for c, g in self.R_v1.groupby("karier")}
        W3 = {c: dict(zip(g["skill"], g["w"])) for c, g in self.R.groupby("karier")}

        def peringkat(W, S, benar):
            sk = {c: sum(w for s, w in W[c].items() if s in S) / sum(W[c].values()) for c in K}
            return sorted(K, key=lambda c: (-sk[c], c)).index(benar) + 1
        u["rank_v1"] = [peringkat(W1, S, k) for S, k in zip(u["S_teknis"], u["karier"])]
        u["rank_v3_teknis"] = [peringkat(W3, S, k) for S, k in zip(u["S_teknis"], u["karier"])]
        u["rank_v3_lengkap"] = [peringkat(W3, S, k) for S, k in zip(u["S_lengkap"], u["karier"])]

        def metrik(df, col):
            r = df[col]
            return pd.Series({"Hit@1": (r == 1).mean(), "Hit@3": (r <= 3).mean(), "MRR": (1 / r).mean(), "n": len(r)})
        self.VAR = ["v1", "v3_teknis", "v3_lengkap"]
        per = pd.concat({v: u.groupby("karier").apply(metrik, col=f"rank_{v}", include_groups=False) for v in self.VAR}, axis=1)
        self.makro = {v: per[v][["Hit@1", "Hit@3", "MRR"]].mean().round(3).to_dict() for v in self.VAR}
        self.mikro = {v: metrik(u, f"rank_{v}")[["Hit@1", "Hit@3", "MRR"]].astype(float).round(3).to_dict() for v in self.VAR}
        per.round(3).to_csv(self.EVAL / "ranking_holdout_softskill_per_karier.csv")
        u.drop(columns=["S_teknis", "S_lengkap"]).to_csv(self.EVAL / "ranking_holdout_softskill_hasil.csv", index=False)
        self.u = u
        return self.makro, self.mikro, per.round(3)

    def uji_statistik(self):
        def mcnemar(a, b):
            n01, n10 = int((~a & b).sum()), int((a & ~b).sum())
            p = binomtest(n10, n01 + n10, 0.5).pvalue if n01 + n10 else 1.0
            return {"baru_benar_v1_salah": n10, "v1_benar_baru_salah": n01, "p": float(p)}
        rng = np.random.default_rng(SEED)
        self.stat = {}
        for v in ["v3_teknis", "v3_lengkap"]:
            rb, r1 = self.u[f"rank_{v}"], self.u["rank_v1"]
            diff = (1 / rb - 1 / r1).values
            boot = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(2000)]
            self.stat[v] = {"McNemar_Hit@1": mcnemar((rb == 1).values, (r1 == 1).values),
                            "McNemar_Hit@3": mcnemar((rb <= 3).values, (r1 <= 3).values),
                            "Wilcoxon_RR_p": float(wilcoxon(1 / rb, 1 / r1, zero_method="wilcox").pvalue) if diff.any() else 1.0,
                            "selisih_MRR_mikro": float(diff.mean()),
                            "CI95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]}
        return self.stat

    # ---------- Langkah 6: ekspor web dan log ----------
    def simpan(self):
        kriteria = {v: {"Hit@3_makro>=0.80": bool(self.makro[v]["Hit@3"] >= 0.80)} for v in self.VAR}
        cols = ["karier", "skill", "n_lowongan", "n_total", "persen", "kategori", "m_s", "d", "idf", "w"]
        self.R[cols].to_csv(self.WEB / "bobot_skill_karier.csv", index=False)
        self.kamus_v4[["skill", "kategori", "pola", "jenis", "sumber"]].to_csv(self.WEB / "kamus_skill_v4.csv", index=False)
        log = {"tanggal": datetime.datetime.now().isoformat(timespec="seconds"), "versi_kamus_soft": VERSI_KAMUS,
               "seed": SEED, "ambang_%": AMBANG, "soft_skill_onet": len(self.SOFT),
               "skill_total": len(self.TEKNIS + self.BAHASA + self.SOFT), "profil_uji": int(len(self.u)),
               "R_c_rata2": {"Tahap8": round(float(self.R_v1.groupby("karier").size().mean()), 1),
                             "v3": round(float(self.R.groupby("karier").size().mean()), 1)},
               "makro": self.makro, "mikro": self.mikro, "uji_statistik": self.stat, "kriteria": kriteria,
               "presisi_pola_softskill": self.PRESISI}
        lama = self.LOG / "tahap13_log.json"
        if lama.exists() and "versi_kamus_soft" not in json.loads(lama.read_text()):
            lama.rename(self.LOG / "tahap13_log_v1b.json")          # simpan hasil run 19 Okt sebagai arsip
        with open(self.LOG / "tahap13_log.json", "w") as fp:
            json.dump(log, fp, indent=2, ensure_ascii=False, default=float)
        return {k: log[k] for k in ["R_c_rata2", "makro", "kriteria"]}, sorted(p.name for p in self.WEB.iterdir())
