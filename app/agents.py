from __future__ import annotations

import html
import re
from collections import Counter

from app.domain import (
    DebugOpinion,
    DebugSession,
    LogEvidence,
    LogFinding,
    MCPObservation,
    ReportBundle,
    RiskSignal,
    SourceReference,
    TestCase,
)
from app.rag import SimpleRAG, compact


class TestPlanGeneratorAgent:
    def run(self, spec: str, knowledge_base: SimpleRAG) -> list[TestCase]:
        spec_lc = spec.lower()
        definitions = [
            {
                "title": "Power-On and Rail Validation",
                "terms": [],
                "priority": "P0",
                "objective": "Verify the card powers on cleanly and all monitored rails remain inside tolerance.",
                "setup": ["Install card in qualified host", "Attach power monitor", "Enable serial console"],
                "procedure": [
                    "Cold boot the host with the device installed.",
                    "Capture rail telemetry during boot and firmware initialization.",
                    "Verify link LEDs, boot messages, and health registers.",
                ],
                "expected": "No brownout, fault LED, boot hang, or rail excursion is observed.",
            },
            {
                "title": "PCIe Enumeration and DMA Sanity",
                "terms": ["pcie", "pci", "dma", "transaction"],
                "priority": "P0",
                "objective": "Validate PCIe link training, enumeration, BAR mapping, interrupts, and basic DMA movement.",
                "setup": ["Protocol analyzer optional", "Driver installed", "DMA test utility available"],
                "procedure": [
                    "Boot the system and confirm expected PCIe generation and lane width.",
                    "Run DMA read/write smoke tests with small and large buffers.",
                    "Check for completion timeout, poisoned TLP, or interrupt loss.",
                ],
                "expected": "Device enumerates at expected link width and DMA completes without timeout.",
            },
            {
                "title": "Firmware Boot and Recovery",
                "terms": ["firmware", "boot", "loader", "image", "watchdog"],
                "priority": "P0",
                "objective": "Confirm firmware loads, validates, and recovers predictably from failed image scenarios.",
                "setup": ["Known-good image", "Rollback image", "Console log capture"],
                "procedure": [
                    "Boot using a known-good image and record initialization sequence.",
                    "Inject an invalid image and verify rejection path.",
                    "Trigger watchdog recovery and confirm rollback behavior.",
                ],
                "expected": "Firmware enters service mode or rollback path without bricking the card.",
            },
            {
                "title": "Throughput and Packet Loss",
                "terms": ["throughput", "packet", "network", "traffic", "loss", "crc"],
                "priority": "P1",
                "objective": "Measure sustained traffic performance and packet integrity under nominal conditions.",
                "setup": ["Traffic generator", "Loopback cable or peer host", "Counters reset"],
                "procedure": [
                    "Run bidirectional traffic at target line rate.",
                    "Record throughput, packet drops, retries, CRC errors, and queue depth.",
                    "Repeat with small, medium, and jumbo frames.",
                ],
                "expected": "Throughput meets target and packet loss remains below acceptance threshold.",
            },
            {
                "title": "Thermal Stress and Throttling",
                "terms": ["thermal", "temperature", "temp", "overheat", "fan"],
                "priority": "P1",
                "objective": "Verify the card remains functional across thermal limits and reports throttling accurately.",
                "setup": ["Thermal chamber or controlled airflow", "Temperature sensors", "Sustained traffic load"],
                "procedure": [
                    "Run sustained traffic while increasing ambient temperature.",
                    "Capture ASIC temperature, throttling events, and packet counters.",
                    "Return to nominal temperature and verify recovery.",
                ],
                "expected": "Thermal warnings occur before failure and traffic recovers after cooldown.",
            },
            {
                "title": "Queue Overflow and Buffer Pressure",
                "terms": ["buffer", "queue", "memory", "overflow", "descriptor", "ring"],
                "priority": "P1",
                "objective": "Exercise packet buffers, descriptor rings, and memory paths under burst traffic.",
                "setup": ["Burst traffic profile", "Driver debug counters", "Memory error reporting enabled"],
                "procedure": [
                    "Generate burst traffic above steady-state line rate.",
                    "Monitor queue occupancy, descriptor ownership, and allocation failures.",
                    "Check recovery after pressure is removed.",
                ],
                "expected": "No unrecovered queue overflow, memory corruption, or descriptor leak is observed.",
            },
            {
                "title": "Reset and Recovery",
                "terms": ["reset", "recovery", "hot reset", "surprise", "watchdog"],
                "priority": "P1",
                "objective": "Verify graceful recovery after software reset, hot reset, and surprise link events.",
                "setup": ["Reset control script", "Driver loaded", "Log capture enabled"],
                "procedure": [
                    "Run baseline traffic and trigger software reset.",
                    "Repeat with hot reset and surprise link down events.",
                    "Confirm driver and firmware return to ready state.",
                ],
                "expected": "Device recovers without host reboot, stale queues, or firmware crash.",
            },
            {
                "title": "Fault Injection and Diagnostic Reporting",
                "terms": [],
                "priority": "P2",
                "objective": "Validate diagnostic quality when injected faults trigger errors.",
                "setup": ["Fault injection harness", "Debug logging enabled", "Report export enabled"],
                "procedure": [
                    "Inject representative PCIe, firmware, packet, and thermal faults.",
                    "Verify the correct event IDs, counters, and recovery actions are logged.",
                    "Generate a failure report and confirm evidence is attached.",
                ],
                "expected": "Diagnostics identify the failing subsystem and preserve useful evidence.",
            },
        ]

        cases: list[TestCase] = []
        for definition in definitions:
            if definition["terms"] and not any(term in spec_lc for term in definition["terms"]):
                continue
            refs = knowledge_base.search(f"{definition['title']} {definition['objective']}")
            cases.append(
                TestCase(
                    id=f"TC-{len(cases) + 1:03d}",
                    title=definition["title"],
                    objective=definition["objective"],
                    setup=definition["setup"],
                    procedure=definition["procedure"],
                    expected_result=definition["expected"],
                    priority=definition["priority"],
                    source_refs=refs,
                )
            )

        return cases


