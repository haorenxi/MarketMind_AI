import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BACKEND_ROOT))

from app.market_data import MarketMetric, analyze_market_metrics, calculate_cagr, validate_market_data


class MarketDataTests(unittest.TestCase):
    def test_calculates_cagr_deterministically(self) -> None:
        self.assertAlmostEqual(calculate_cagr(10, 15, 3), 14.4714, places=3)

    def test_builds_time_series_and_calculated_cagr(self) -> None:
        metrics = [
            MarketMetric(
                metric_name="market_size", value=10, unit="billion", currency="USD",
                geography="Global", period="2022", source_url="https://example.com/a",
            ),
            MarketMetric(
                metric_name="market_size", value=15, unit="billion", currency="USD",
                geography="Global", period="2025", source_url="https://example.com/b",
            ),
        ]

        normalized, calculated, time_series, _warnings = analyze_market_metrics(metrics)

        self.assertEqual(len(normalized), 2)
        self.assertEqual([point.period for point in time_series], ["2022", "2025"])
        self.assertEqual(calculated[0].metric_name, "cagr")
        self.assertAlmostEqual(calculated[0].value, 14.47, places=2)

    def test_validation_exposes_citation_and_scope_limits(self) -> None:
        metric = MarketMetric(
            metric_name="market_size", value=12, unit="billion", currency="USD",
            geography="Global", period="2025", source_url="https://example.com/a",
            confidence=0.7,
        )

        validation = validate_market_data(
            [metric],
            [{"url": "https://example.com/a", "content": "The market reached USD 12 billion in 2025."}],
        )

        self.assertEqual(validation.citation_coverage, 1)
        self.assertEqual(validation.applicability_score, 100)
        self.assertEqual(validation.cross_source_rate, 0)
        self.assertEqual(validation.status, "warning")
        self.assertIn("两个独立来源", validation.claims[0].issues[0])


if __name__ == "__main__":
    unittest.main()
