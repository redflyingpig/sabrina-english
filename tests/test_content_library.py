import hashlib
import json
import random
import re
import tempfile
import unittest
from pathlib import Path

from scripts.validate_content import normalize_identity, validate_library, write_manifest


REPO_CONTENT = Path(__file__).resolve().parents[1] / "content"
ALLOWED_TOPICS = {
    "daily-life",
    "family",
    "school",
    "work",
    "shopping",
    "food",
    "health",
    "transport",
    "travel",
    "weather",
    "home",
    "relationships",
    "entertainment",
    "digital-life",
    "public-services",
    "time",
    "nature",
}


class ContentLibraryTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.content_dir = Path(self.tempdir.name)
        self.minimums = {"vocabulary": 4, "expressions": 1, "patterns": 1}
        for level in ("a1", "a2", "b1", "b2"):
            self.write_json(
                f"vocabulary-{level}.json",
                [
                    {
                        "id": f"v1:{level}-word",
                        "level": level.upper(),
                        "topic": "daily-life",
                        "word": f"{level}word",
                        "phonetic": f"/{level}/",
                        "translation": f"{level} 释义",
                        "example": f"This is the {level} example.",
                    }
                ],
            )
        self.write_json(
            "expressions.json",
            [
                {
                    "id": "e1:take-care",
                    "level": "A2",
                    "topic": "relationships",
                    "expression": "Take care.",
                    "usage": "用于告别并表达关心。",
                    "example": "Take care and call me when you arrive.",
                }
            ],
        )
        self.write_json(
            "patterns.json",
            [
                {
                    "id": "p1:would-like",
                    "level": "A1",
                    "topic": "food",
                    "pattern": "I would like to + verb",
                    "explanation": "礼貌表达想做某事。",
                    "examples": ["I would like to order lunch."],
                }
            ],
        )
        write_manifest(self.content_dir, "test-v1")

    def tearDown(self):
        self.tempdir.cleanup()

    def write_json(self, name, payload):
        (self.content_dir / name).write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

    def read_json(self, name):
        return json.loads((self.content_dir / name).read_text(encoding="utf-8"))

    def rebuild_manifest(self):
        write_manifest(self.content_dir, "test-v1")

    def test_valid_library_and_manifest_contract(self):
        self.assertEqual("hello world", normalize_identity("  Hello—World!  "))
        self.assertEqual([], validate_library(self.content_dir, self.minimums))

        manifest = self.read_json("manifest.json")
        self.assertEqual("test-v1", manifest["version"])
        self.assertEqual(
            {"vocabulary": 4, "expressions": 1, "patterns": 1},
            manifest["counts"],
        )
        expected_files = {
            "vocabulary-a1.json",
            "vocabulary-a2.json",
            "vocabulary-b1.json",
            "vocabulary-b2.json",
            "expressions.json",
            "patterns.json",
        }
        self.assertEqual(expected_files, set(manifest["files"]))
        for filename, metadata in manifest["files"].items():
            digest = hashlib.sha256((self.content_dir / filename).read_bytes()).hexdigest()
            self.assertEqual(digest, metadata["sha256"])
            self.assertGreater(metadata["count"], 0)

    def test_reports_duplicate_ids_and_normalized_content(self):
        a2 = self.read_json("vocabulary-a2.json")
        a2[0]["id"] = "v1:a1-word"
        a2[0]["word"] = "A1WORD!"
        self.write_json("vocabulary-a2.json", a2)
        self.rebuild_manifest()

        errors = validate_library(self.content_dir, self.minimums)

        self.assertTrue(any("duplicate id v1:a1-word" in error for error in errors), errors)
        self.assertTrue(any("duplicate vocabulary a1word" in error for error in errors), errors)

    def test_reports_missing_fields_invalid_level_and_bad_examples(self):
        rows = self.read_json("vocabulary-a1.json")
        rows[0].pop("translation")
        rows[0]["level"] = "C1"
        rows[0]["example"] = ["not", "a", "string"]
        self.write_json("vocabulary-a1.json", rows)
        self.rebuild_manifest()

        errors = validate_library(self.content_dir, self.minimums)

        self.assertTrue(any("missing translation" in error for error in errors), errors)
        self.assertTrue(any("invalid level C1" in error for error in errors), errors)
        self.assertTrue(any("example must be a non-empty string" in error for error in errors), errors)

    def test_reports_non_string_pattern_examples(self):
        rows = self.read_json("patterns.json")
        rows[0]["examples"] = ["Good example.", 42]
        self.write_json("patterns.json", rows)
        self.rebuild_manifest()

        errors = validate_library(self.content_dir, self.minimums)

        self.assertTrue(any("examples must contain non-empty strings" in error for error in errors), errors)

    def test_reports_manifest_hash_mismatch(self):
        rows = self.read_json("expressions.json")
        rows[0]["usage"] = "内容在 manifest 生成后被修改。"
        self.write_json("expressions.json", rows)

        errors = validate_library(self.content_dir, self.minimums)

        self.assertTrue(any("sha256 mismatch for expressions.json" in error for error in errors), errors)

    def test_reports_counts_below_production_minimums(self):
        errors = validate_library(self.content_dir)

        self.assertTrue(any("vocabulary count 4 is below 4000" in error for error in errors), errors)
        self.assertTrue(any("expressions count 1 is below 600" in error for error in errors), errors)
        self.assertTrue(any("patterns count 1 is below 250" in error for error in errors), errors)


