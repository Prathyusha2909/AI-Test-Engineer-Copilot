from pathlib import Path
import os
import unittest

from app.pipeline import TestEngineerPipeline


ROOT = Path(__file__).resolve().parents[1]


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["AI_COPILOT_DISABLE_LLM"] = "1"
        spec = (ROOT / "data" / "sample_network_card_spec.md").read_text(encoding="utf-8")
        logs = (ROOT / "data" / "sample_validation_log.txt").read_text(encoding="utf-8")
        self.result = TestEngineerPipeline().analyze(spec, logs)

    def tearDown(self) -> None:
        os.environ.pop("AI_COPILOT_DISABLE_LLM", None)

    def test_generates_domain_specific_test_plan(self) -> None:
        titles = {case.title for case in self.result.test_plan}
        self.assertIn("PCIe Enumeration and DMA Sanity", titles)
        self.assertIn("Throughput and Packet Loss", titles)
        self.assertIn("Thermal Stress and Throttling", titles)

    def test_predicts_critical_components(self) -> None:
        components = {risk.component for risk in self.result.failure_predictions}
        self.assertIn("PCIe Interface", components)
        self.assertIn("Packet Buffer Manager", components)
        self.assertIn("Thermal and Power Delivery", components)

    def test_detects_dma_timeout_root_cause(self) -> None:
        self.assertIn("DMA timeout", self.result.log_analysis.root_cause)
        self.assertGreaterEqual(self.result.log_analysis.confidence, 0.8)
        self.assertTrue(self.result.log_analysis.evidence)

    def test_report_contains_recommended_actions(self) -> None:
        report = self.result.report.markdown
        self.assertIn("Recommended Fixes and Next Tests", report)
        self.assertIn("PCIe protocol trace", report)

    def test_llm_layer_can_be_disabled_for_local_demo(self) -> None:
        self.assertFalse(self.result.llm_insight.enabled)
        self.assertIn("LLM disabled", self.result.llm_insight.confidence_note)


if __name__ == "__main__":
    unittest.main()
