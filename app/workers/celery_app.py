from celery import Celery
from celery.signals import setup_logging

from app.core.config import settings
from app.core.logging import configure_logging


@setup_logging.connect
def _configure_structlog(**_kwargs: object) -> None:
    """Keep Celery from installing its own root handler; use structlog JSON."""
    configure_logging()


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
