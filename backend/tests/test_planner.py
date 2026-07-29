import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BACKEND_ROOT))

from app.agents import ResearchPlan, generate_research_plan


class FakePlannerModel:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def with_structured_output(self, schema):
        self.calls.append(("with_structured_output", schema))
        return self

    def invoke(self, messages):
        self.calls.append(("invoke", messages))
        return ResearchPlan(
            objective="robot vision sensor market analysis",
            needs_web_research=True,
            steps=[
                {
                    "id": "market",
                    "topic": "market size",
                    "purpose": "collect market size information",
                    "search_queries": ["robot vision sensor market size"],
                    "required_evidence": ["market size"],
                    "priority": "high",
                }
            ],
            stop_conditions=["enough evidence collected"],
        )


class PlannerTests(unittest.TestCase):
    def test_generates_research_plan_for_robot_vision_sensor_market(self) -> None:
        model = FakePlannerModel()

        plan = generate_research_plan(model, "Analyze the robot vision sensor market", "skill prompt")

        self.assertEqual(plan.objective, "robot vision sensor market analysis")
        self.assertTrue(plan.needs_web_research)
        self.assertEqual(plan.steps[0].id, "market")
        self.assertEqual(plan.steps[0].priority, "high")
        self.assertGreaterEqual(len(model.calls), 2)

    def test_falls_back_to_default_plan_when_model_fails(self) -> None:
        class BrokenModel:
            def with_structured_output(self, schema):
                raise TimeoutError("planner timeout")

        plan = generate_research_plan(BrokenModel(), "Analyze the robot vision sensor market", "skill prompt")

        self.assertEqual(plan.objective, "comprehensive research")
        self.assertEqual(plan.steps[0].id, "general")
        self.assertTrue(plan.needs_web_research)


if __name__ == "__main__":
    unittest.main()
