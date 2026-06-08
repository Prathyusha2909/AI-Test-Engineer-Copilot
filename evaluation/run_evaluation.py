from __future__ import annotations

import csv
import json
import os
import sys
from datetime import date
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.pipeline import TestEngineerPipeline

DATASET_PATH = ROOT / "evaluation" / "dataset.json"
RESULTS_PATH = ROOT / "evaluation" / "results.csv"
SUMMARY_PATH = ROOT / "evaluation" / "summary.json"
REPORT_PATH = ROOT / "docs" / "benchmark_report.md"


def main() -> None:
    os.environ.setdefault("AI_COPILOT_DISABLE_LLM", "1")
    cases = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    pipeline = TestEngineerPipeline()
    rows = [evaluate_case(pipeline, case) for case in cases]
    summary = summarize(rows)
    write_results(rows)
    write_summary(summary)
    write_report(summary, rows)
    print(json.dumps(summary, indent=2))


def evaluate_case(pipeline: TestEngineerPipeline, case: dict[str, Any]) -> dict[str, Any]:
    result = pipeline.analyze(case["spec"], case["logs"])
    expected = case["expected"]
    predicted_root = result.log_analysis.root_cause
    expected_signature = expected["root_cause_signature"].lower()
    root_match = expected_signature in predicted_root.lower()

    predicted_components = set(result.log_analysis.affected_components)
    expected_components = set(expected["components"])
    component_precision = safe_divide(len(predicted_components & expected_components), len(predicted_components))
    component_recall = safe_divide(len(predicted_components & expected_components), len(expected_components))

    generated_titles = {item.title for item in result.test_plan}
    required_titles = set(expected["required_tests"])
    test_plan_coverage = safe_divide(len(generated_titles & required_titles), len(required_titles))

    evidence_text = " ".join(item.message.lower() for item in result.log_analysis.evidence)
    evidence_terms = [term.lower() for term in expected["evidence_terms"]]
    evidence_recall = safe_divide(sum(1 for term in evidence_terms if term in evidence_text), len(evidence_terms))

    return {
        "case_id": case["id"],
        "description": case["description"],
        "expected_root_signature": expected["root_cause_signature"],
        "predicted_root_cause": predicted_root,
        "root_cause_accuracy": int(root_match),
        "component_precision": round(component_precision, 4),
        "component_recall": round(component_recall, 4),
        "test_plan_coverage": round(test_plan_coverage, 4),
        "evidence_recall": round(evidence_recall, 4),
        "overall_score": round(
            mean([int(root_match), component_precision, component_recall, test_plan_coverage, evidence_recall]),
            4,
        ),
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = [
        "root_cause_accuracy",
        "component_precision",
        "component_recall",
        "test_plan_coverage",
        "evidence_recall",
        "overall_score",
    ]
    summary = {
        "generated_on": date.today().isoformat(),
        "case_count": len(rows),
    }
    for metric in metrics:
        summary[metric] = round(mean(float(row[metric]) for row in rows), 4)
    return summary


def write_results(rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "case_id",
        "description",
        "expected_root_signature",
        "predicted_root_cause",
        "root_cause_accuracy",
        "component_precision",
        "component_recall",
        "test_plan_coverage",
        "evidence_recall",
        "overall_score",
    ]
    with RESULTS_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(summary: dict[str, Any]) -> None:
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def write_report(summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    report = [
        "# Benchmark Report",
        "",
        f"Generated on: {summary['generated_on']}",
        "",
        "## Dataset",
        "",
        f"- Cases: {summary['case_count']}",
        "- Domain: hardware/software validation logs for network-card style systems",
        "- Coverage: PCIe/DMA, packet buffers, firmware recovery, PHY signal integrity, thermal stress, power rail faults, and an ambiguous mixed-fault case",
        "",
        "## Metrics",
        "",
        "| Metric | Score |",
        "| --- | ---: |",
        f"| Root Cause Accuracy | {percent(summary['root_cause_accuracy'])} |",
        f"| Root Cause Precision | {percent(summary['component_precision'])} |",
        f"| Root Cause Recall | {percent(summary['component_recall'])} |",
        f"| Test Plan Coverage | {percent(summary['test_plan_coverage'])} |",
        f"| Evidence Recall | {percent(summary['evidence_recall'])} |",
        f"| Overall Score | {percent(summary['overall_score'])} |",
        "",
        "## Per-Case Results",
        "",
        "| Case | Expected Signature | Predicted Root Cause | Score |",
        "| --- | --- | --- | ---: |",
    ]
    for row in rows:
        report.append(
            f"| {row['case_id']} | {row['expected_root_signature']} | "
            f"{row['predicted_root_cause']} | {percent(float(row['overall_score']))} |"
        )

    report.extend(
        [
            "",
            "## Notes",
            "",
            "- The benchmark is deterministic and can run without API keys.",
            "- The ambiguous mixed thermal/power case is intentionally included so the score is not artificially perfect.",
            "- DeepEval and Ragas adapters are included for LLM-as-judge and RAG-specific evaluation when optional dependencies and model keys are available.",
        ]
    )
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def percent(value: float) -> str:
    return f"{round(value * 100)}%"


def safe_divide(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


if __name__ == "__main__":
    main()
