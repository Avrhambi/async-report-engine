"""Domain exceptions. This layer imports nothing from other app/ layers."""
from __future__ import annotations


class DomainError(Exception):
    """Base class for domain-level errors."""


class ReportNotFoundError(DomainError):
    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"No report found for task_id {task_id!r}")
