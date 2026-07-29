import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BACKEND_ROOT))

from app.agents import ResearchPlan
from app.graph import build_agent_graph


class FakeGraphModel:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def with_structured_output(self, schema):
        self.calls.append("planner")
        return self

    def bind_tools(self, tools):
        self.calls.append("research")
        return self

    def invoke(self, messages):
        from langchain_core.messages import AIMessage

        prompt_text = "\n".join(getattr(message, "content", "") for message in messages)
        if "Planner Agent" in prompt_text:
            return ResearchPlan(
                objective="robotics research",
                needs_web_research=True,
                steps=[
                    {
                        "id": "general",
                        "topic": "general analysis",
                        "purpose": "collect external facts",
                        "search_queries": ["robotics market"],
                        "required_evidence": ["market size"],
                        "priority": "high",
                    }
                ],
                stop_conditions=["complete"],
            )

        if "Research Executor" in prompt_text:
            return AIMessage(content="No search needed")

        if "Report Generator" in prompt_text:
            return AIMessage(content="# Report\n\nFinal report")

        return AIMessage(content="# Report\n\nFinal report")


class FlakyGraphModel:
    def __init__(self) -> None:
        self.report_calls = 0

    def with_structured_output(self, schema):
        return self

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        from langchain_core.messages import AIMessage

        prompt_text = "\n".join(getattr(message, "content", "") for message in messages)
        if "Planner Agent" in prompt_text:
            return ResearchPlan(
                objective="robotics research",
                needs_web_research=True,
                steps=[
                    {
                        "id": "general",
                        "topic": "general analysis",
                        "purpose": "collect external facts",
                        "search_queries": ["robotics market"],
                        "required_evidence": ["market size"],
                        "priority": "high",
                    }
                ],
                stop_conditions=["complete"],
            )

        if "Research Executor" in prompt_text:
            return AIMessage(content="No search needed")

        if "Report Generator" in prompt_text:
            self.report_calls += 1
            if self.report_calls >= 2:
                raise RuntimeError("report model failed on second call")
            return AIMessage(content="# Report\n\nFirst report")

        return AIMessage(content="# Report\n\nFallback report")


class GraphFlowTests(unittest.TestCase):
    def test_graph_connects_prepare_planner_research_report(self) -> None:
        graph = build_agent_graph(FakeGraphModel())

        result = graph.invoke({"user_input": "Analyze the robot vision sensor market"})

        self.assertIn("output", result)
        self.assertIn("research", result)
        self.assertEqual(result["output"], result["research"])

    def test_graph_recovers_on_second_call_failure(self) -> None:
        graph = build_agent_graph(FlakyGraphModel())

        first = graph.invoke({"user_input": "Analyze the robot vision sensor market"})
        second = graph.invoke({"user_input": "Analyze the robot vision sensor market"})

        self.assertIn("output", first)
        self.assertIn("output", second)
        self.assertTrue(second["output"])


if __name__ == "__main__":
    unittest.main()
