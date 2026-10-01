from celery import Celery

from src.settings import settings

celery_app = Celery(
    "orchestrator",
    broker=settings.celery_broker_url,
)

celery_app.conf.update(
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
    enable_utc=True,
    result_serializer="json",
    task_ignore_result=True,
    task_serializer="json",
    timezone="UTC",
)
