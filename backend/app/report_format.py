"""Markdown report formatting helpers."""

from __future__ import annotations

import re
from typing import Any


def normalize_markdown_report(text: str, title: str = "Research Report") -> str:
    """Clean up generated markdown so the UI receives a stable document."""

    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"<!--.*?-->", "", normalized, flags=re.S)
    normalized = re.sub(r"[ \t]+\n", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    if not normalized:
        return build_fallback_markdown_report(title=title, reason="empty report content", evidence=[])

    if not normalized.startswith("#"):
        normalized = f"# {title}\n\n{normalized}"

    if "## Facts" not in normalized and "## Analysis" not in normalized and "## Recommendations" not in normalized:
        normalized = _inject_three_layer_structure(normalized, title=title)

    return normalized


def _format_evidence_line(item: dict[str, Any]) -> str:
    evidence_title = str(item.get("title", "")).strip() or "Untitled"
    evidence_url = str(item.get("url", "")).strip()
    evidence_source = str(item.get("source", "")).strip()
    line = f"- {evidence_title}"
    if evidence_url:
        line += f" ([source]({evidence_url}))"
    if evidence_source:
        line += f" - {evidence_source}"
    return line


def _inject_three_layer_structure(text: str, title: str) -> str:
    body = text.split("\n\n", 1)[1] if "\n\n" in text else text
    return "\n".join(
        [
            f"# {title}",
            "",
            "## Facts",
            "",
            body.strip(),
            "",
            "## Analysis",
            "",
            "The report should include explicit trend interpretation grounded in the facts above.",
            "",
            "## Recommendations",
            "",
            "The report should include next-step actions grounded in the analysis above.",
        ]
    )


def build_sources_appendix(sources: list[dict[str, Any]]) -> str:
    """Build a Markdown appendix listing source URLs."""

    lines: list[str] = ["## Sources", ""]
    if not sources:
        lines.extend(["- No sources collected."])
        return "\n".join(lines)

    seen: set[str] = set()
    for item in sources:
        title = str(item.get("title", "")).strip() or "Untitled"
        url = str(item.get("url", "")).strip()
        source = str(item.get("source", "")).strip()
        if not url or url in seen:
            continue
        seen.add(url)
        line = f"- [{title}]({url})"
        if source:
            line += f" - {source}"
        lines.append(line)

    return "\n".join(lines)


def append_sources_appendix(report_markdown: str, sources: list[dict[str, Any]]) -> str:
    """Append a unique source list to the report if it is not already present."""

    appendix = build_sources_appendix(sources)
    if "## Sources" in report_markdown:
        return report_markdown
    return f"{report_markdown}\n\n{appendix}"


def build_fallback_markdown_report(
    title: str,
    reason: str,
    evidence: list[dict[str, Any]],
) -> str:
    """Build a consistent markdown fallback report."""

    evidence_lines: list[str] = []
    for item in evidence:
        evidence_lines.append(_format_evidence_line(item))

    if not evidence_lines:
        evidence_lines.append("- No evidence collected.")

    return "\n".join(
        [
            f"# {title}",
            "",
            "## Facts",
            "",
            "The report could not be fully generated, so this fallback version is returned to keep the API stable.",
            "",
            "## Analysis",
            "",
            "The fallback report could not produce a full analysis, so only evidence is listed here.",
            "",
            "## Recommendations",
            "",
            f"- Fallback reason: {reason}",
            "",
            "## Sources",
            "",
            *evidence_lines,
        ]
    )