class ProductionContentTest(unittest.TestCase):
    @staticmethod
    def load(name):
        return json.loads((REPO_CONTENT / name).read_text(encoding="utf-8"))

    def test_production_library_meets_counts_and_level_distribution(self):
        shards = {
            level: self.load(f"vocabulary-{level.lower()}.json")
            for level in ("A1", "A2", "B1", "B2")
        }
        self.assertGreaterEqual(len(shards["A1"]), 800)
        self.assertGreaterEqual(len(shards["A2"]), 1200)
        self.assertGreaterEqual(len(shards["B1"]), 1200)
        self.assertGreaterEqual(len(shards["B2"]), 800)
        self.assertGreaterEqual(sum(map(len, shards.values())), 4000)
        self.assertGreaterEqual(len(self.load("expressions.json")), 600)
        self.assertGreaterEqual(len(self.load("patterns.json")), 250)
        self.assertEqual([], validate_library(REPO_CONTENT))

    def test_production_records_are_safe_complete_and_unique(self):
        rows = []
        for name in (
            "vocabulary-a1.json",
            "vocabulary-a2.json",
            "vocabulary-b1.json",
            "vocabulary-b2.json",
            "expressions.json",
            "patterns.json",
        ):
            rows.extend(self.load(name))
        self.assertEqual(len(rows), len({row["id"] for row in rows}))
        for row in rows:
            self.assertIn(row["level"], {"A1", "A2", "B1", "B2"})
            self.assertIn(row["topic"], ALLOWED_TOPICS)
            serialized = json.dumps(row, ensure_ascii=False)
            self.assertIsNone(re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", serialized))
            self.assertNotRegex(serialized, r"<\s*(script|iframe|object|embed)\b")

    def test_stratified_vocabulary_review_sample_has_learning_fields(self):
        for level in ("A1", "A2", "B1", "B2"):
            rows = self.load(f"vocabulary-{level.lower()}.json")
            sample = random.Random(f"sabrina-review-{level}").sample(rows, 25)
            self.assertEqual(25, len(sample))
            for row in sample:
                self.assertTrue(row["word"].strip())
                self.assertTrue(row["phonetic"].strip())
                self.assertTrue(row["translation"].strip())
                self.assertTrue(row["example"].strip())
                self.assertNotIn(r"\n", row["translation"])
                self.assertNotIn(r"\n", row["example"])
                self.assertNotRegex(row["translation"], r"男子名|女子名|人名|地名|国名")
                self.assertNotRegex(row["example"], r"\bmeans\s+[nvars]\.")

    def test_vocabulary_excludes_known_bad_entries_and_spelling_aliases(self):
        words = set()
        for level in ("A1", "A2", "B1", "B2"):
            words.update(row["word"] for row in self.load(f"vocabulary-{level.lower()}.json"))
        self.assertTrue({"bastard", "bullshit", "crap", "eric", "fuck", "fucked", "fucker", "fucking", "phil", "shit"}.isdisjoint(words))
        for left, right in (("color", "colour"), ("center", "centre"), ("labor", "labour"), ("organize", "organise")):
            self.assertFalse(left in words and right in words, (left, right))


if __name__ == "__main__":
    unittest.main()
