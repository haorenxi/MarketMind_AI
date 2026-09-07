"""Structured market metric extraction from collected evidence."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.market_data import MarketExtraction


def build_market_extraction_prompt(
    user_input: str,
    research_type: str,
    evidence: list[dict[str, Any]],
) -> list[Any]:
    return [
        SystemMessage(
            content=(
                "You are a Market Data Extractor. Return structured data matching the schema. "
                "Extract only explicit numeric facts from the supplied evidence. Never estimate or invent values. "
                "For every metric preserve its source URL, title, excerpt, period, unit, geography, company or "
                "segment when stated. Use metric_name market_size for market-size observations and market_share "
                "for company shares. Mark forecasts explicitly. Confidence must be lower when evidence is only a "
                "search snippet or scope is incomplete. Add a warning for ambiguous units, periods or geography."
            )
        ),
        HumanMessage(
            content=(
                f"User request: {user_input}\n"
                f"Research type: {research_type}\n"
                f"Evidence: {json.dumps(evidence, ensure_ascii=False)}"
            )
        ),
    ]


def extract_market_data(
    model: Any,
    user_input: str,
    research_type: str,
    evidence: list[dict[str, Any]],
) -> MarketExtraction:
    """Extract market data with an empty, safe fallback."""

    if not evidence:
        return MarketExtraction(warnings=["没有可供结构化提取的搜索证据。"]) 
    try:
        structured_model = model.with_structured_output(MarketExtraction)
        value = structured_model.invoke(build_market_extraction_prompt(user_input, research_type, evidence))
        if isinstance(value, MarketExtraction):
            return value
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        return MarketExtraction.model_validate(value)
    except Exception as error:
        return MarketExtraction(warnings=[f"市场指标提取失败: {error}"])
