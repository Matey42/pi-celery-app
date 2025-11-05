# Pi Celery App

Asynchronous API that calculates `n` decimal places of π using a fun Chudnovsky-series algorithm with Celery workers. Packaged with Docker Compose so you don't need to install anything locally.

## What you get

- FastAPI HTTP API with automatic docs at `/docs`
- Celery worker computing π with progress updates
- Redis as broker/result backend
- Flower dashboard at `http://localhost:5555` for task monitoring

## Run it

Prerequisites: Docker Desktop.

In a terminal at the project root:

```powershell
docker compose up --build
```

Services will start:

- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Flower: http://localhost:5555

## API

Two endpoints:

1) Start a calculation

```
GET /calculate_pi?n=123
```

Response

```json
{ "task_id": "<celery-task-id>" }
```

2) Check progress

```
GET /check_progress?task_id=<celery-task-id>
```

Responses

```json
{ "state": "PROGRESS", "progress": 0.25, "result": null }
```

or

```json
{ "state": "FINISHED", "progress": 1.0, "result": "3.14" }
```

Notes:

- `result` is a string to preserve precision for large `n`.
- Progress is the fraction of terms computed (not accuracy), which is great for UX.

## Implementation details

- Algorithm: Chudnovsky series with arbitrary precision via `mpmath`
- Each term adds ~14.18 digits; we compute enough terms to cover `n`
- Celery task reports progress via `self.update_state(...)` with `{progress}`
- FastAPI pulls task state using `AsyncResult`

## Tuning

- Max `n` is capped at 10000 to avoid excessive CPU/RAM in a container
- Change the cap in `tasks.py` if you need more
- Update worker concurrency via Docker resources or Celery options

## Dev tips

- Watch tasks in Flower: http://localhost:5555
- Explore and try the API at `/docs`

