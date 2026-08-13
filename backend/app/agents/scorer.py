"""Scoring helpers for the research report."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field


class ReportScore(BaseModel):
    """Structured score for a generated report."""

    score: int = Field(ge=0, le=100)
    dimension_scores: dict[str, int] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)
    pass_or_fail: str = "pass"
    score_status: str = "model_scored"
    score_error: str | None = None
    score_raw: str | None = None


DEFAULT_REPORT_SCORE = ReportScore(
    score=60,
    dimension_scores={
        "coverage": 60,
        "truthfulness": 60,
        "structure": 60,
        "actionability": 60,
        "citation_quality": 60,
    },
    issues=["scoring fallback used"],
    improvement_suggestions=["inspect the report output and the collected evidence"],
    pass_or_fail="pass",
    score_status="fallback_scored",
    score_error="scoring fallback used",
)


def build_scoring_prompt(
    skill_prompt: str,
    user_input: str,
    plan: dict[str, Any],
    evidence: list[dict[str, Any]],
    report_markdown: str,
) -> list[Any]:
    """Build a structured prompt for the scoring agent."""

    system_message = SystemMessage(
        content=(
            "You are the Scoring Agent. Evaluate the final markdown report and "
            "return only a valid JSON object that matches the provided schema. "
            "Do not output markdown, code fences, or free-form text.\n\n"
            "Required JSON keys:\n"
            '- "score": integer from 0 to 100\n'
            '- "dimension_scores": object with integer values\n'
            '- "issues": array of strings\n'
            '- "improvement_suggestions": array of strings\n'
            '- "pass_or_fail": string\n'
            '- "score_status": string\n'
            '- "score_error": string or null\n'
            '- "score_raw": string or null\n\n'
            "Score the report on coverage, truthfulness, structure, actionability, "
            "and citation quality."
        )
    )
    human_message = HumanMessage(
        content=(
            f"User request:\n{user_input}\n\n"
            f"Plan:\n{plan}\n\n"
            f"Evidence:\n{evidence}\n\n"
            f"Report:\n{report_markdown}\n\n"
            f"Skill prompt:\n{skill_prompt}"
        )
    )
    return [system_message, human_message]


def fallback_report_score() -> ReportScore:
    return DEFAULT_REPORT_SCORE.model_copy(deep=True)


def _stringify_payload(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


def _extract_json_payload(text: str) -> str | None:
    cleaned = text.strip()
    if not cleaned:
        return None

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        return cleaned[start : end + 1]
    return None


def _fallback_with_details(reason: str, raw: str | None = None) -> ReportScore:
    score = DEFAULT_REPORT_SCORE.model_copy(deep=True)
    score.score_error = reason
    score.score_raw = raw
    return score


def coerce_report_score(value: Any, raw_text: str | None = None, error: str | None = None) -> ReportScore:
    """Convert model output or raw payloads into a validated score object."""

    if isinstance(value, ReportScore):
        score = value.model_copy(deep=True)
        if raw_text and not score.score_raw:
            score.score_raw = raw_text
        if error and not score.score_error:
            score.score_error = error
        return score

    candidate: Any = value
    if hasattr(value, "model_dump"):
        candidate = value.model_dump()
    elif hasattr(value, "dict"):
        candidate = value.dict()
    elif isinstance(value, str):
        payload = _extract_json_payload(value)
        if payload is None:
            return _fallback_with_details(error or "score response was not valid JSON", raw=value)
        try:
            candidate = json.loads(payload)
        except json.JSONDecodeError as exc:
            return _fallback_with_details(error or f"score JSON parse failed: {exc}", raw=value)

    try:
        validated = ReportScore.model_validate(candidate)
        if raw_text and not validated.score_raw:
            validated.score_raw = raw_text
        if error and not validated.score_error:
            validated.score_error = error
        return validated
    except Exception as exc:
        raw_value = raw_text or _stringify_payload(value)
        return _fallback_with_details(error or f"score validation failed: {exc}", raw=raw_value)


def generate_report_score(
    model: Any,
    skill_prompt: str,
    user_input: str,
    plan: dict[str, Any],
    evidence: list[dict[str, Any]],
    report_markdown: str,
) -> ReportScore:
    """Generate a structured score with a safe fallback."""

    try:
        response = model.invoke(build_scoring_prompt(skill_prompt, user_input, plan, evidence, report_markdown))
        raw_text = str(getattr(response, "content", response))
        return coerce_report_score(raw_text, raw_text=raw_text)
    except Exception as exc:
        return _fallback_with_details(f"score generation failed: {exc}")
