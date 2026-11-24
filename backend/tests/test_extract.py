import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from career_model.extract import SkillExtractor, with_experience_patterns  # noqa: E402

SKILLS = json.loads((Path(__file__).resolve().parents[1] / "model.json").read_text(encoding="utf-8"))["skills"]
STORY = ("Saya pernah jadi ketua panitia acara kampus, menyusun anggaran di Excel, mengatur jadwal, "
         "dan memimpin 15 anggota.")   # experience text of peer test PT6


class ExperiencePhrases(unittest.TestCase):
    def test_soft_skills_found_in_experience_text(self):
        found = SkillExtractor(with_experience_patterns(SKILLS)).skill_set(STORY)
        self.assertEqual(found, {"excel", "leadership_orientation", "time_management"})

    def test_job_ad_dictionary_unchanged(self):
        self.assertEqual(SkillExtractor(SKILLS).skill_set(STORY), {"excel"})
        self.assertEqual(SkillExtractor(with_experience_patterns(SKILLS)).skill_set("dipimpin oleh manajer"), set())


if __name__ == "__main__":
    unittest.main()
