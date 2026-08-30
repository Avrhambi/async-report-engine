from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "async_report_engine",
    broker=settings.CELERY_BROKER_URL,
    backend="rpc://",
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_default_queue="default",
    task_track_started=True,
)
