"""Repeatable black-box evaluation runner for the market research API."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path
from statistics import mean


def post_json(url: str, payload: dict, timeout: int) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def evaluate_case(case: dict, response: dict, latency: float) -> dict:
    validation = response.get("validation") or {}
    metrics = response.get("metrics") or []
    competitors = response.get("competitors") or []
    checks = {
        "has_report": bool(response.get("answer")),
        "research_type_matches": response.get("research_type") == case["research_type"],
        "minimum_metrics": len(metrics) >= case.get("minimum_metrics", 0),
        "minimum_competitors": len(competitors) >= case.get("minimum_competitors", 0),
        "has_validation": bool(validation),
    }
    return {
        "id": case["id"],
        "passed": all(checks.values()),
        "checks": checks,
        "accuracy_score": validation.get("accuracy_score", 0),
        "applicability_score": validation.get("applicability_score", 0),
        "citation_coverage": validation.get("citation_coverage", 0),
        "cross_source_rate": validation.get("cross_source_rate", 0),
        "latency_seconds": round(latency, 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/agent")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    cases_path = Path(__file__).with_name("cases.jsonl")
    cases = [json.loads(line) for line in cases_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    results: list[dict] = []
    for run in range(args.runs):
        for case in cases:
            started = time.perf_counter()
            try:
                response = post_json(
                    args.url,
                    {"message": case["message"], "research_type": case["research_type"]},
                    args.timeout,
                )
                result = evaluate_case(case, response, time.perf_counter() - started)
            except Exception as error:
                result = {"id": case["id"], "passed": False, "error": str(error), "latency_seconds": round(time.perf_counter() - started, 2)}
            result["run"] = run + 1
            results.append(result)

    scored = [item for item in results if "accuracy_score" in item]
    summary = {
        "runs": args.runs,
        "case_executions": len(results),
        "pass_rate": round(sum(item["passed"] for item in results) / max(len(results), 1), 3),
        "average_accuracy": round(mean(item["accuracy_score"] for item in scored), 2) if scored else 0,
        "average_applicability": round(mean(item["applicability_score"] for item in scored), 2) if scored else 0,
        "average_citation_coverage": round(mean(item["citation_coverage"] for item in scored), 3) if scored else 0,
        "average_cross_source_rate": round(mean(item["cross_source_rate"] for item in scored), 3) if scored else 0,
        "average_latency_seconds": round(mean(item["latency_seconds"] for item in results), 2) if results else 0,
    }
    print(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
