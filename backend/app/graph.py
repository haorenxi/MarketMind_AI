"""Tool-aware LangGraph workflow for company research."""

from __future__ import annotations

import json
import os
import sys
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

# `tools/` is a project-level package, while the FastAPI app runs from
# `backend/`. Make the project root importable without changing the API entrypoint.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents import build_report_prompt, build_research_prompt, classify_task_type, extract_market_data, generate_research_plan
from app.agents import fallback_report_score, generate_report_score
from app.evidence import evidence_from_search_result, evidence_to_dict, unique_records_by_url
from app.market_data import MarketMetric, analyze_market_metrics, validate_market_data
from app.report_format import append_sources_appendix, build_fallback_markdown_report, normalize_markdown_report
from app.state import AgentState
from tools.search import ResearchTool, SearchResult, SearchToolError

from .skill_loader import SkillLoader

MAX_SEARCH_ROUNDS = int(os.getenv("MAX_SEARCH_ROUNDS", "3"))


def _build_model() -> ChatOpenAI:
    """Build the configured OpenAI-compatible chat model."""

    model_options = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        "temperature": 0,
        "timeout": 30,
        "max_retries": 1,
    }
    if base_url := os.getenv("OPENAI_BASE_URL"):
        model_options["base_url"] = base_url
    return ChatOpenAI(**model_options)


@tool("search_web")
def search_web(keyword: str) -> str:
    """Search the public web for current, externally verifiable research facts."""

    try:
        results = ResearchTool().search(keyword)
        return json.dumps([_serialize_result(result) for result in results], ensure_ascii=False)
    except SearchToolError as error:
        return json.dumps({"error": str(error), "keyword": keyword}, ensure_ascii=False)


def _serialize_result(result: SearchResult) -> dict[str, str]:
    return {
        "title": result.title,
        "url": result.url,
        "snippet": result.snippet,
        "source": result.source,
    }


def prepare_context_node(state: AgentState) -> AgentState:
    """Load the unchanged company-research skill and initialize workflow state."""

    task_id = state.get("task_id") or uuid.uuid4().hex
    skill = SkillLoader().load("company-research")
    task_type = str(state.get("task_type") or classify_task_type(state["user_input"]))
    research_type = str(state.get("research_type") or "comprehensive")
    return {
        "task_id": task_id,
        "skill_name": skill.name,
        "skill_prompt": skill.content,
        "task_type": task_type,
        "research_type": research_type,
        "messages": [HumanMessage(content=state["user_input"])],
        "completed_steps": [],
        "search_rounds": 0,
        "sources": [],
        "search_results": [],
        "evidence": [],
        "market_metrics": [],
        "calculated_metrics": [],
        "time_series": [],
        "competitors": [],
        "data_warnings": [],
        "errors": [],
    }


def _normalize_plan(plan: dict[str, Any] | None, fallback_step: str = "general") -> dict[str, Any]:
    if plan:
        return plan
    return {
        "objective": "comprehensive research",
        "needs_web_research": True,
        "steps": [
            {
                "id": fallback_step,
                "topic": "general analysis",
                "purpose": "collect externally verifiable information.",
                "search_queries": [],
                "required_evidence": [],
                "priority": "high",
            }
        ],
        "stop_conditions": ["enough evidence has been collected for a markdown report."],
    }


def _default_report(state: AgentState, reason: str) -> str:
    plan = _normalize_plan(state.get("plan"))
    evidence_context = list(state.get("evidence", [])) or list(state.get("search_results", []))
    title = plan.get("objective") or "comprehensive research"
    return build_fallback_markdown_report(title=title, reason=reason, evidence=evidence_context)


def _next_step_id(plan: dict[str, Any], completed_steps: list[str], current_step: str | None) -> str | None:
    ordered_steps = plan.get("steps", [])
    completed = set(completed_steps)
    if current_step:
        completed.add(current_step)
    for step in ordered_steps:
        step_id = str(step.get("id", "")).strip()
        if step_id and step_id not in completed:
            return step_id
    return None


