from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.pipeline import TestEngineerPipeline


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
FRONTEND = ROOT / "frontend"


class AnalyzeRequest(BaseModel):
    spec: str = Field(default="", description="Requirement or design specification text")
    logs: str = Field(default="", description="Validation or debug log text")


app = FastAPI(title="AI Test Engineer Copilot", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = TestEngineerPipeline()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ai-test-engineer-copilot"}


@app.get("/api/sample")
def sample() -> dict[str, str]:
    return {
        "spec": (DATA / "sample_network_card_spec.md").read_text(encoding="utf-8"),
        "logs": (DATA / "sample_validation_log.txt").read_text(encoding="utf-8"),
    }


@app.post("/api/analyze")
def analyze(request: AnalyzeRequest) -> dict:
    return pipeline.analyze(request.spec, request.logs).to_dict()


if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND), html=True), name="frontend")
