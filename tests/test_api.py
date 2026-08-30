import pytest
from unittest.mock import patch, AsyncMock

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@patch("app.api.routes.TraceService.ingest_trace", new_callable=AsyncMock)
def test_ingest_traces_batch(mock_ingest, client):
    mock_ingest.return_value = {"status": "created", "trace_id": "123"}
    
    payload = {
        "traces": [
            {
                "idempotency_key": "key1",
                "prompt": "Hello",
                "completion": "World",
                "latency_ms": 150.5,
                "token_usage": 10
            }
        ]
    }
    
    response = client.post("/api/v1/traces/batch", json=payload)
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert len(response.json()["results"]) == 1

@patch("app.api.routes.TraceService.trigger_evaluation", new_callable=AsyncMock)
def test_run_evaluations(mock_trigger, client):
    payload = {"trace_ids": ["123", "456"]}
    response = client.post("/api/v1/evaluations/run", json=payload)
    
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    mock_trigger.assert_called_once_with(["123", "456"])

@patch("app.api.routes.AnalyticsService.get_model_performance", new_callable=AsyncMock)
def test_get_model_performance(mock_get_perf, client):
    mock_get_perf.return_value = {
        "total_traces": 100,
        "avg_latency_ms": 200.0,
        "avg_token_usage": 50.0
    }
    
    response = client.get("/api/v1/analytics/model-performance")
    assert response.status_code == 200
    assert response.json()["total_traces"] == 100