class FailurePredictionAgent:
    COMPONENTS = [
        {
            "component": "PHY Layer",
            "terms": ["phy", "serdes", "signal", "crc", "link", "eye", "jitter"],
            "failure": "Signal integrity margin loss causing link retrain or CRC bursts",
            "indicators": ["CRC errors", "Link flap", "Reduced eye height", "Elevated jitter"],
            "severity": "High",
        },
        {
            "component": "PCIe Interface",
            "terms": ["pcie", "pci", "dma", "bar", "tlp", "completion", "interrupt"],
            "failure": "DMA completion timeout or PCIe transaction retry storm",
            "indicators": ["DMA timeout", "Completion timeout", "Poisoned TLP", "MSI-X delay"],
            "severity": "Critical",
        },
        {
            "component": "Firmware Loader",
            "terms": ["firmware", "boot", "loader", "image", "watchdog", "rollback"],
            "failure": "Firmware boot hang, rollback failure, or watchdog reset loop",
            "indicators": ["Boot stage stall", "Invalid image", "Watchdog reset", "Rollback mismatch"],
            "severity": "Critical",
        },
        {
            "component": "Packet Buffer Manager",
            "terms": ["buffer", "queue", "descriptor", "ring", "memory", "overflow", "drop"],
            "failure": "Queue overflow or descriptor ownership bug under burst traffic",
            "indicators": ["Queue depth saturation", "Packet drops", "Descriptor leak", "Memory corruption"],
            "severity": "High",
        },
        {
            "component": "Thermal and Power Delivery",
            "terms": ["thermal", "temperature", "power", "voltage", "rail", "throttle"],
            "failure": "Thermal throttling or rail droop under sustained load",
            "indicators": ["ASIC temperature spike", "Rail droop", "Throttle event", "Clock reduction"],
            "severity": "High",
        },
    ]

    def run(self, spec: str, knowledge_base: SimpleRAG) -> list[RiskSignal]:
        spec_lc = spec.lower()
        risks: list[RiskSignal] = []

        for component in self.COMPONENTS:
            hits = sum(1 for term in component["terms"] if term in spec_lc)
            if not hits:
                continue
            confidence = min(0.92, 0.58 + hits * 0.07)
            refs = knowledge_base.search(f"{component['component']} {component['failure']}")
            risks.append(
                RiskSignal(
                    component=component["component"],
                    failure_mode=component["failure"],
                    indicators=component["indicators"],
                    severity=component["severity"],
                    confidence=round(confidence, 2),
                    source_refs=refs,
                )
            )

        if not risks:
            refs = knowledge_base.search("power boot diagnostics")
            risks.append(
                RiskSignal(
                    component="System Integration",
                    failure_mode="Unknown integration failure due to underspecified requirements",
                    indicators=["Missing acceptance thresholds", "No diagnostic hooks", "Limited observability"],
                    severity="Medium",
                    confidence=0.48,
                    source_refs=refs,
                )
            )

        return sorted(risks, key=lambda risk: (severity_rank(risk.severity), risk.confidence), reverse=True)


