from typing import List
from app.repositories.trace_repo import TraceRepository
from app.workers.tasks import evaluate_trace_task

class TraceService:
    def __init__(self, trace_repo: TraceRepository):
        self.trace_repo = trace_repo

    async def ingest_trace(self, idempotency_key: str, prompt: str, completion: str, latency_ms: float, token_usage: int) -> dict:
        trace = await self.trace_repo.create_trace(
            idempotency_key=idempotency_key,
            prompt=prompt,
            completion=completion,
            latency_ms=latency_ms,
            token_usage=token_usage
        )
        
        if not trace:
            # Idempotency collision
            return {"status": "duplicate", "trace_id": None}
            
        return {"status": "created", "trace_id": trace.id}

    async def trigger_evaluation(self, trace_ids: List[str]) -> None:
        for trace_id in trace_ids:
            # Create a pending report in the DB first
            await self.trace_repo.create_evaluation_report(trace_id=trace_id, status="PENDING")
            
            # Dispatch background task
            evaluate_trace_task.delay(trace_id)
