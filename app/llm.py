from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from app.domain import DebugSession, LLMInsight, LogFinding, MCPObservation, RiskSignal, TestCase


SYSTEM_PROMPT = """You are an expert AI test engineer for hardware/software validation.
Review the deterministic analysis and produce a concise engineering review.
Focus on PCIe, DMA, firmware, packet buffers, PHY/link behavior, thermal/power, reproducibility, and next tests.
Do not invent evidence. If evidence is weak, say what instrumentation is missing."""


REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "executive_summary": {"type": "string"},
        "root_cause_rationale": {"type": "string"},
        "additional_tests": {
            "type": "array",
            "items": {"type": "string"},
        },
        "recommended_fix_order": {
            "type": "array",
            "items": {"type": "string"},
        },
        "confidence_note": {"type": "string"},
    },
    "required": [
        "executive_summary",
        "root_cause_rationale",
        "additional_tests",
        "recommended_fix_order",
        "confidence_note",
    ],
    "additionalProperties": False,
}


@dataclass
class LLMConfig:
    provider: str
    model: str
    api_key: str
    disabled: bool = False

    @classmethod
    def from_env(cls) -> "LLMConfig":
        disabled = os.environ.get("AI_COPILOT_DISABLE_LLM", "").lower() in {"1", "true", "yes"}
        provider = os.environ.get("LLM_PROVIDER", "openai").lower()
        if provider in {"gemini", "google"}:
            model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
            api_key = os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))
        else:
            model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
            api_key = os.environ.get("OPENAI_API_KEY", "")
        return cls(
            provider=provider,
            model=model,
            api_key=api_key,
            disabled=disabled,
        )


class LLMReviewer:
    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig.from_env()

    def run(
        self,
        test_plan: list[TestCase],
        predictions: list[RiskSignal],
        log_finding: LogFinding,
        observations: list[MCPObservation],
        debugging: DebugSession,
    ) -> LLMInsight:
        if self.config.disabled:
            return disabled_insight(self.config, "LLM disabled by AI_COPILOT_DISABLE_LLM.")

        provider = self.config.provider.lower()
        if provider not in {"openai", "gemini", "google"}:
            return disabled_insight(self.config, f"Unsupported LLM provider: {self.config.provider}.")

        if not self.config.api_key:
            key_name = "OPENAI_API_KEY" if provider == "openai" else "GEMINI_API_KEY"
            return disabled_insight(self.config, f"Set {key_name} to enable the LLM engineering review.")

        payload = build_review_payload(test_plan, predictions, log_finding, observations, debugging)

        if provider == "openai":
            return self._run_openai(payload)
        return self._run_gemini(payload)

    def _run_openai(self, payload: dict[str, Any]) -> LLMInsight:
        try:
            from openai import OpenAI
        except ImportError:
            return disabled_insight(self.config, "Install the openai package to enable the OpenAI LLM layer.")

        try:
            client = OpenAI(api_key=self.config.api_key)
            response = client.responses.create(
                model=self.config.model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": "Return a JSON engineering review for this validation analysis:\n"
                        + json.dumps(payload, indent=2),
                    },
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "engineering_review",
                        "schema": REVIEW_SCHEMA,
                        "strict": True,
                    }
                },
            )
            raw_text = extract_output_text(response)
            parsed = json.loads(raw_text)
            return LLMInsight(
                enabled=True,
                provider="openai",
                model=self.config.model,
                executive_summary=str(parsed["executive_summary"]),
                root_cause_rationale=str(parsed["root_cause_rationale"]),
                additional_tests=[str(item) for item in parsed["additional_tests"]],
                recommended_fix_order=[str(item) for item in parsed["recommended_fix_order"]],
                confidence_note=str(parsed["confidence_note"]),
            )
        except Exception as exc:
            return disabled_insight(self.config, f"LLM review failed: {exc}")

    def _run_gemini(self, payload: dict[str, Any]) -> LLMInsight:
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            return disabled_insight(self.config, "Install google-genai to enable the Gemini LLM layer.")

        try:
            client = genai.Client(api_key=self.config.api_key)
            response = client.models.generate_content(
                model=self.config.model,
                contents="Return a JSON engineering review for this validation analysis:\n"
                + json.dumps(payload, indent=2),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=REVIEW_SCHEMA,
                ),
            )
            parsed = json.loads(str(response.text))
            return LLMInsight(
                enabled=True,
                provider="gemini",
                model=self.config.model,
                executive_summary=str(parsed["executive_summary"]),
                root_cause_rationale=str(parsed["root_cause_rationale"]),
                additional_tests=[str(item) for item in parsed["additional_tests"]],
                recommended_fix_order=[str(item) for item in parsed["recommended_fix_order"]],
                confidence_note=str(parsed["confidence_note"]),
            )
        except Exception as exc:
            return disabled_insight(self.config, f"Gemini review failed: {exc}")


def build_review_payload(
    test_plan: list[TestCase],
    predictions: list[RiskSignal],
    log_finding: LogFinding,
    observations: list[MCPObservation],
    debugging: DebugSession,
) -> dict[str, Any]:
    return {
        "test_plan": [
            {
                "id": item.id,
                "title": item.title,
                "priority": item.priority,
                "objective": item.objective,
                "expected_result": item.expected_result,
            }
            for item in test_plan
        ],
        "failure_predictions": [
            {
                "component": item.component,
                "failure_mode": item.failure_mode,
                "severity": item.severity,
                "confidence": item.confidence,
                "indicators": item.indicators,
            }
            for item in predictions
        ],
        "log_analysis": {
            "root_cause": log_finding.root_cause,
            "confidence": log_finding.confidence,
            "affected_components": log_finding.affected_components,
            "evidence": [
                {"line": item.line, "severity": item.severity, "message": item.message}
                for item in log_finding.evidence[:8]
            ],
            "anomalies": log_finding.anomalies,
        },
        "mcp_observations": [
            {"tool": item.tool, "summary": item.summary, "data": item.data} for item in observations
        ],
        "multi_agent_debugging": {
            "consensus_root_cause": debugging.consensus_root_cause,
            "recommended_actions": debugging.recommended_actions,
            "opinions": [
                {
                    "agent": item.agent,
                    "hypothesis": item.hypothesis,
                    "confidence": item.confidence,
                    "evidence": item.evidence,
                }
                for item in debugging.opinions
            ],
        },
    }


def extract_output_text(response: Any) -> str:
    output_text = getattr(response, "output_text", "")
    if output_text:
        return str(output_text)

    output = getattr(response, "output", [])
    chunks: list[str] = []
    for item in output:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", "")
            if text:
                chunks.append(str(text))
    return "".join(chunks)


def disabled_insight(config: LLMConfig, reason: str) -> LLMInsight:
    return LLMInsight(
        enabled=False,
        provider=config.provider,
        model=config.model,
        executive_summary="Local deterministic agents completed the analysis.",
        root_cause_rationale="Enable the LLM layer to add a model-generated engineering review.",
        additional_tests=[],
        recommended_fix_order=[],
        confidence_note=reason,
        error=reason,
    )