def planner_node_factory(model: ChatOpenAI):
    """Create the planner node so tests can inject a fake model."""

    def planner_node(state: AgentState) -> AgentState:
        try:
            plan = generate_research_plan(
                model,
                state["user_input"],
                state["skill_prompt"],
                str(state.get("research_type") or "comprehensive"),
            )
            plan_dict = plan.model_dump()
            first_step = plan.steps[0].id if plan.steps else None
            return {
                "plan": plan_dict,
                "task_type": plan.task_type or classify_task_type(state["user_input"]),
                "current_step": first_step,
                "completed_steps": [],
            }
        except Exception as error:
            fallback_plan = _normalize_plan(None)
            return {
                "plan": fallback_plan,
                "task_type": classify_task_type(state["user_input"]),
                "current_step": fallback_plan["steps"][0]["id"],
                "completed_steps": [],
                "errors": [f"planner failed: {error}"],
            }

    return planner_node


def research_agent_node_factory(model: ChatOpenAI):
    """Create the executor node so tests can inject a fake model."""

    def research_agent_node(state: AgentState) -> AgentState:
        try:
            if int(state.get("search_rounds", 0) or 0) >= MAX_SEARCH_ROUNDS:
                return {
                    "messages": [
                        AIMessage(
                            content=(
                                "Search limit reached. I have enough context to draft the final report "
                                "without further tool calls."
                            )
                        )
                    ]
                }
            prompt = build_research_prompt(
                skill_prompt=state["skill_prompt"],
                user_input=state["user_input"],
                plan=_normalize_plan(state.get("plan")),
                current_step=state.get("current_step"),
                completed_steps=list(state.get("completed_steps", [])),
                evidence=list(state.get("evidence", [])),
            )
            response = model.bind_tools([search_web]).invoke(prompt)
            return {"messages": [response]}
        except Exception as error:
            fallback_report = _default_report(state, f"research executor failed: {error}")
            return {
                "messages": [AIMessage(content="Research executor failed and fell back to report mode.")],
                "research": fallback_report,
                "output": fallback_report,
                "errors": [f"research executor failed: {error}"],
            }

    return research_agent_node


def safe_research_tool_node(state: AgentState) -> AgentState:
    """Execute search tool calls defensively and return ToolMessages."""

    last_message = state["messages"][-1]
    tool_messages: list[ToolMessage] = []
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"messages": []}

    for tool_call in last_message.tool_calls:
        try:
            keyword = str((tool_call.get("args") or {}).get("keyword", "")).strip()
            result = search_web.invoke({"keyword": keyword})
            tool_messages.append(
                ToolMessage(
                    content=result,
                    tool_call_id=str(tool_call.get("id", "")),
                )
            )
        except Exception as error:
            tool_messages.append(
                ToolMessage(
                    content=json.dumps({"error": str(error), "keyword": tool_call.get("args", {})}, ensure_ascii=False),
                    tool_call_id=str(tool_call.get("id", "")),
                )
            )

    return {"messages": tool_messages}


def route_after_research(state: AgentState) -> Literal["research_tool", "metric_extractor"]:
    """Route to ToolNode only when the model requested a tool call."""

    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "research_tool"
    return "metric_extractor"


def route_after_evidence(state: AgentState) -> Literal["research_agent", "metric_extractor"]:
    """Stop the research loop once enough search rounds have been completed."""

    if int(state.get("search_rounds", 0) or 0) >= MAX_SEARCH_ROUNDS:
        return "metric_extractor"
    if not state.get("current_step"):
        return "metric_extractor"
    return "research_agent"


def metric_extractor_node_factory(model: ChatOpenAI):
    """Create structured numeric market data from collected evidence."""

    def metric_extractor_node(state: AgentState) -> AgentState:
        extraction = extract_market_data(
            model,
            state["user_input"],
            str(state.get("research_type") or "comprehensive"),
            list(state.get("evidence", [])),
        )
        return {
            "market_metrics": [item.model_dump() for item in extraction.metrics],
            "competitors": [item.model_dump() for item in extraction.competitors],
            "data_warnings": extraction.warnings,
        }

    return metric_extractor_node