class LogAnalysisAgent:
    PATTERNS = [
        {
            "name": "DMA timeout",
            "terms": ["dma timeout", "completion timeout", "tlp retry", "msi-x delay"],
            "root": "DMA timeout caused by delayed PCIe completions",
            "components": ["PCIe Interface", "DMA Engine"],
        },
        {
            "name": "Queue overflow",
            "terms": ["queue overflow", "descriptor leak", "ring full", "buffer exhausted"],
            "root": "Packet queue overflow under burst traffic",
            "components": ["Packet Buffer Manager", "Driver"],
        },
        {
            "name": "Firmware crash",
            "terms": ["watchdog", "firmware crash", "boot stage", "assert", "rollback"],
            "root": "Firmware state machine fault during initialization or recovery",
            "components": ["Firmware Loader", "Control Plane"],
        },
        {
            "name": "Signal integrity",
            "terms": ["crc", "link flap", "link retrain", "jitter", "eye height"],
            "root": "Signal integrity margin issue causing link instability",
            "components": ["PHY Layer", "PCIe Link"],
        },
        {
            "name": "Thermal throttling",
            "terms": ["thermal", "temperature", "overheat", "throttle"],
            "root": "Thermal stress triggered throttling and performance degradation",
            "components": ["Thermal and Power Delivery"],
        },
        {
            "name": "Power rail instability",
            "terms": ["voltage", "rail droop", "brownout", "power fault"],
            "root": "Power delivery instability during high-load transition",
            "components": ["Power Delivery"],
        },
    ]

    def run(self, logs: str, knowledge_base: SimpleRAG) -> LogFinding:
        if not logs.strip():
            return LogFinding(
                root_cause="No validation log provided",
                confidence=0.3,
                affected_components=[],
                evidence=[],
                anomalies=["Upload or paste test logs to enable root cause analysis."],
                source_refs=[],
            )

        evidence = extract_evidence(logs)
        lower_logs = logs.lower()
        pattern_scores: Counter[str] = Counter()
        pattern_lookup = {pattern["name"]: pattern for pattern in self.PATTERNS}

        for pattern in self.PATTERNS:
            for term in pattern["terms"]:
                pattern_scores[pattern["name"]] += lower_logs.count(term)

        error_count = sum(1 for item in evidence if item.severity in {"ERROR", "FAIL", "TIMEOUT"})
        warning_count = sum(1 for item in evidence if item.severity == "WARN")

        if pattern_scores:
            name, score = pattern_scores.most_common(1)[0]
            if score > 0:
                pattern = pattern_lookup[name]
                confidence = min(0.96, 0.55 + score * 0.1 + error_count * 0.04 + warning_count * 0.02)
                anomalies = build_anomalies(logs, pattern["terms"])
                refs = knowledge_base.search(pattern["root"])
                return LogFinding(
                    root_cause=pattern["root"],
                    confidence=round(confidence, 2),
                    affected_components=pattern["components"],
                    evidence=evidence[:10],
                    anomalies=anomalies,
                    source_refs=refs,
                )

        refs = knowledge_base.search("failure warning error validation")
        return LogFinding(
            root_cause="Failure signature is inconclusive",
            confidence=0.42,
            affected_components=[],
            evidence=evidence[:10],
            anomalies=["No known high-confidence signature matched the supplied log."],
            source_refs=refs,
        )


