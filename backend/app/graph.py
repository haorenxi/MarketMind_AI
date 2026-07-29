"""Tool-aware LangGraph workflow for company research."""

from __future__ import annotations

import json
import os
import sys
import uuid
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

from app.agents import build_report_prompt, build_research_prompt, generate_research_plan
from app.evidence import evidence_from_search_result, evidence_to_dict, unique_records_by_url
from app.state import AgentState
from tools.search import ResearchTool, SearchResult, SearchToolError

from .skill_loader import SkillLoader


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
    skill = SkillLoader().load("company_research")
    return {
        "task_id": task_id,
        "skill_name": skill.name,
        "skill_prompt": skill.content,
        "messages": [HumanMessage(content=state["user_input"])],
        "completed_steps": [],
        "sources": [],
        "search_results": [],
        "evidence": [],
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
    evidence_summary = json.dumps(evidence_context, ensure_ascii=False, indent=2)
    error_block = f"\n\n> Fallback reason: {reason}" if reason else ""
    return (
        f"# {title}\n\n"
        "The report generator could not complete the full LLM drafting step, so "
        "this fallback report is being returned to keep the API stable.\n\n"
        "## Evidence\n\n"
        f"```json\n{evidence_summary}\n```"
        f"{error_block}"
    )


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
            plan = generate_research_plan(model, state["user_input"], state["skill_prompt"])
            plan_dict = plan.model_dump()
            first_step = plan.steps[0].id if plan.steps else None
            return {
                "plan": plan_dict,
                "current_step": first_step,
                "completed_steps": [],
            }
        except Exception as error:
            fallback_plan = _normalize_plan(None)
            return {
                "plan": fallback_plan,
                "current_step": fallback_plan["steps"][0]["id"],
                "completed_steps": [],
                "errors": [f"planner failed: {error}"],
            }

    return planner_node


def research_agent_node_factory(model: ChatOpenAI):
    """Create the executor node so tests can inject a fake model."""

    def research_agent_node(state: AgentState) -> AgentState:
        try:
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


def route_after_research(state: AgentState) -> Literal["research_tool", "report"]:
    """Route to ToolNode only when the model requested a tool call."""

    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "research_tool"
    return "report"


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
            )
            response = model.invoke(prompt)
            return {"research": str(response.content)}
        except Exception as error:
            fallback = _default_report(state, f"report generation failed: {error}")
            return {
                "research": fallback,
                "output": fallback,
                "errors": [f"report generation failed: {error}"],
            }

    return report_node


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
    workflow.add_node("report", report_node_factory(graph_model))
    workflow.add_node("output", output_node)
    workflow.add_edge(START, "prepare_context")
    workflow.add_edge("prepare_context", "planner_node")
    workflow.add_edge("planner_node", "research_agent")
    workflow.add_conditional_edges(
        "research_agent",
        route_after_research,
        {"research_tool": "research_tool", "report": "report"},
    )
    workflow.add_edge("research_tool", "evidence")
    workflow.add_edge("evidence", "research_agent")
    workflow.add_edge("report", "output")
    workflow.add_edge("output", END)
    return workflow.compile()


agent_graph = build_agent_graph()
