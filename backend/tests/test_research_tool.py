import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from tools.search import ResearchTool, SearchResult, SearchToolError


class FakeSearchProvider:
    def __init__(self, results: list[SearchResult] | None = None) -> None:
        self.results = results or []
        self.calls: list[tuple[str, int]] = []

    def search(self, keyword: str, max_results: int) -> list[SearchResult]:
        self.calls.append((keyword, max_results))
        return self.results


class FailingSearchProvider:
    def search(self, keyword: str, max_results: int) -> list[SearchResult]:
        raise SearchToolError("provider unavailable")


class ResearchToolTests(unittest.TestCase):
    def test_returns_normalized_search_results(self) -> None:
        expected = [
            SearchResult(
                title="Example result",
                url="https://example.com/article",
                snippet="A result summary.",
                source="test",
            )
        ]
        provider = FakeSearchProvider(expected)

        results = ResearchTool(provider).search(" robotics ", max_results=3)

        self.assertEqual(results, expected)
        self.assertEqual(provider.calls, [("robotics", 3)])

    def test_rejects_empty_keywords(self) -> None:
        with self.assertRaises(ValueError):
            ResearchTool(FakeSearchProvider()).search("  ")

    def test_rejects_invalid_result_limit(self) -> None:
        with self.assertRaises(ValueError):
            ResearchTool(FakeSearchProvider()).search("robotics", max_results=21)

    def test_preserves_provider_error(self) -> None:
        with self.assertRaisesRegex(SearchToolError, "provider unavailable"):
            ResearchTool(FailingSearchProvider()).search("robotics")


if __name__ == "__main__":
    unittest.main()
