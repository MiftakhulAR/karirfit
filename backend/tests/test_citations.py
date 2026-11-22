import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import llm  # noqa: E402

P = [{"id": "skkni-00385"}, {"id": "profil_karier-14b"}]


class StripUnknownCitations(unittest.TestCase):
    def test_unknown_markers_removed_known_kept(self):
        text = "Anda menguasai SQL [FACT-SQL] dan analisis [skkni-00385]. Saran [FACTS]."
        clean, removed = llm.strip_unknown_citations(text, P)
        self.assertEqual(clean, "Anda menguasai SQL dan analisis [skkni-00385]. Saran.")
        self.assertEqual(removed, ["FACT-SQL", "FACTS"])

    def test_grouped_citations_filtered(self):
        clean, removed = llm.strip_unknown_citations("Bukti [skkni-00385, P1, profil_karier-14b].", P)
        self.assertEqual(clean, "Bukti [skkni-00385, profil_karier-14b].")
        self.assertEqual(removed, ["P1"])

    def test_plain_bracket_words_untouched(self):
        text = "Pelajari [Python] dan [contoh: proyek web]."
        self.assertEqual(llm.strip_unknown_citations(text, P), (text, []))


if __name__ == "__main__":
    unittest.main()
