from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.pipeline import TestEngineerPipeline

DATASET_PATH = ROOT / "evaluation" / "dataset.json"


def main() -> None:
    os.environ.setdefault("AI_COPILOT_DISABLE_LLM", "1")
    try:
        from deepeval import evaluate
        from deepeval.metrics import AnswerRelevancyMetric, GEval
        from deepeval.test_case import LLMTestCase, LLMTestCaseParams
    except ImportError as exc:
        raise SystemExit("Install optional dependencies first: pip install -r requirements-optional.txt") from exc

    pipeline = TestEngineerPipeline()
    test_cases = []
    for case in json.loads(DATASET_PATH.read_text(encoding="utf-8")):
        result = pipeline.analyze(case["spec"], case["logs"])
        expected = case["expected"]
        test_cases.append(
            LLMTestCase(
                input=case["logs"],
                actual_output=result.log_analysis.root_cause,
                expected_output=expected["root_cause_signature"],
                retrieval_context=[ref.snippet for ref in result.log_analysis.source_refs],
            )
        )

    domain_correctness = GEval(
        name="Root Cause Correctness",
        criteria="Score whether the predicted root cause is consistent with the expected failure signature and log evidence.",
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
    )
    metrics = [AnswerRelevancyMetric(), domain_correctness]
    evaluate(test_cases=test_cases, metrics=metrics)


if __name__ == "__main__":
    main()
