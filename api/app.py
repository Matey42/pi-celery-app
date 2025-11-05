from __future__ import annotations

import random
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from celery.result import AsyncResult

from celery_config import make_celery


app = FastAPI(
	title="Pi Celery App",
	description=(
		"Calculate π asynchronously using Chudnovsky (high precision) or Buffon's needle (Monte Carlo).\n\n"
		"This endpoint randomly picks one method: n = decimals for Chudnovsky; for Buffon we derive throws and decimals from n.\n\n"
		"Use /check_progress?task_id=... to poll status."
	),
	version="1.1.0",
)

celery_app = make_celery()


class StartResponse(BaseModel):
    task_id: str = Field(..., description="Celery task ID for tracking progress")
    algorithm: str = Field(..., description="Algorithm used for π calculation")


class ProgressResponse(BaseModel):
    state: str = Field(..., description="PROGRESS or FINISHED")
    progress: float = Field(..., ge=0.0, le=1.0, description="Proportion complete (0..1)")
    result: Optional[str] = Field(
        None, description="π as a string when finished; null otherwise"
    )


@app.get("/", summary="Service info")
def root() -> dict:
    return {
        "service": "pi-celery-app",
        "docs": "/docs",
        "examples": {
            "start": "/calculate_pi?n=123",
            "progress": "/check_progress?task_id=<id>",
        },
    }


@app.get("/calculate_pi", response_model=StartResponse, summary="Start π calculation")
def calculate_pi_endpoint(n: int = Query(..., ge=1, le=10000, description="Decimal places")):
	from tasks import calculate_pi_chudnovsky, calculate_pi_buffon

	# Randomly choose an algorithm
	if random.choice([True, False]):
		# Chudnovsky: use n as decimal places directly
		async_result = calculate_pi_chudnovsky.delay(int(n))
		algorithm = "calculate_pi_chudnovsky"
	else:
		# Buffon: derive throws and decimals from n
		throws = max(100, min(20_000_000, int(n) * 1000))
		async_result = calculate_pi_buffon.delay(int(n), throws=throws)
		algorithm = "calculate_pi_buffon"

	return StartResponse(task_id=async_result.id, algorithm=algorithm)


@app.get(
	"/check_progress",
	response_model=ProgressResponse,
	summary="Check progress for a task",
)
def check_progress(task_id: str = Query(..., description="Celery task ID")):
    result = AsyncResult(task_id, app=celery_app)

    if result.successful():
        value = result.get()
        return ProgressResponse(state="FINISHED", progress=1.0, result=str(value))

    if result.failed():
        # Map failure to FINISHED with no result; include minimal error detail
        err = str(result.result) if result.result else "Task failed"
        raise HTTPException(status_code=500, detail={"task_id": task_id, "error": err})

    # Pending/started/progress
    info = result.info or {}
    progress = float(info.get("progress", 0.0))
    progress = max(0.0, min(1.0, progress))
    return ProgressResponse(state="PROGRESS", progress=progress, result=None)