class CollaborativeDebuggingAgent:
    def run(
        self,
        predictions: list[RiskSignal],
        log_finding: LogFinding,
        observations: list[MCPObservation],
    ) -> DebugSession:
        risk_by_component = {risk.component: risk for risk in predictions}
        observation_text = " ".join(obs.summary.lower() for obs in observations)
        evidence_lines = [item.message for item in log_finding.evidence[:4]]

        hardware_confidence = 0.58
        hardware_hypothesis = "Hardware path is likely healthy; continue with firmware and driver isolation."
        hardware_evidence = ["MCP equipment health and signal summaries do not show a dominant hardware fault."]
        if "marginal" in observation_text or "temperature" in observation_text or "rail" in observation_text:
            hardware_confidence = 0.74
            hardware_hypothesis = "Hardware margins may be contributing to the failure signature."
            hardware_evidence = [obs.summary for obs in observations if any(term in obs.summary.lower() for term in ("marginal", "temperature", "rail"))]

        firmware_confidence = 0.61
        firmware_hypothesis = "Firmware or driver queue handling should be inspected for state-machine or descriptor bugs."
        firmware_evidence = evidence_lines or ["Log evidence is limited; prioritize instrumentation around firmware transitions."]
        if "Firmware Loader" in risk_by_component or "Packet Buffer Manager" in risk_by_component:
            firmware_confidence = 0.76

        validation_confidence = 0.72 if log_finding.evidence else 0.45
        validation_hypothesis = "Failure is reproducible enough for a narrowed validation campaign."
        validation_evidence = [obs.summary for obs in observations if obs.tool in {"test_runner.loopback", "log_server.failure_window"}]

        root_confidence = max(log_finding.confidence, hardware_confidence if "hardware" in log_finding.root_cause.lower() else 0)
        root_hypothesis = log_finding.root_cause
        root_evidence = [compact(item.message, 140) for item in log_finding.evidence[:5]] or log_finding.anomalies

        opinions = [
            DebugOpinion(
                agent="Hardware Expert",
                hypothesis=hardware_hypothesis,
                evidence=hardware_evidence,
                confidence=round(hardware_confidence, 2),
            ),
            DebugOpinion(
                agent="Firmware Expert",
                hypothesis=firmware_hypothesis,
                evidence=firmware_evidence,
                confidence=round(firmware_confidence, 2),
            ),
            DebugOpinion(
                agent="Validation Engineer",
                hypothesis=validation_hypothesis,
                evidence=validation_evidence,
                confidence=round(validation_confidence, 2),
            ),
            DebugOpinion(
                agent="Root Cause Analyzer",
                hypothesis=root_hypothesis,
                evidence=root_evidence,
                confidence=round(root_confidence, 2),
            ),
        ]

        return DebugSession(
            consensus_root_cause=log_finding.root_cause,
            opinions=opinions,
            recommended_actions=recommend_actions(log_finding, predictions, observations),
        )


class ReportGeneratorAgent:
    def run(
        self,
        test_plan: list[TestCase],
        predictions: list[RiskSignal],
        log_finding: LogFinding,
        observations: list[MCPObservation],
        debugging: DebugSession,
    ) -> ReportBundle:
        markdown = build_markdown_report(test_plan, predictions, log_finding, observations, debugging)
        return ReportBundle(markdown=markdown, html=markdown_to_html(markdown))


def extract_evidence(logs: str) -> list[LogEvidence]:
    evidence: list[LogEvidence] = []
    severity_terms = {
        "ERROR": ("error", "fatal"),
        "FAIL": ("fail", "failed", "failure"),
        "TIMEOUT": ("timeout",),
        "WARN": ("warn", "warning"),
    }

    for line_number, line in enumerate(logs.splitlines(), start=1):
        lowered = line.lower()
        severity = next((name for name, terms in severity_terms.items() if any(term in lowered for term in terms)), "")
        if severity:
            evidence.append(LogEvidence(line=line_number, severity=severity, message=line.strip()))

    return evidence


def build_anomalies(logs: str, focus_terms: list[str]) -> list[str]:
    lowered = logs.lower()
    anomalies = []
    for term in focus_terms:
        count = lowered.count(term)
        if count:
            anomalies.append(f"{term}: {count} occurrence(s)")
    if "temperature" in lowered or "thermal" in lowered:
        anomalies.append("Thermal telemetry appears near the failure window")
    if "packet drop" in lowered or "lost" in lowered:
        anomalies.append("Packet loss counters changed during the run")
    return anomalies[:8]


