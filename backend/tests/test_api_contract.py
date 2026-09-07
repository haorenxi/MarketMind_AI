import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BACKEND_ROOT))

from app import main as app_main


class FakeAgentGraph:
    payload = None

    def invoke(self, payload):
        self.payload = payload
        return {
            "output": "markdown report",
            "research": "markdown report",
            "score": {
                "score": 88,
                "dimension_scores": {"coverage": 90},
                "issues": [],
                "improvement_suggestions": [],
                "pass_or_fail": "pass",
            },
        }


class ApiContractTests(unittest.TestCase):
    def test_api_response_shape_is_unchanged(self) -> None:
        original_graph = app_main.agent_graph
        fake_graph = FakeAgentGraph()
        app_main.agent_graph = fake_graph
        try:
            client = TestClient(app_main.app)
            response = client.post(
                "/api/agent",
                json={"message": "Analyze the robot vision sensor market", "research_type": "market_size"},
            )
        finally:
            app_main.agent_graph = original_graph

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["answer"], "markdown report")
        self.assertEqual(payload["research_type"], "market_size")
        self.assertEqual(payload["metrics"], [])
        self.assertEqual(payload["warnings"], [])
        self.assertEqual(fake_graph.payload["research_type"], "market_size")


if __name__ == "__main__":
    unittest.main()
