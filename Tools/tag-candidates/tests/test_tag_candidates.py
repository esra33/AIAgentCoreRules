import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tag_candidates as tc  # noqa: E402


class TagCandidatesTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write(self, name: str, content: str) -> Path:
        path = self.tmp / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_parse_claude_md_imports_flat(self):
        self._write("Rules/A.md", "## apply: always\n\nSome rule text here.\n")
        self._write("Rules/B.md", "## apply: always\n\nAnother rule entirely.\n")
        claude_md = self._write(
            "CLAUDE.md",
            "@Rules/A.md\n@Rules/B.md\nNot an import line\n",
        )
        resolved = tc.parse_claude_md_imports(claude_md)
        self.assertEqual(len(resolved), 2)
        self.assertTrue(all(p.is_file() for p in resolved))

    def test_parse_claude_md_imports_missing_file_skipped(self):
        claude_md = self._write("CLAUDE.md", "@Rules/DoesNotExist.md\n")
        self.assertEqual(tc.parse_claude_md_imports(claude_md), [])

    def test_exact_ngram_repeat_across_files_is_new_candidate(self):
        repeated = "Every resource acquisition must have a matching release in the same scope today"
        a = self._write("A.md", f"- {repeated}\n")
        b = self._write("B.md", f"- {repeated}\n")
        candidates = tc.build_candidates(
            files=[a, b], core_tags={}, ngram=8, near_dup_threshold=0.9,
            min_words=6, tag_match_threshold=0.5,
        )
        self.assertTrue(any(c.classification == "new-candidate" for c in candidates))
        hit = next(c for c in candidates if c.classification == "new-candidate")
        self.assertEqual(len({occ.file for occ in hit.occurrences}), 2)
        self.assertIsNotNone(hit.suggested_tag)

    def test_near_duplicate_reworded_chunk_detected(self):
        a = self._write(
            "A.md",
            "- Every acquired resource needs a matching release in the same logical scope.\n",
        )
        b = self._write(
            "B.md",
            "- Every resource acquisition needs a matching release in the same logical scope.\n",
        )
        candidates = tc.build_candidates(
            files=[a, b], core_tags={}, ngram=8, near_dup_threshold=0.7,
            min_words=6, tag_match_threshold=0.5,
        )
        self.assertTrue(any(c.signal == "near-duplicate" for c in candidates))

    def test_pattern_already_covered_by_existing_tag_is_flagged(self):
        existing_rule_text = "No var, all types must be declared explicitly everywhere in code"
        core_tags = {"EXPLICIT": existing_rule_text}
        a = self._write("A.md", f"- {existing_rule_text} today\n")
        b = self._write("B.md", f"- {existing_rule_text} today\n")
        candidates = tc.build_candidates(
            files=[a, b], core_tags=core_tags, ngram=8, near_dup_threshold=0.9,
            min_words=6, tag_match_threshold=0.3,
        )
        self.assertTrue(any(c.classification == "already-tagged" for c in candidates))
        hit = next(c for c in candidates if c.classification == "already-tagged")
        self.assertEqual(hit.matched_tag, "EXPLICIT")

    def test_no_duplicates_yields_empty_candidate_list(self):
        a = self._write("A.md", "- This passage appears only once and nowhere else at all.\n")
        b = self._write("B.md", "- A completely different sentence with no overlap whatsoever.\n")
        candidates = tc.build_candidates(
            files=[a, b], core_tags={}, ngram=8, near_dup_threshold=0.9,
            min_words=6, tag_match_threshold=0.5,
        )
        self.assertEqual(candidates, [])

    def test_parse_core_tags_table(self):
        core_tags_md = self._write(
            "CoreTags.md",
            "| Tag | Rule |\n|---|---|\n"
            "| **[EXPLICIT]** | No var — all types declared explicitly. |\n"
            "| **[ALLMAN]** | Allman braces — `{` always on its own new line. |\n",
        )
        tags = tc.parse_core_tags(core_tags_md)
        self.assertEqual(
            tags,
            {
                "EXPLICIT": "No var — all types declared explicitly.",
                "ALLMAN": "Allman braces — `{` always on its own new line.",
            },
        )

    def test_table_rows_chunk_at_their_own_line_not_the_table_start(self):
        repeated_row_1 = "No ServiceLocator.Instance — use constructor injection or LazyService today"
        repeated_row_2 = "Never cast to a concrete type inside a high level system today"
        core_tags_md = self._write(
            "CoreTags.md",
            "| Tag | Rule |\n|---|---|\n"
            f"| **[DI]** | {repeated_row_1} |\n"
            f"| **[IFACE]** | {repeated_row_2} |\n",
        )
        other_md = self._write(
            "Other.md",
            f"- {repeated_row_1}\n- {repeated_row_2}\n",
        )
        candidates = tc.build_candidates(
            files=[core_tags_md, other_md], core_tags={}, ngram=8, near_dup_threshold=0.9,
            min_words=6, tag_match_threshold=0.5,
        )
        di_hit = next(c for c in candidates if "servicelocator" in c.text.lower())
        iface_hit = next(c for c in candidates if "concrete type" in c.text.lower())
        di_line = next(occ.line for occ in di_hit.occurrences if occ.file == str(core_tags_md))
        iface_line = next(occ.line for occ in iface_hit.occurrences if occ.file == str(core_tags_md))
        self.assertEqual(di_line, 3)
        self.assertEqual(iface_line, 4)

    def test_render_markdown_no_candidates(self):
        markdown = tc.render_markdown([])
        self.assertIn("No repeated or near-duplicate", markdown)

    def test_tool_never_writes_to_scanned_files(self):
        repeated = "Every resource acquisition must have a matching release in the same scope today"
        a = self._write("A.md", f"- {repeated}\n")
        b = self._write("B.md", f"- {repeated}\n")
        before_a, before_b = a.read_text(), b.read_text()
        tc.build_candidates(
            files=[a, b], core_tags={}, ngram=8, near_dup_threshold=0.9,
            min_words=6, tag_match_threshold=0.5,
        )
        self.assertEqual(a.read_text(), before_a)
        self.assertEqual(b.read_text(), before_b)


if __name__ == "__main__":
    unittest.main()
