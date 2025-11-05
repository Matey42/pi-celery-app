import os
from celery import Celery


def make_celery() -> Celery:
	broker_url = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
	result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

	celery = Celery(
		"pi_celery_app",
		broker=broker_url,
		backend=result_backend,
		include=["tasks"],
	)
	
	celery.conf.update(
		task_track_started=True,
		result_expires=3600,
		task_serializer="json",
		accept_content=["json"],
		result_serializer="json",
		timezone="UTC",
		worker_max_tasks_per_child=100,
	)

	return celery
