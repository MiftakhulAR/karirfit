import json
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import catalog  # noqa: E402

BASE = json.load(open(Path(__file__).resolve().parents[1] / "model.json", encoding="utf-8"))


class Catalog(unittest.TestCase):
    def test_new_career_weighted_with_equation_3_2(self):
        p = catalog.validate("careers", "game_dev", {"name_id": "Game Developer", "name_en": "Game Developer",
                                                     "group": "alternative",
                                                     "requirements": [{"skill": "python", "demand": 0.5}]}, BASE)
        it = [c for c in BASE["careers"] if c["group"] != "non_it"]
        m = 1 + sum(any(r["skill"] == "python" for r in c["requirements"]) for c in it)
        self.assertAlmostEqual(p["requirements"][0]["weight"], round(0.5 * math.log(1 + (len(it) + 1) / m), 6))
        model = catalog.apply(BASE, [("careers", "game_dev", p, 0)])
        self.assertEqual(model["params"]["n_careers"], 16)
        self.assertEqual(len(BASE["careers"]) + 1, len(model["careers"]))   # base untouched
        self.assertEqual(BASE["params"]["n_careers"], 15)

    def test_deleted_skill_leaves_no_dangling_references(self):
        model = catalog.apply(BASE, [("skills", "python", None, 0)])
        self.assertFalse(any(r["skill"] == "python" for c in model["careers"] for r in c["requirements"]))
        self.assertFalse(any("python" in c["skills"] for c in model["courses"]))
        self.assertNotIn("python", model.get("crosswalk", {}))
        self.assertTrue(any(r["skill"] == "python" for c in BASE["careers"] for r in c["requirements"]))

    def test_deleted_career_removed_from_interests(self):
        cid = BASE["interests"][0]["careers"][0]
        model = catalog.apply(BASE, [("careers", cid, None, 0)])
        self.assertFalse(any(cid in i["careers"] for i in model["interests"]))

    def test_validation_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            catalog.validate("skills", "x_bad", {"name": "X", "category": "Y", "patterns": ["(unclosed"]}, BASE)
        with self.assertRaises(ValueError):
            catalog.validate("careers", "new_one", {"name_id": "A", "name_en": "A", "requirements": [{"skill": "nope", "demand": 0.3}]}, BASE)
        with self.assertRaises(ValueError):
            catalog.validate("courses", "Bad Id!", {"name_id": "A"}, BASE)


if __name__ == "__main__":
    unittest.main()
