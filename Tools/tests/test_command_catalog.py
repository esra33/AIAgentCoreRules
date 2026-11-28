"""The catalog, dispatcher and README expose the same public command map."""
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import command_catalog  # noqa: E402


class CommandCatalogTests(unittest.TestCase):
    def test_routes_targets_and_readme_match_help(self):
        subprocess.run([sys.executable, "-B", str(TOOLS / "command_catalog.py"), "verify"], check=True)
        help_text = subprocess.check_output(["bash", str(TOOLS / "tools.sh"), "-h"], text=True)
        readme = (TOOLS / "README.md").read_text()
        rows = "\n".join(command_catalog.rows())
        self.assertIn(rows, help_text)
        self.assertIn(rows, readme)
        for retired in ("unity", "unitysource", "cslint", "feature-state", "link-diagram-tasks",
                        "session-lifecycle", "session-support", "mermaid-preview",
                        "migrate-phase-reports", "backfill-diagrams"):
            self.assertNotIn(retired, rows)
        for domain, method, kind, target, *_ in command_catalog.ROUTES:
            route = subprocess.check_output([sys.executable, "-B", str(TOOLS / "command_catalog.py"),
                                             "route", domain, method,
                                             "preview" if method == "doc-review" else ""], text=True).strip()
            self.assertEqual(route, kind + "\t" + target)

    def test_public_dispatch_rejects_internal_methods_and_review_subcommands(self):
        for arguments in (("features", "feature-state", "list"),
                          ("sessions", "session-support", "history"),
                          ("code", "unity", "index", "status"),
                          ("code", "unitysource", "status"),
                          ("code", "cslint", "-h"),
                          ("documents", "doc-review", "comments", "Doc.md"),
                          ("documents", "doc-review", "serve", "Doc.md")):
            with self.subTest(arguments=arguments):
                result = subprocess.run(["bash", str(TOOLS / "tools.sh"), *arguments],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
        help_text = subprocess.check_output(["bash", str(TOOLS / "tools.sh"),
                                             "documents", "doc-review", "-h"], text=True)
        self.assertIn("preview", help_text)
        self.assertIn("servers", help_text)
        self.assertNotIn("comments", help_text)


if __name__ == "__main__":
    unittest.main()
