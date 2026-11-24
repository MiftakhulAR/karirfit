"""
Administrator catalogue maintenance (FR10): careers, skills, interest areas and course templates.

model.json (built by tools/build_model.py from the Colab artefacts) stays the evaluated baseline. Changes made
in the admin panel are stored as rows (kind, id, payload) in the database and applied on top of it at start-up
and after every change; payload None deletes an item, and removing the row restores the original.

  validate(kind, item_id, data, model) -> clean payload (raises ValueError with a readable message)
  apply(base, rows)                   -> model dict with the changes applied and references kept consistent
"""
from __future__ import annotations

import math
import re

KINDS = ("careers", "skills", "interests", "courses")
ID_RE = re.compile(r"^[a-z0-9_]{2,60}$")


# messages are shown in the (Indonesian-only) admin panel
LABELS = {"name": "Nama", "category": "Kategori", "name_id": "Nama (ID)", "name_en": "Nama (EN)",
          "skills": "keterampilan", "careers": "karier"}


def _text(data: dict, key: str, max_len: int, required: bool = True) -> str:
    v = str(data.get(key) or "").strip()
    if required and not v:
        raise ValueError(f"{LABELS.get(key, key)} wajib diisi")
    if len(v) > max_len:
        raise ValueError(f"{LABELS.get(key, key)} lebih dari {max_len} karakter")
    return v


def _ids(values, valid: set[str], what: str, max_n: int) -> list[str]:
    out = list(dict.fromkeys(str(v) for v in (values or [])))
    if len(out) > max_n:
        raise ValueError(f"maksimal {max_n} {LABELS.get(what, what)}")
    unknown = [v for v in out if v not in valid]
    if unknown:
        raise ValueError(f"{LABELS.get(what, what)} tidak dikenal: {', '.join(unknown[:5])}")
    return out


def _weights(model: dict, career_id: str, reqs: list[dict]) -> list[dict]:
    """Equation 3.2, w = d * ln(1 + |C| / m(s)), with |C| and m(s) counted over the IT careers of the current
    catalogue (this career included), so a new career is weighted like the evaluated ones."""
    it = [c for c in model["careers"] if c["group"] != "non_it" and c["id"] != career_id]
    n = len(it) + 1
    out = []
    for r in reqs:
        m = 1 + sum(any(x["skill"] == r["skill"] for x in c["requirements"]) for c in it)
        out.append({"skill": r["skill"], "demand": r["demand"], "weight": round(r["demand"] * math.log(1 + n / m), 6)})
    return sorted(out, key=lambda x: -x["weight"])


