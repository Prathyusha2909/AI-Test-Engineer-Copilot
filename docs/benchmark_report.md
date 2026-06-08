# Benchmark Report

Generated on: 2026-06-08

## Dataset

- Cases: 7
- Domain: hardware/software validation logs for network-card style systems
- Coverage: PCIe/DMA, packet buffers, firmware recovery, PHY signal integrity, thermal stress, power rail faults, and an ambiguous mixed-fault case

## Metrics

| Metric | Score |
| --- | ---: |
| Root Cause Accuracy | 86% |
| Root Cause Precision | 100% |
| Root Cause Recall | 93% |
| Test Plan Coverage | 100% |
| Evidence Recall | 100% |
| Overall Score | 96% |

## Per-Case Results

| Case | Expected Signature | Predicted Root Cause | Score |
| --- | --- | --- | ---: |
| dma_timeout_pcie | dma timeout | DMA timeout caused by delayed PCIe completions | 100% |
| queue_overflow_burst | queue overflow | Packet queue overflow under burst traffic | 100% |
| firmware_watchdog | firmware state machine | Firmware state machine fault during initialization or recovery | 100% |
| phy_signal_integrity | signal integrity | Signal integrity margin issue causing link instability | 100% |
| thermal_throttle | thermal stress | Thermal stress triggered throttling and performance degradation | 100% |
| power_rail_droop | power delivery | Power delivery instability during high-load transition | 100% |
| mixed_thermal_power_ambiguous | power delivery | Thermal stress triggered throttling and performance degradation | 70% |

## Notes

- The benchmark is deterministic and can run without API keys.
- The ambiguous mixed thermal/power case is intentionally included so the score is not artificially perfect.
- DeepEval and Ragas adapters are included for LLM-as-judge and RAG-specific evaluation when optional dependencies and model keys are available.
