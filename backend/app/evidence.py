"""Evidence data structures and normalization helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class Evidence:
    """A single verifiable fact extracted from research output."""

    source: str
    url: str
    title: str
    content: str
    confidence: float = 0.5


def evidence_from_search_result(result: dict[str, Any]) -> Evidence:
    """Convert a normalized search result dictionary into structured evidence."""

    return Evidence(
        source=str(result.get("source", "")),
        url=str(result.get("url", "")),
        title=str(result.get("title", "")),
        content=str(result.get("snippet", "")),
        confidence=float(result.get("confidence", 0.5)),
    )


def evidence_to_dict(item: Evidence) -> dict[str, Any]:
    """Serialize evidence for state storage and prompt context."""

    return asdict(item)


def unique_records_by_url(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate records while preserving the first observation for each URL."""

    seen: set[str] = set()
    unique_records: list[dict[str, Any]] = []
    for record in records:
        url = str(record.get("url", "")).strip()
        if not url or url in seen:
            continue
        seen.add(url)
        unique_records.append(record)
    return unique_records