def market_analysis_node(state: AgentState) -> AgentState:
    """Run deterministic calculations and prepare chart-ready data."""

    metrics: list[MarketMetric] = []
    warnings: list[str] = []
    for item in state.get("market_metrics", []):
        try:
            metrics.append(MarketMetric.model_validate(item))
        except Exception as error:
            warnings.append(f"忽略了一个无效市场指标: {error}")
    normalized, calculated, time_series, analysis_warnings = analyze_market_metrics(metrics)
    return {
        "market_metrics": [item.model_dump() for item in normalized],
        "calculated_metrics": [item.model_dump() for item in calculated],
        "time_series": [item.model_dump() for item in time_series],
        "data_warnings": warnings + analysis_warnings,
    }


def validation_agent_node(state: AgentState) -> AgentState:
    """Validate citations and declared applicability with explainable rules."""

    metrics = [MarketMetric.model_validate(item) for item in state.get("market_metrics", [])]
    result = validate_market_data(metrics, list(state.get("evidence", [])))
    return {"validation": result.model_dump(), "data_warnings": result.warnings}


def evidence_node(state: AgentState) -> AgentState:
    """Move fresh ToolNode results into report-ready, structured state."""

    try:
        recent_tool_messages: list[ToolMessage] = []
        for message in reversed(state["messages"]):
            if not isinstance(message, ToolMessage):
                break
            recent_tool_messages.append(message)

        existing_urls = {str(item.get("url", "")).strip() for item in state.get("search_results", [])}
        source_records: list[dict[str, Any]] = []
        evidence_records: list[dict[str, Any]] = []
        for message in reversed(recent_tool_messages):
            try:
                results = json.loads(str(message.content))
            except json.JSONDecodeError:
                continue
            if isinstance(results, dict) and results.get("error"):
                return {
                    "errors": [str(results.get("error"))],
                    "current_step": None,
                    "research": _default_report(state, str(results.get("error"))),
                    "output": _default_report(state, str(results.get("error"))),
                }
            if not isinstance(results, list):
                continue
            for result in results:
                if not isinstance(result, dict) or not result.get("url"):
                    continue
                url = str(result["url"]).strip()
                if not url or url in existing_urls:
                    continue
                existing_urls.add(url)
                source_record = {
                    "title": str(result.get("title", "")),
                    "url": url,
                    "snippet": str(result.get("snippet", "")),
                    "source": str(result.get("source", "")),
                }
                evidence_item = evidence_to_dict(
                    evidence_from_search_result(
                        {
                            "title": source_record["title"],
                            "url": source_record["url"],
                            "snippet": source_record["snippet"],
                            "source": source_record["source"],
                        }
                    )
                )
                source_records.append(source_record)
                evidence_records.append(evidence_item)

        plan = _normalize_plan(state.get("plan"))
        completed_steps = list(state.get("completed_steps", []))
        current_step = state.get("current_step")
        next_step = _next_step_id(plan, completed_steps, current_step)
        updates: AgentState = {
            "sources": unique_records_by_url(source_records),
            "search_results": unique_records_by_url(source_records),
            "evidence": evidence_records,
            "completed_steps": [current_step] if current_step else [],
            "current_step": next_step,
            "search_rounds": int(state.get("search_rounds", 0) or 0) + 1,
        }
        return updates
    except Exception as error:
        fallback = _default_report(state, f"evidence processing failed: {error}")
        return {
            "errors": [f"evidence processing failed: {error}"],
            "research": fallback,
            "output": fallback,
            "current_step": None,
        }