def validate(kind: str, item_id: str, data: dict, model: dict) -> dict:
    if kind not in KINDS:
        raise ValueError("jenis katalog tidak dikenal")
    existing = next((x for x in model[kind] if x["id"] == item_id), None)
    if existing is None and not ID_RE.match(item_id):
        raise ValueError("ID harus 2-60 karakter: huruf kecil, angka atau _")
    skills = {s["id"] for s in model["skills"]}

    if kind == "skills":
        kind_ = data.get("kind") or "hard"
        if kind_ not in ("hard", "soft"):
            raise ValueError("jenis harus hard atau soft")
        patterns = [str(p) for p in (data.get("patterns") or []) if str(p).strip()][:10]
        for p in patterns:
            try:
                re.compile(p, re.I)
            except re.error as e:
                raise ValueError(f"pola regex tidak valid {p!r}: {e}") from None
        name = _text(data, "name", 80)
        out = {"id": item_id, "name": name, "category": _text(data, "category", 60), "kind": kind_, "patterns": patterns,
               "name_id": _text(data, "name_id", 80, False) or name, "name_en": _text(data, "name_en", 80, False) or name}
        return (existing or {}) | out

    if kind == "careers":
        group = data.get("group") or (existing or {}).get("group") or "alternative"
        if group not in ("primary", "alternative", "non_it"):
            raise ValueError("kelompok harus primary, alternative atau non_it")
        out = (existing or {}) | {"id": item_id, "name_id": _text(data, "name_id", 120), "name_en": _text(data, "name_en", 120),
                                  "group": group}
        if group == "non_it":
            if existing is None or existing["group"] != "non_it":
                raise ValueError("karier baru harus karier TI (primary atau alternative); profil O*NET hanya berasal dari O*NET")
            return out   # O*NET requirements are importance ratings from O*NET; only the names can be edited
        reqs = []
        for r in data.get("requirements") or []:
            d = float(r.get("demand", 0))
            if not 0 < d <= 1:
                raise ValueError("permintaan harus antara 0 dan 1 (proporsi iklan lowongan)")
            reqs.append({"skill": str(r.get("skill")), "demand": round(d, 4)})
        if not reqs:
            raise ValueError("karier TI membutuhkan minimal satu keterampilan")
        _ids([r["skill"] for r in reqs], skills, "skills", 80)
        soft = {s["id"] for s in model["skills"] if s.get("kind") == "soft"}
        out["requirements"] = _weights(model, item_id, reqs)
        out["soft_skills"] = [{"skill": r["skill"], "demand": r["demand"]} for r in out["requirements"] if r["skill"] in soft]
        out.setdefault("onet_soc", "")
        out.setdefault("n_ads", 0)
        return out

    if kind == "interests":
        careers = {c["id"] for c in model["careers"]}
        return (existing or {}) | {"id": item_id, "name_id": _text(data, "name_id", 120), "name_en": _text(data, "name_en", 120),
                                   "careers": _ids(data.get("careers"), careers, "careers", 1000)}

    # courses
    cats = {c["id"] for c in model.get("course_categories", [])} or {"prodi"}
    category = data.get("category") or "prodi"
    if category not in cats:
        raise ValueError(f"kelompok mata kuliah harus salah satu dari: {', '.join(sorted(cats))}")
    try:
        semester = int(data.get("semester") or 1)
        credits = int(data["credits"]) if data.get("credits") not in (None, "") else None
    except (TypeError, ValueError):
        raise ValueError("semester dan SKS harus bilangan bulat") from None
    if not 1 <= semester <= 8 or (credits is not None and not 1 <= credits <= 8):
        raise ValueError("semester dan SKS harus antara 1 dan 8")
    return (existing or {}) | {"id": item_id, "name_id": _text(data, "name_id", 160), "name_en": _text(data, "name_en", 160, False)
                               or _text(data, "name_id", 160), "semester": semester, "credits": credits, "category": category,
                               "skills": _ids(data.get("skills"), skills, "skills", 30)}


def apply(base: dict, rows) -> dict:
    """rows: iterable of (kind, item_id, payload_or_None, ts). Returns a new model; base is not modified."""
    m = dict(base)
    changed = {k: {} for k in KINDS}
    for kind, item_id, payload, *_ in rows:
        if kind in changed:
            changed[kind][item_id] = payload
    for kind in KINDS:
        if not changed[kind]:
            continue
        items = [changed[kind].get(x["id"], x) if x["id"] in changed[kind] else x for x in base[kind]]
        known = {x["id"] for x in base[kind]}
        items += [p for i, p in changed[kind].items() if i not in known and p is not None]
        m[kind] = [x for x in items if x is not None]

    skills = {s["id"] for s in m["skills"]}
    careers = {c["id"] for c in m["careers"]}

    def drop_skills(c: dict) -> dict:   # copy a career only when it loses a deleted skill; others stay shared with base
        if all(r["skill"] in skills for r in c["requirements"] + c.get("soft_skills", [])):
            return c
        return c | {"requirements": [r for r in c["requirements"] if r["skill"] in skills],
                    "soft_skills": [r for r in c.get("soft_skills", []) if r["skill"] in skills]}

    if changed["skills"]:
        m["careers"] = [drop_skills(c) for c in m["careers"]]
        m["courses"] = [c if all(s in skills for s in c["skills"]) else c | {"skills": [s for s in c["skills"] if s in skills]}
                        for c in m["courses"]]
        m["crosswalk"] = {s: [e for e in els if e in skills] for s, els in base.get("crosswalk", {}).items() if s in skills}
        soft = {x["id"]: x for x in base.get("soft_skills", [])}
        for s in m["skills"]:
            if s["id"] in changed["skills"]:
                soft.pop(s["id"], None)
                if s.get("kind") == "soft":
                    soft[s["id"]] = {"id": s["id"], "name_en": s.get("name_en", s["name"]), "name_id": s.get("name_id", s["name"]),
                                     "patterns": s.get("patterns", [])}
        m["soft_skills"] = [x for x in soft.values() if x["id"] in skills]
    if changed["careers"]:
        m["interests"] = [i if all(c in careers for c in i["careers"]) else i | {"careers": [c for c in i["careers"] if c in careers]}
                          for i in m["interests"]]
    m["params"] = base["params"] | {"n_careers": sum(c["group"] != "non_it" for c in m["careers"])}
    m["catalog_changes"] = sum(len(v) for v in changed.values())
    return m
