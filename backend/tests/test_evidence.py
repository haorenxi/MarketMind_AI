import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BACKEND_ROOT))

from app.evidence import Evidence, evidence_from_search_result, evidence_to_dict, unique_records_by_url


class EvidenceTests(unittest.TestCase):
    def test_normalizes_search_result_into_evidence(self) -> None:
        evidence = evidence_from_search_result(
            {
                "source": "duckduckgo",
                "url": "https://example.com",
                "title": "Example",
                "snippet": "A sample snippet.",
                "confidence": 0.8,
            }
        )

        self.assertEqual(evidence, Evidence("duckduckgo", "https://example.com", "Example", "A sample snippet.", 0.8))
        self.assertEqual(evidence_to_dict(evidence)["url"], "https://example.com")

    def test_deduplicates_records_by_url(self) -> None:
        records = [
            {"url": "https://example.com/a", "title": "A"},
            {"url": "https://example.com/a", "title": "A duplicate"},
            {"url": "https://example.com/b", "title": "B"},
        ]

        unique_records = unique_records_by_url(records)

        self.assertEqual(len(unique_records), 2)
        self.assertEqual(unique_records[0]["title"], "A")


if __name__ == "__main__":
    unittest.main()
