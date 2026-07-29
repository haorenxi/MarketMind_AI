"""Data structures returned by search providers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResult:
    """A normalized search result independent of the search provider."""

    title: str
    url: str
    snippet: str = ""
    source: str = "duckduckgo"
