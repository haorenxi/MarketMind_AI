"""A provider-agnostic keyword search tool.

The tool is intentionally not wired into the current LangGraph workflow. A
future Research Agent can construct it and call ``search(keyword)`` directly.
"""

from collections.abc import Iterable
from typing import Protocol

from .models import SearchResult


class SearchToolError(RuntimeError):
    """Raised when a configured search provider cannot complete a request."""


class SearchProvider(Protocol):
    """Contract that all search provider adapters must follow."""

    def search(self, keyword: str, max_results: int) -> Iterable[SearchResult]:
        """Return normalized results for a non-empty keyword."""


class DuckDuckGoProvider:
    """Default provider backed by the optional ``ddgs`` package."""

    def search(self, keyword: str, max_results: int) -> Iterable[SearchResult]:
        try:
            from ddgs import DDGS
        except ImportError as error:
            raise SearchToolError(
                "Search dependency is missing. Install backend requirements first."
            ) from error

        try:
            raw_results = DDGS().text(keyword, max_results=max_results)
            return [
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("href", ""),
                    snippet=item.get("body", ""),
                    source="duckduckgo",
                )
                for item in raw_results
                if item.get("title") and item.get("href")
            ]
        except Exception as error:
            raise SearchToolError(f"Search provider request failed: {error}") from error


class ResearchTool:
    """Search the web by keyword through an injectable provider."""

    def __init__(self, provider: SearchProvider | None = None) -> None:
        self.provider = provider or DuckDuckGoProvider()

    def search(self, keyword: str, max_results: int = 5) -> list[SearchResult]:
        normalized_keyword = keyword.strip()
        if not normalized_keyword:
            raise ValueError("keyword must not be empty")
        if not 1 <= max_results <= 20:
            raise ValueError("max_results must be between 1 and 20")

        return list(self.provider.search(normalized_keyword, max_results))
