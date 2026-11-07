"""Builds backend/model.json from the thesis pipeline tables (careerai artifacts, Colab Tahap 8-13 v2b).

Input (backend/data_careerai/):
  bobot_skill_karier.csv  career, skill, n_lowongan, n_total, persen, kategori, m_s, d, idf, w
                          (training split of the Indonesian IT job ads, threshold 10 %, w = d * ln(1 + |C| / m(s)))
  kamus_skill_v4.csv      skill dictionary v4: 106 technical skills + 29 O*NET soft skills, regex pattern (ID/EN)
  katalog_karier.csv      15 IT careers, graduate-profile flag, interest areas
  mk_skill_web.csv        PNJ Informatics courses (curriculum 2021) -> skills (from the RPS)
  terjemahan.json         Indonesian names of interest areas and soft skills
The weights w are copied as computed in Colab, so the web gives exactly the notebook ranking.
Soft skills are part of R(c) (Tahap 13 v2b) and are scored like technical skills.

Run:  python tools/build_model.py
"""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SRC = HERE / "data_careerai"

# Peraturan Pendidikan PNJ 2023/2024 Pasal 10 (0-4), e(s) = points / 4  (Bab III 3.5.2, v8.2: D = 0.25)
GRADE_POINTS = {"A": 4.0, "A-": 3.7, "B+": 3.3, "B": 3.0, "B-": 2.7, "C+": 2.3, "C": 2.0, "D": 1.0, "E": 0.0}
SELF_LEVEL = {"advanced": 1.0, "intermediate": 0.67, "beginner": 0.33}


def slug(s: str) -> str:
    s = s.lower().replace("c#", "csharp").replace("c/c++", "c_cpp").replace(".net", "dotnet").replace("node.js", "nodejs")
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def rows(name):
    return list(csv.DictReader(open(SRC / name, encoding="utf-8")))


def main():
    tr = json.load(open(SRC / "terjemahan.json", encoding="utf-8"))
    kamus = rows("kamus_skill_v4.csv")
    sid = {k["skill"]: slug(k["skill"]) for k in kamus}
    assert len(set(sid.values())) == len(sid), "skill slug collision"
    skills = [{"id": sid[k["skill"]], "name": k["skill"], "category": k["kategori"], "kind": k["jenis"],
               "patterns": [k["pola"]]} for k in kamus]
    for s in skills:                                   # every pattern must compile in Python
        [re.compile(p, re.I) for p in s["patterns"]]
    soft_skills = [{"id": sid[k["skill"]], "name_en": k["skill"], "name_id": tr["soft"].get(k["skill"], k["skill"]),
                    "patterns": [k["pola"]]} for k in kamus if k["jenis"] == "soft"]

    katalog = rows("katalog_karier.csv")
    cid = {c["karier"]: slug(c["karier"]) for c in katalog}
    req = defaultdict(list)
    n_ads = {}
    for r in rows("bobot_skill_karier.csv"):
        req[r["karier"]].append({"skill": sid[r["skill"]], "demand": round(float(r["d"]), 4), "weight": float(r["w"]),
                                 "n_ads": int(r["n_lowongan"]), "soft": r["kategori"] == "Soft skill"})
        n_ads[r["karier"]] = int(r["n_total"])
    careers = []
    for c in katalog:
        items = sorted(req[c["karier"]], key=lambda x: -x["weight"])
        careers.append({"id": cid[c["karier"]], "name_en": c["karier"], "name_id": c["karier"],
                        "group": "primary" if c["profil_lulusan"] == "1" else "alternative",
                        "onet_soc": c["onet_soc"], "n_ads": n_ads.get(c["karier"], 0),
                        "requirements": [{k: x[k] for k in ("skill", "demand", "weight")} for x in items],
                        "soft_skills": [{"skill": x["skill"], "demand": x["demand"]} for x in items if x["soft"]]})
    areas = defaultdict(list)
    for c in katalog:
        for a in c["area_minat"].split(";"):
            areas[a.strip()].append(cid[c["karier"]])
    interests = [{"id": slug(a), "name_en": a, "name_id": tr["interests"].get(a, a), "careers": cs} for a, cs in areas.items()]

    courses = {}
    for r in rows("mk_skill_web.csv"):
        c = courses.setdefault(r["kode"], {"id": r["kode"], "name_id": r["nama_mata_kuliah"], "name_en": r["nama_mata_kuliah"],
                                          "semester": int(r["semester"]), "skills": [], "category": "it"})
        if sid[r["skill"]] not in c["skills"]:
            c["skills"].append(sid[r["skill"]])
    courses = sorted(courses.values(), key=lambda c: (c["semester"], c["id"]))

    n_train = sum(n_ads.values())
    model = {
        "version": 2,
        "data_label": "iklan lowongan TI Indonesia",
        "demand_source": f"Lowongan TI Indonesia: {n_train} iklan latih (70 % dari 8.228 iklan), kamus skill v4",
        "n_ads_train": n_train,
        "params": {"alpha": 0.5, "threshold": 0.1, "n_careers": len(careers),
                   "grade_points": {g: round(p / 4, 4) for g, p in GRADE_POINTS.items()}, "self_level": SELF_LEVEL},
        "careers": careers,
        "interests": interests,
        "skills": skills,
        "soft_skills": soft_skills,
        "courses": courses,
        "course_categories": [{"id": "it", "name_id": "Teknik Informatika PNJ (Kurikulum 2021)",
                               "name_en": "PNJ Informatics (curriculum 2021)"}],
    }
    out = HERE / "model.json"
    json.dump(model, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{out}: {len(careers)} careers, {sum(len(c['requirements']) for c in careers)} weights, "
          f"{len(skills)} skills ({len(soft_skills)} soft), {len(courses)} courses, {len(interests)} interest areas, {n_train} ads")


if __name__ == "__main__":
    main()
