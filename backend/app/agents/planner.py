"""Planner models and prompt builders for the research workflow."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    """One actionable research step produced by the planner."""

    id: str
    topic: str
    purpose: str
    search_queries: list[str] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)
    priority: str = "medium"


class ResearchPlan(BaseModel):
    """Structured research plan consumed by the executor."""

    objective: str
    needs_web_research: bool = True
    steps: list[PlanStep] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)


DEFAULT_RESEARCH_PLAN = ResearchPlan(
    objective="comprehensive research",
    needs_web_research=True,
    steps=[
        PlanStep(
            id="general",
            topic="general analysis",
            purpose="Collect market, brand, product, technology, review, and application signals.",
            search_queries=["comprehensive research"],
            required_evidence=["market size", "main brands", "popular products"],
            priority="high",
        )
    ],
    stop_conditions=["enough evidence has been collected to produce a markdown report."],
)


def build_default_research_plan(user_input: str | None = None) -> ResearchPlan:
    """Return the fallback plan used when structured planning fails."""

    if not user_input:
        return DEFAULT_RESEARCH_PLAN

    return ResearchPlan(
        objective="comprehensive research",
        needs_web_research=True,
        steps=[
            PlanStep(
                id="general",
                topic="general analysis",
                purpose="Collect externally verifiable information around the user topic.",
                search_queries=[user_input.strip()],
                required_evidence=["core market facts", "competitive landscape", "application direction"],
                priority="high",
            )
        ],
        stop_conditions=["enough evidence has been collected for a markdown report."],
    )


def build_planner_prompt(skill_prompt: str, user_input: str) -> list[Any]:
    """Create the structured planning prompt."""

    system_message = SystemMessage(
        content=(
            "You are the Planner Agent. Your job is to convert the user's request "
            "into a structured research plan. Return only structured data that "
            "matches the provided schema. Do not output markdown, analysis, or "
            "extra prose.\n\n"
            "The plan must be specific enough for a downstream executor to decide "
            "which searches to run and which evidence to collect.\n\n"
            "<skill name=\"company_research\">\n"
            f"{skill_prompt}\n"
            "</skill>"
        )
    )
    human_message = HumanMessage(
        content=(
            "Create a research plan for the following user request:\n"
            f"{user_input}"
        )
    )
    return [system_message, human_message]


def build_research_prompt(
    skill_prompt: str,
    user_input: str,
    plan: dict[str, Any],
    current_step: str | None,
    completed_steps: list[str],
    evidence: list[dict[str, Any]],
) -> list[Any]:
    """Create the execution prompt used by the research agent."""

    system_message = SystemMessage(
        content=(
            "You are the Research Executor. Follow the skill and the provided "
            "research plan. Decide whether external search is needed for the "
            "current step. Use the search_web tool only when it helps gather "
            "fresh or externally verifiable facts. Stop calling tools when the "
            "collected evidence is sufficient to draft the final report.\n\n"
            "Always consider the plan, the current step, the completed steps, and "
            "the evidence already collected.\n\n"
            "<skill name=\"company_research\">\n"
            f"{skill_prompt}\n"
            "</skill>\n\n"
            "<plan>\n"
            f"{json.dumps(plan, ensure_ascii=False)}\n"
            "</plan>\n\n"
            "<current_step>\n"
            f"{current_step or ''}\n"
            "</current_step>\n\n"
            "<completed_steps>\n"
            f"{json.dumps(completed_steps, ensure_ascii=False)}\n"
            "</completed_steps>\n\n"
            "<evidence>\n"
            f"{json.dumps(evidence, ensure_ascii=False)}\n"
            "</evidence>"
        )
    )
    human_message = HumanMessage(content=user_input)
    return [system_message, human_message]


def build_report_prompt(
    skill_prompt: str,
    user_input: str,
    plan: dict[str, Any],
    evidence: list[dict[str, Any]],
    sources: list[dict[str, Any]],
) -> list[Any]:
    """Create the Markdown report prompt."""

    system_message = SystemMessage(
        content=(
            "You are the Report Generator. Produce only the final answer in valid "
            "Markdown. Use the skill, the research plan, the collected evidence, "
            "and the raw sources to write a concise but complete market "
            "intelligence report. Cite URLs inline when making factual claims. "
            "Separate facts from inferences.\n\n"
            "<skill name=\"company_research\">\n"
            f"{skill_prompt}\n"
            "</skill>\n\n"
            "<plan>\n"
            f"{json.dumps(plan, ensure_ascii=False)}\n"
            "</plan>\n\n"
            "<evidence>\n"
            f"{json.dumps(evidence, ensure_ascii=False)}\n"
            "</evidence>\n\n"
            "<sources>\n"
            f"{json.dumps(sources, ensure_ascii=False)}\n"
            "</sources>"
        )
    )
    human_message = HumanMessage(content=user_input)
    return [system_message, human_message]


def coerce_research_plan(value: Any, user_input: str | None = None) -> ResearchPlan:
    """Convert a model response into a validated ``ResearchPlan``."""

    if isinstance(value, ResearchPlan):
        return value

    candidate: Any = value
    if hasattr(value, "model_dump"):
        candidate = value.model_dump()
    elif hasattr(value, "dict"):
        candidate = value.dict()
    elif isinstance(value, str):
        try:
            candidate = json.loads(value)
        except json.JSONDecodeError:
            return build_default_research_plan(user_input)

    try:
        return ResearchPlan.model_validate(candidate)
    except Exception:
        return build_default_research_plan(user_input)


def generate_research_plan(model: Any, user_input: str, skill_prompt: str) -> ResearchPlan:
    """Generate a structured plan with a safe fallback."""

    try:
        structured_model = model.with_structured_output(ResearchPlan)
        result = structured_model.invoke(build_planner_prompt(skill_prompt, user_input))
        return coerce_research_plan(result, user_input)
    except Exception:
        return build_default_research_plan(user_input)
