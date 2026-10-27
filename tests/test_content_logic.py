import subprocess
import unittest
from pathlib import Path


class ContentLogicTest(unittest.TestCase):
    def test_node_content_library_contract(self):
        repo = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ["node", "tests/content_library_node_test.js"],
            cwd=repo,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("content library node tests: ok", result.stdout)

    def test_node_wordbook_contract(self):
        repo = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ["node", "tests/wordbook_node_test.js"],
            cwd=repo,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("wordbook node tests: ok", result.stdout)

    def test_node_cantonese_contract(self):
        repo = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ["node", "tests/cantonese_node_test.js"],
            cwd=repo,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("cantonese node tests: ok", result.stdout)


if __name__ == "__main__":
    unittest.main()
