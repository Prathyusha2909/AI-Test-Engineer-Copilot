from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.domain import MCPObservation


ToolHandler = Callable[[dict[str, Any]], MCPObservation]


@dataclass
class MCPToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


class MCPToolRegistry:
    """MCP-style registry with deterministic mock engineering tools.

    The interface mirrors how a real MCP client would discover and call tools.
    Swap these handlers with MCP Python SDK tool calls when connecting to lab
    equipment or internal services.
    """

    def __init__(self) -> None:
        self._tools: dict[str, tuple[MCPToolSpec, ToolHandler]] = {
            "test_equipment.health": (
                MCPToolSpec(
                    name="test_equipment.health",
                    description="Read card-level health, rails, thermals, and link state.",
                    input_schema={"type": "object", "properties": {"target": {"type": "string"}}},
                ),
                self._equipment_health,
            ),
            "oscilloscope.capture_summary": (
                MCPToolSpec(
                    name="oscilloscope.capture_summary",
                    description="Return summary statistics for a captured hardware signal.",
                    input_schema={"type": "object", "properties": {"signal": {"type": "string"}}},
                ),
                self._oscilloscope_summary,
            ),
            "test_runner.loopback": (
                MCPToolSpec(
                    name="test_runner.loopback",
                    description="Execute a short loopback validation sequence.",
                    input_schema={"type": "object", "properties": {"duration_s": {"type": "integer"}}},
                ),
                self._loopback_test,
            ),
            "log_server.failure_window": (
                MCPToolSpec(
                    name="log_server.failure_window",
                    description="Fetch a condensed window around the first failure.",
                    input_schema={"type": "object", "properties": {"logs": {"type": "string"}}},
                ),
                self._failure_window,
            ),
        }

    def list_tools(self) -> list[MCPToolSpec]:
        return [spec for spec, _handler in self._tools.values()]

    def call(self, tool_name: str, arguments: dict[str, Any]) -> MCPObservation:
        if tool_name not in self._tools:
            raise KeyError(f"Unknown MCP tool: {tool_name}")
        _spec, handler = self._tools[tool_name]
        return handler(arguments)

    def _equipment_health(self, arguments: dict[str, Any]) -> MCPObservation:
        target = str(arguments.get("target", "network-card"))
        logs = str(arguments.get("logs", "")).lower()
        thermal_alert = "thermal" in logs or "temperature" in logs or "overheat" in logs
        voltage_alert = "voltage" in logs or "rail" in logs
        data = {
            "target": target,
            "pcie_link": "Gen4 x16",
            "core_rail_v": 0.91 if not voltage_alert else 0.84,
            "aux_rail_v": 3.29,
            "asic_temp_c": 74 if not thermal_alert else 91,
            "health": "degraded" if thermal_alert or voltage_alert else "nominal",
        }
        summary = "Card health nominal"
        if thermal_alert:
            summary = "Card health degraded: elevated ASIC temperature"
        elif voltage_alert:
            summary = "Card health degraded: core rail droop observed"
        return MCPObservation(tool="test_equipment.health", summary=summary, data=data)

    def _oscilloscope_summary(self, arguments: dict[str, Any]) -> MCPObservation:
        signal = str(arguments.get("signal", "pcie_refclk"))
        logs = str(arguments.get("logs", "")).lower()
        link_issue = "link flap" in logs or "crc" in logs or "retrain" in logs
        data = {
            "signal": signal,
            "jitter_ps": 7.8 if not link_issue else 15.6,
            "eye_height_mv": 318 if not link_issue else 208,
            "capture_quality": "pass" if not link_issue else "marginal",
        }
        summary = "Signal capture within margin"
        if link_issue:
            summary = "Signal capture marginal: elevated jitter and reduced eye height"
        return MCPObservation(tool="oscilloscope.capture_summary", summary=summary, data=data)

    def _loopback_test(self, arguments: dict[str, Any]) -> MCPObservation:
        duration_s = int(arguments.get("duration_s", 30))
        logs = str(arguments.get("logs", "")).lower()
        packet_issue = "packet drop" in logs or "crc" in logs or "queue overflow" in logs
        data = {
            "duration_s": duration_s,
            "packets_sent": duration_s * 125_000,
            "packets_lost": 0 if not packet_issue else 1842,
            "result": "pass" if not packet_issue else "fail",
        }
        summary = "Loopback validation passed"
        if packet_issue:
            summary = "Loopback validation failed: packet loss reproduced"
        return MCPObservation(tool="test_runner.loopback", summary=summary, data=data)

    def _failure_window(self, arguments: dict[str, Any]) -> MCPObservation:
        logs = str(arguments.get("logs", ""))
        lines = logs.splitlines()
        failure_index = next(
            (index for index, line in enumerate(lines) if any(term in line.lower() for term in ("error", "fail", "timeout"))),
            0,
        )
        start = max(0, failure_index - 2)
        end = min(len(lines), failure_index + 3)
        window = lines[start:end]
        return MCPObservation(
            tool="log_server.failure_window",
            summary=f"Captured {len(window)} lines around first failure",
            data={"start_line": start + 1, "lines": window},
        )


def collect_mcp_context(registry: MCPToolRegistry, logs: str) -> list[MCPObservation]:
    calls = [
        ("test_equipment.health", {"target": "network-card", "logs": logs}),
        ("oscilloscope.capture_summary", {"signal": "pcie_refclk", "logs": logs}),
        ("test_runner.loopback", {"duration_s": 30, "logs": logs}),
        ("log_server.failure_window", {"logs": logs}),
    ]
    return [registry.call(name, arguments) for name, arguments in calls]
