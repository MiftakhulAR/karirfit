import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from career_model.scoring import recommend  # noqa: E402
from claims import check_explanation  # noqa: E402

MODEL = json.load(open(Path(__file__).resolve().parents[1] / "model.json", encoding="utf-8"))


class Claims(unittest.TestCase):
    """The evidence-support metric of Section 4.8: what counts as supported and what does not."""

    def test_supported_and_unsupported_claims(self):
        profile = {"skills": {"python": "advanced", "sql": "advanced"}, "interests": []}
        r = next(x for x in recommend(profile, MODEL)["all"] if x["career"] == "data_analyst_bi")
        gap = next(g for g in r["gaps"] if g.get("demand") is not None)
        gap_name = next(s["name"] for s in MODEL["skills"] if s["id"] == gap["skill"])
        text = (f"1. Dasar kecocokan\nSkor kecocokan {round(r['fit'])}/100 [skkni-1].\n"
                f"2. Kompetensi yang sudah sesuai\nPython\n"
                f"3. Kompetensi yang perlu ditingkatkan\n{gap_name} {gap['demand'] * 100:.0f}% [FACTS]\n"
                f"4. Saran pengembangan\nPelajari {gap_name}.")
        out = check_explanation(text, r, MODEL, [{"id": "skkni-1", "text": ""}], profile)
        by = {(c["type"], c["supported"]) for c in out["claims"]}
        self.assertIn(("fit_score", True), by)
        self.assertIn(("citation", True), by)        # [skkni-1] was retrieved
        self.assertIn(("citation", False), by)       # [FACTS] was not: counted as unsupported
        self.assertIn(("demand", True), by)
        self.assertTrue(out["four_parts"])
        self.assertTrue(out["gaps_correct"])
        self.assertLess(out["evidence_support"], 1.0)


if __name__ == "__main__":
    unittest.main()
