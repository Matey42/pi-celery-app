from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from celery.result import AsyncResult

from celery_config import make_celery


app = FastAPI(
	title="Pi Celery App",
	description=(
		"Calculate n digits of π asynchronously using a (not) fun algorithm (Chudnovsky).\n\n"
		"Use /calculate_pi?n=123 to start a job and /check_progress?task_id=... to poll status."
	),
	version="1.0.0",
)

celery_app = make_celery()


class StartResponse(BaseModel):
	task_id: str = Field(..., description="Celery task ID for tracking progress")


class ProgressResponse(BaseModel):
	state: str = Field(..., description="PROGRESS or FINISHED")
	progress: float = Field(..., ge=0.0, le=1.0, description="Proportion complete (0..1)")
	result: Optional[str] = Field(
		None, description="π to n decimals as a string when finished; null otherwise"
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
	from tasks import calculate_pi as calculate_pi_task

	async_result = calculate_pi_task.delay(int(n))
	return StartResponse(task_id=async_result.id)


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
