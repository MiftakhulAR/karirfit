import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from career_model.scoring import score  # noqa: E402

# two careers with identical requirements: only interest (M) separates them
MODEL = {
    "params": {"alpha": 0.5, "grade_points": {"A": 1.0, "B": 0.75}},
    "careers": [
        {"id": "b", "name_en": "B", "name_id": "B", "group": "primary",
         "requirements": [{"skill": "sql", "weight": 3.0}, {"skill": "py", "weight": 1.0}]},
        {"id": "a", "name_en": "A", "name_id": "A", "group": "primary",
         "requirements": [{"skill": "sql", "weight": 3.0}, {"skill": "py", "weight": 1.0}]},
    ],
    "interests": [{"id": "data", "careers": ["b"]}],
    "skills": [{"id": "sql"}, {"id": "py"}],
    "courses": [{"id": "db", "name_en": "Databases", "skills": ["sql"]}],
}


class Fit(unittest.TestCase):
    def test_equation_3_5(self):
        # K = (3 * 0.75 [course grade B] + 1 * 0.67 [self: intermediate]) / 4 = 0.73
        r = {x["career"]: x for x in score({"courses": {"db": "B"}, "skills": {"py": "intermediate"},
                                            "interests": ["data"]}, MODEL)}
        self.assertAlmostEqual(r["b"]["K"], 0.73)
        self.assertAlmostEqual(r["b"]["fit"], 100 * (0.5 * 0.73 + 0.5 * 1))   # Fit = 100 [aK + (1-a)M]
        self.assertAlmostEqual(r["a"]["fit"], 100 * 0.5 * 0.73)
        self.assertEqual(r["b"]["rank"], 1)

    def test_ties_broken_by_name(self):
        ranked = score({}, MODEL)   # empty profile: both 0, same K -> English name order
        self.assertEqual([x["career"] for x in ranked], ["a", "b"])
        self.assertEqual(ranked[0]["gaps"][0]["skill"], "sql")


if __name__ == "__main__":
    unittest.main()
