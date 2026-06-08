from __future__ import annotations

import os

from app.agents import (
    CollaborativeDebuggingAgent,
    FailurePredictionAgent,
    LogAnalysisAgent,
    ReportGeneratorAgent,
    TestPlanGeneratorAgent,
)
from app.domain import PipelineResult
from app.llm import LLMReviewer
from app.mcp_tools import MCPToolRegistry, collect_mcp_context
from app.rag import SimpleRAG


class TestEngineerPipeline:
    def __init__(self, tool_registry: MCPToolRegistry | None = None) -> None:
        self.tool_registry = tool_registry or MCPToolRegistry()
        self.test_plan_agent = TestPlanGeneratorAgent()
        self.failure_agent = FailurePredictionAgent()
        self.log_agent = LogAnalysisAgent()
        self.debugging_agent = CollaborativeDebuggingAgent()
        self.report_agent = ReportGeneratorAgent()
        self.llm_reviewer = LLMReviewer()

    def analyze(self, spec: str, logs: str) -> PipelineResult:
        if os.environ.get("AI_COPILOT_USE_LANGGRAPH", "").lower() in {"1", "true", "yes"}:
            try:
                from app.langgraph_workflow import run_langgraph_workflow

                return run_langgraph_workflow(spec, logs, self.tool_registry, self.llm_reviewer)
            except Exception:
                if os.environ.get("AI_COPILOT_LANGGRAPH_STRICT", "").lower() in {"1", "true", "yes"}:
                    raise

        knowledge_base = SimpleRAG.from_documents(
            {
                "Requirement Specification": spec,
                "Validation Log": logs,
            }
        )

        observations = collect_mcp_context(self.tool_registry, logs)
        test_plan = self.test_plan_agent.run(spec, knowledge_base)
        predictions = self.failure_agent.run(spec, knowledge_base)
        log_analysis = self.log_agent.run(logs, knowledge_base)
        debugging = self.debugging_agent.run(predictions, log_analysis, observations)
        llm_insight = self.llm_reviewer.run(test_plan, predictions, log_analysis, observations, debugging)
        report = self.report_agent.run(
            test_plan,
            predictions,
            log_analysis,
            observations,
            debugging,
            llm_insight,
        )

        return PipelineResult(
            test_plan=test_plan,
            failure_predictions=predictions,
            log_analysis=log_analysis,
            mcp_observations=observations,
            debugging=debugging,
            llm_insight=llm_insight,
            report=report,
        )
