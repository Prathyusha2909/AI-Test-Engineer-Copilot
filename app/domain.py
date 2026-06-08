from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SourceReference:
    title: str
    snippet: str
    score: float


@dataclass
class TestCase:
    id: str
    title: str
    objective: str
    setup: list[str]
    procedure: list[str]
    expected_result: str
    priority: str
    source_refs: list[SourceReference] = field(default_factory=list)


@dataclass
class RiskSignal:
    component: str
    failure_mode: str
    indicators: list[str]
    severity: str
    confidence: float
    source_refs: list[SourceReference] = field(default_factory=list)


@dataclass
class LogEvidence:
    line: int
    severity: str
    message: str


@dataclass
class LogFinding:
    root_cause: str
    confidence: float
    affected_components: list[str]
    evidence: list[LogEvidence]
    anomalies: list[str]
    source_refs: list[SourceReference] = field(default_factory=list)


@dataclass
class MCPObservation:
    tool: str
    summary: str
    data: dict[str, Any]


@dataclass
class DebugOpinion:
    agent: str
    hypothesis: str
    evidence: list[str]
    confidence: float


@dataclass
class DebugSession:
    consensus_root_cause: str
    opinions: list[DebugOpinion]
    recommended_actions: list[str]


@dataclass
class LLMInsight:
    enabled: bool
    provider: str
    model: str
    executive_summary: str
    root_cause_rationale: str
    additional_tests: list[str]
    recommended_fix_order: list[str]
    confidence_note: str
    error: str | None = None


@dataclass
class ReportBundle:
    markdown: str
    html: str


@dataclass
class PipelineResult:
    test_plan: list[TestCase]
    failure_predictions: list[RiskSignal]
    log_analysis: LogFinding
    mcp_observations: list[MCPObservation]
    debugging: DebugSession
    llm_insight: LLMInsight
    report: ReportBundle

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