def report_node_factory(model: ChatOpenAI):
    """Create the report node so tests can inject a fake model."""

    def report_node(state: AgentState) -> AgentState:
        try:
            plan = _normalize_plan(state.get("plan"))
            evidence_context = list(state.get("evidence", [])) or list(state.get("search_results", []))
            sources_context = list(state.get("sources", [])) or list(state.get("search_results", []))
            prompt = build_report_prompt(
                skill_prompt=state["skill_prompt"],
                user_input=state["user_input"],
                plan=plan,
                evidence=evidence_context,
                sources=sources_context,
                task_type=str(state.get("task_type") or classify_task_type(state["user_input"])),
                market_data={
                    "metrics": state.get("market_metrics", []),
                    "calculated_metrics": state.get("calculated_metrics", []),
                    "time_series": state.get("time_series", []),
                    "competitors": state.get("competitors", []),
                    "warnings": state.get("data_warnings", []),
                },
            )
            response = model.invoke(prompt)
            report_markdown = normalize_markdown_report(str(response.content), title=plan.get("objective") or "Research Report")
            report_markdown = append_sources_appendix(report_markdown, sources_context)
            return {"research": report_markdown}
        except Exception as error:
            fallback = _default_report(state, f"report generation failed: {error}")
            return {
                "research": fallback,
                "output": fallback,
                "errors": [f"report generation failed: {error}"],
            }

    return report_node


def scorer_node_factory(model: ChatOpenAI):
    """Create the scoring node so the final report can be evaluated."""

    def scorer_node(state: AgentState) -> AgentState:
        try:
            score = generate_report_score(
                model,
                skill_prompt=state["skill_prompt"],
                user_input=state["user_input"],
                plan=_normalize_plan(state.get("plan")),
                evidence=list(state.get("evidence", [])) or list(state.get("search_results", [])),
                report_markdown=str(state.get("research", "")),
            )
            return {"score": score.model_dump()}
        except Exception as error:
            fallback_score = fallback_report_score().model_dump()
            fallback_score["issues"] = list(fallback_score.get("issues", [])) + [f"score generation failed: {error}"]
            return {"score": fallback_score, "errors": [f"score generation failed: {error}"]}

    return scorer_node


def output_node(state: AgentState) -> AgentState:
    """Preserve the existing API response contract."""

    return {"output": state["research"]}


def build_agent_graph(model: ChatOpenAI | None = None):
    graph_model = model or _build_model()
    workflow = StateGraph(AgentState)
    workflow.add_node("prepare_context", prepare_context_node)
    workflow.add_node("planner_node", planner_node_factory(graph_model))
    workflow.add_node("research_agent", research_agent_node_factory(graph_model))
    workflow.add_node("research_tool", safe_research_tool_node)
    workflow.add_node("evidence", evidence_node)
    workflow.add_node("metric_extractor", metric_extractor_node_factory(graph_model))
    workflow.add_node("market_analysis", market_analysis_node)
    workflow.add_node("report", report_node_factory(graph_model))
    workflow.add_node("validation_agent", validation_agent_node)
    workflow.add_node("scorer", scorer_node_factory(graph_model))
    workflow.add_node("output", output_node)
    workflow.add_edge(START, "prepare_context")
    workflow.add_edge("prepare_context", "planner_node")
    workflow.add_edge("planner_node", "research_agent")
    workflow.add_conditional_edges(
        "research_agent",
        route_after_research,
        {"research_tool": "research_tool", "metric_extractor": "metric_extractor"},
    )
    workflow.add_edge("research_tool", "evidence")
    workflow.add_conditional_edges(
        "evidence",
        route_after_evidence,
        {"research_agent": "research_agent", "metric_extractor": "metric_extractor"},
    )
    workflow.add_edge("metric_extractor", "market_analysis")
    workflow.add_edge("market_analysis", "report")
    workflow.add_edge("report", "validation_agent")
    workflow.add_edge("validation_agent", "scorer")
    workflow.add_edge("scorer", "output")
    workflow.add_edge("output", END)
    return workflow.compile()


agent_graph = build_agent_graph()
