"""Shared LangGraph state for the research workflow."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """Mutable workflow state shared across all graph nodes."""

    task_id: str
    user_input: str
    skill_name: str
    skill_prompt: str
    plan: dict[str, Any]
    current_step: str | None
    completed_steps: Annotated[list[str], operator.add]
    messages: Annotated[list[AnyMessage], add_messages]
    sources: Annotated[list[dict[str, Any]], operator.add]
    search_results: Annotated[list[dict[str, Any]], operator.add]
    evidence: Annotated[list[dict[str, Any]], operator.add]
    errors: Annotated[list[str], operator.add]
    research: str
    output: str
