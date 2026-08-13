import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BACKEND_ROOT))

from app.agents.scorer import ReportScore, fallback_report_score, generate_report_score


class DummyModel:
    def __init__(self, response):
        self.response = response

    def invoke(self, prompt):
        return self.response


class ScorerTests(unittest.TestCase):
    def test_default_score_is_available(self) -> None:
        score = fallback_report_score()

        self.assertIsInstance(score, ReportScore)
        self.assertEqual(score.score, 60)
        self.assertEqual(score.dimension_scores["coverage"], 60)
        self.assertEqual(score.score_status, "fallback_scored")
        self.assertIsNotNone(score.score_error)

    def test_generate_report_score_parses_json_string(self) -> None:
        model = DummyModel(
            """{
                "score": 91,
                "dimension_scores": {
                    "coverage": 92,
                    "truthfulness": 90,
                    "structure": 91,
                    "actionability": 89,
                    "citation_quality": 93
                },
                "issues": [],
                "improvement_suggestions": [],
                "pass_or_fail": "pass",
                "score_status": "model_scored",
                "score_error": null,
                "score_raw": null
            }"""
        )

        score = generate_report_score(
            model=model,
            skill_prompt="skill",
            user_input="input",
            plan={"objective": "test"},
            evidence=[],
            report_markdown="# Report",
        )

        self.assertEqual(score.score, 91)
        self.assertEqual(score.score_status, "model_scored")
        self.assertIsNone(score.score_error)

    def test_generate_report_score_reports_parse_failure(self) -> None:
        model = DummyModel("not json")

        score = generate_report_score(
            model=model,
            skill_prompt="skill",
            user_input="input",
            plan={"objective": "test"},
            evidence=[],
            report_markdown="# Report",
        )

        self.assertEqual(score.score, 60)
        self.assertEqual(score.score_status, "fallback_scored")
        self.assertIsNotNone(score.score_error)
        self.assertIn("JSON", score.score_error or "")


if __name__ == "__main__":
    unittest.main()
