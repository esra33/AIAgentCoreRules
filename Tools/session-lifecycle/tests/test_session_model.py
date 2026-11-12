"""main_model(): the session's main model, recorded at compile for per-phase model reviews."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import session_lifecycle as lifecycle


class MainModelTests(unittest.TestCase):

    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".jsonl")
        os.close(handle)

    def tearDown(self):
        os.remove(self.path)

    def write(self, entries):
        with open(self.path, "w") as handle:
            for entry in entries:
                handle.write((entry if isinstance(entry, str) else json.dumps(entry)) + "\n")

    def assistant(self, model):
        return {"type": "assistant", "message": {"role": "assistant", "model": model, "content": []}}

    def test_most_frequent_model_wins(self):
        self.write([self.assistant("claude-haiku-4-5"), self.assistant("claude-sonnet-5"),
                    self.assistant("claude-sonnet-5")])
        self.assertEqual(lifecycle.main_model(self.path), "claude-sonnet-5")

    def test_synthetic_messages_and_bad_lines_are_ignored(self):
        self.write(["{not json \"model\"", {"type": "user", "message": "text with \"model\""},
                    self.assistant("<synthetic>"), self.assistant("<synthetic>"),
                    self.assistant("claude-opus-5-5")])
        self.assertEqual(lifecycle.main_model(self.path), "claude-opus-5-5")

    def test_no_model_or_missing_transcript_gives_none(self):
        self.write([{"type": "user", "message": {"role": "user", "content": "hi"}}])
        self.assertIsNone(lifecycle.main_model(self.path))
        self.assertIsNone(lifecycle.main_model(None))
        self.assertIsNone(lifecycle.main_model(self.path + ".missing"))


if __name__ == "__main__":
    unittest.main()
