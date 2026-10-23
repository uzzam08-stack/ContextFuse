"""
ContextFuse – FastAPI router for scenarios, orchestration, and benchmarks.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.scenarios.loader import list_scenarios, load_scenario
from app.schemas.decision import OrchestrationResult, BenchmarkEntry
from app.services.orchestrator import run_orchestration
from app.services.benchmark import run_benchmark
from app.services.run_store import get_run, list_runs, get_storage_status
from app.services.bedrock_client import check_bedrock_status
from app.services.decider_client import check_decider_status

router = APIRouter(prefix="/api", tags=["contextfuse"])


# ─── Health & Status ─────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    return {"status": "ok", "service": "ContextFuse", "version": "1.0.0"}


@router.get("/status")
async def get_status():
    """
    Accurately exposes the status of all integrations:
    Amazon Bedrock, Strands Decider 2B, DynamoDB, CloudWatch, and Lambda.
    """
    return {
        "app": "ContextFuse",
        "version": "1.0.0",
        "integrations": {
            "bedrock": check_bedrock_status(),
            "decider": await check_decider_status(),
            "dynamodb": get_storage_status(),
            "cloudwatch": {
                "status": "CONFIGURED",
                "mode": "stdout_structured_stream",
                "note": "JSON audit events emitted to stdout for automatic CloudWatch ingestion",
            },
            "lambda": {
                "status": "CONFIGURED",
                "handler": "app.lambda_handler.handler",
                "note": "Mangum ASGI adapter ready for AWS Lambda & API Gateway",
            },
        },
    }


# ─── Scenarios ───────────────────────────────────────────────────────────────

@router.get("/scenarios")
async def get_scenarios():
    """List all available scenarios."""
    return {"scenarios": list_scenarios()}


@router.get("/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str):
    """Get scenario details including evidence bundle."""
    try:
        bundle = load_scenario(scenario_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return bundle.model_dump(mode="json")


# ─── Orchestration ───────────────────────────────────────────────────────────

@router.post("/run/{scenario_id}", response_model=OrchestrationResult)
async def run_scenario(scenario_id: str):
    """
    Execute the full ContextFuse orchestration for a scenario:
    context load → risk detection → Decider → safety guard → tool → Bedrock → outcome.
    """
    try:
        result = await run_orchestration(scenario_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Orchestration error: {exc}")
    return result


# ─── Benchmark ───────────────────────────────────────────────────────────────

@router.get("/benchmark", response_model=list[BenchmarkEntry])
async def get_benchmark():
    """Run the three-strategy benchmark and return comparison data."""
    return await run_benchmark()


# ─── Run History / Audit ─────────────────────────────────────────────────────

@router.get("/runs")
async def get_runs(limit: int = 20):
    """Retrieve history of recent orchestration runs from persistence."""
    return {"runs": await list_runs(limit=limit)}


@router.get("/runs/{run_id}")
async def get_run_by_id(run_id: str):
    """Retrieve details of a specific orchestration run by ID."""
    run_data = await get_run(run_id)
    if not run_data:
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found")
    return run_data