def recommend_actions(
    log_finding: LogFinding,
    predictions: list[RiskSignal],
    observations: list[MCPObservation],
) -> list[str]:
    root = log_finding.root_cause.lower()
    components = {risk.component for risk in predictions}
    observation_text = " ".join(obs.summary.lower() for obs in observations)
    actions: list[str] = []

    if "dma" in root or "pcie" in root or "PCIe Interface" in components:
        actions.extend(
            [
                "Capture PCIe protocol trace around the DMA timeout window.",
                "Audit DMA ring ownership, completion queue depth, and interrupt moderation settings.",
                "Run DMA tests with reduced payload size to separate timing from memory pressure.",
            ]
        )

    if "queue" in root or "Packet Buffer Manager" in components:
        actions.extend(
            [
                "Enable descriptor lifecycle tracing for enqueue, DMA handoff, completion, and free.",
                "Replay burst traffic with queue-depth telemetry sampled at sub-second intervals.",
            ]
        )

    if "firmware" in root or "Firmware Loader" in components:
        actions.extend(
            [
                "Compare firmware boot-stage timestamps against a known-good image.",
                "Verify rollback and watchdog paths using controlled image corruption.",
            ]
        )

    if "thermal" in root or "temperature" in observation_text:
        actions.extend(
            [
                "Repeat the failing test under controlled airflow and capture thermal sensor slope.",
                "Check throttle thresholds against the product thermal design limits.",
            ]
        )

    if "marginal" in observation_text or "signal" in root:
        actions.append("Run eye capture and link retrain tests across cable, slot, and lane permutations.")

    if not actions:
        actions.append("Increase log verbosity and rerun the smallest test that reproduces the failure.")

    return dedupe(actions)[:8]


def build_markdown_report(
    test_plan: list[TestCase],
    predictions: list[RiskSignal],
    log_finding: LogFinding,
    observations: list[MCPObservation],
    debugging: DebugSession,
) -> str:
    lines = [
        "# AI Test Engineer Copilot Report",
        "",
        "## Executive Summary",
        "",
        f"- Root cause: {log_finding.root_cause}",
        f"- Confidence: {int(log_finding.confidence * 100)}%",
        f"- Affected components: {', '.join(log_finding.affected_components) or 'Not enough evidence'}",
        f"- Generated test cases: {len(test_plan)}",
        "",
        "## Generated Test Plan",
        "",
    ]

    for case in test_plan:
        lines.extend(
            [
                f"### {case.id}: {case.title}",
                "",
                f"- Priority: {case.priority}",
                f"- Objective: {case.objective}",
                f"- Expected result: {case.expected_result}",
                "",
            ]
        )

    lines.extend(["## Predicted Failure Points", ""])
    for risk in predictions:
        lines.extend(
            [
                f"### {risk.component}",
                "",
                f"- Failure mode: {risk.failure_mode}",
                f"- Severity: {risk.severity}",
                f"- Confidence: {int(risk.confidence * 100)}%",
                f"- Indicators: {', '.join(risk.indicators)}",
                "",
            ]
        )

    lines.extend(["## Log Evidence", ""])
    if log_finding.evidence:
        for item in log_finding.evidence[:8]:
            lines.append(f"- Line {item.line} [{item.severity}]: {item.message}")
    else:
        lines.append("- No failure evidence was found in the supplied log.")

    lines.extend(["", "## MCP Tool Observations", ""])
    for observation in observations:
        lines.append(f"- {observation.tool}: {observation.summary}")

    lines.extend(["", "## Multi-Agent Debugging", ""])
    for opinion in debugging.opinions:
        lines.extend(
            [
                f"### {opinion.agent}",
                "",
                f"- Hypothesis: {opinion.hypothesis}",
                f"- Confidence: {int(opinion.confidence * 100)}%",
                f"- Evidence: {'; '.join(opinion.evidence) if opinion.evidence else 'No direct evidence'}",
                "",
            ]
        )

    lines.extend(["## Recommended Fixes and Next Tests", ""])
    for action in debugging.recommended_actions:
        lines.append(f"- {action}")

    return "\n".join(lines).strip() + "\n"


def markdown_to_html(markdown: str) -> str:
    html_lines = [
        "<!doctype html>",
        "<html lang=\"en\">",
        "<head>",
        "<meta charset=\"utf-8\">",
        "<title>AI Test Engineer Copilot Report</title>",
        "<style>body{font-family:Arial,sans-serif;line-height:1.5;max-width:920px;margin:40px auto;color:#17212b}h1,h2,h3{color:#102a43}code{background:#f1f5f9;padding:2px 4px}</style>",
        "</head>",
        "<body>",
    ]

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.startswith("# "):
            html_lines.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            html_lines.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("- "):
            html_lines.append(f"<p>{html.escape(line)}</p>")
        elif not line:
            continue
        else:
            html_lines.append(f"<p>{html.escape(line)}</p>")

    html_lines.extend(["</body>", "</html>"])
    return "\n".join(html_lines)


def severity_rank(value: str) -> int:
    return {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}.get(value, 0)


def dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
