# Evaluation

This folder contains the benchmark dataset and evaluation scripts for the AI Test Engineer Copilot.

## Deterministic Benchmark

Runs without API keys:

```powershell
python evaluation/run_evaluation.py
```

Outputs:

- `evaluation/results.csv`
- `evaluation/summary.json`
- `docs/benchmark_report.md`

## DeepEval Adapter

Requires optional dependencies and an LLM key:

```powershell
pip install -r requirements-optional.txt
$env:OPENAI_API_KEY="your-api-key"
python evaluation/run_deepeval.py
```

## Ragas Adapter

Requires optional dependencies and an LLM key:

```powershell
pip install -r requirements-optional.txt
$env:OPENAI_API_KEY="your-api-key"
python evaluation/run_ragas.py
```

The deterministic benchmark is committed so recruiters can inspect the dataset, metrics, and benchmark report without running paid LLM evaluation.
