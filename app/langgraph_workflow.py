from __future__ import annotations

from typing import TypedDict

from app.agents import (
    CollaborativeDebuggingAgent,
    FailurePredictionAgent,
    LogAnalysisAgent,
    ReportGeneratorAgent,
    TestPlanGeneratorAgent,
)
from app.domain import (
    DebugSession,
    LLMInsight,
    LogFinding,
    MCPObservation,
    PipelineResult,
    ReportBundle,
    RiskSignal,
    TestCase,
)
from app.llm import LLMReviewer
from app.mcp_tools import MCPToolRegistry, collect_mcp_context
from app.rag import SimpleRAG


class TestEngineerState(TypedDict, total=False):
    spec: str
    logs: str
    knowledge_base: SimpleRAG
    observations: list[MCPObservation]
    test_plan: list[TestCase]
    predictions: list[RiskSignal]
    log_analysis: LogFinding
    debugging: DebugSession
    llm_insight: LLMInsight
    report: ReportBundle
    result: PipelineResult


def run_langgraph_workflow(
    spec: str,
    logs: str,
    tool_registry: MCPToolRegistry,
    llm_reviewer: LLMReviewer,
) -> PipelineResult:
    """Run the same agent workflow with LangGraph when the package is installed."""

    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:
        raise RuntimeError("Install langgraph to enable AI_COPILOT_USE_LANGGRAPH=1.") from exc

    test_plan_agent = TestPlanGeneratorAgent()
    failure_agent = FailurePredictionAgent()
    log_agent = LogAnalysisAgent()
    debugging_agent = CollaborativeDebuggingAgent()
    report_agent = ReportGeneratorAgent()

    def build_knowledge(state: TestEngineerState) -> TestEngineerState:
        return {
            "knowledge_base": SimpleRAG.from_documents(
                {
                    "Requirement Specification": state["spec"],
                    "Validation Log": state["logs"],
                }
            )
        }

    def collect_tools(state: TestEngineerState) -> TestEngineerState:
        return {"observations": collect_mcp_context(tool_registry, state["logs"])}

    def generate_tests(state: TestEngineerState) -> TestEngineerState:
        return {"test_plan": test_plan_agent.run(state["spec"], state["knowledge_base"])}

    def predict_failures(state: TestEngineerState) -> TestEngineerState:
        return {"predictions": failure_agent.run(state["spec"], state["knowledge_base"])}

    def analyze_logs(state: TestEngineerState) -> TestEngineerState:
        return {"log_analysis": log_agent.run(state["logs"], state["knowledge_base"])}

    def debug_failure(state: TestEngineerState) -> TestEngineerState:
        return {
            "debugging": debugging_agent.run(
                state["predictions"],
                state["log_analysis"],
                state["observations"],
            )
        }

    def review_with_llm(state: TestEngineerState) -> TestEngineerState:
        return {
            "llm_insight": llm_reviewer.run(
                state["test_plan"],
                state["predictions"],
                state["log_analysis"],
                state["observations"],
                state["debugging"],
            )
        }

    def generate_report(state: TestEngineerState) -> TestEngineerState:
        return {
            "report": report_agent.run(
                state["test_plan"],
                state["predictions"],
                state["log_analysis"],
                state["observations"],
                state["debugging"],
                state["llm_insight"],
            )
        }

    def finalize(state: TestEngineerState) -> TestEngineerState:
        return {
            "result": PipelineResult(
                test_plan=state["test_plan"],
                failure_predictions=state["predictions"],
                log_analysis=state["log_analysis"],
                mcp_observations=state["observations"],
                debugging=state["debugging"],
                llm_insight=state["llm_insight"],
                report=state["report"],
            )
        }

    builder = StateGraph(TestEngineerState)
    builder.add_node("build_knowledge", build_knowledge)
    builder.add_node("collect_tools", collect_tools)
    builder.add_node("generate_tests", generate_tests)
    builder.add_node("predict_failures", predict_failures)
    builder.add_node("analyze_logs", analyze_logs)
    builder.add_node("debug_failure", debug_failure)
    builder.add_node("review_with_llm", review_with_llm)
    builder.add_node("generate_report", generate_report)
    builder.add_node("finalize", finalize)

    builder.add_edge(START, "build_knowledge")
    builder.add_edge("build_knowledge", "collect_tools")
    builder.add_edge("collect_tools", "generate_tests")
    builder.add_edge("generate_tests", "predict_failures")
    builder.add_edge("predict_failures", "analyze_logs")
    builder.add_edge("analyze_logs", "debug_failure")
    builder.add_edge("debug_failure", "review_with_llm")
    builder.add_edge("review_with_llm", "generate_report")
    builder.add_edge("generate_report", "finalize")
    builder.add_edge("finalize", END)

    graph = builder.compile()
    final_state = graph.invoke({"spec": spec, "logs": logs})
    return final_state["result"]
