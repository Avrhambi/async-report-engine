from unittest.mock import patch

import pytest
from httpx import AsyncClient

# Mark all tests in this file as async so we don't have to add @pytest.mark.asyncio to each one
pytestmark = pytest.mark.asyncio

async def test_health_check(client: AsyncClient):
    """Test the root health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

async def test_ingest_events_batch(client: AsyncClient):
    """Test the event ingestion batch endpoint."""
    payload = [
        {
            "user_id": "user_123",
            "event_type": "click",
            "payload": {"button": "submit"}
        },
        {
            "user_id": "user_123",
            "event_type": "view",
            "payload": {"page": "home"}
        }
    ]
    
    response = await client.post("/api/v1/events/batch", json=payload)
    
    assert response.status_code == 202
    data = response.json()
    assert "Successfully queued 2 events" in data["message"]

@patch("app.api.routes.generate_report_task.delay")
async def test_generate_report(mock_delay, client: AsyncClient):
    """Test the report generation dispatch endpoint."""
    response = await client.post("/api/v1/reports/generate")
    
    assert response.status_code == 202
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "202 Accepted"
    
    # Ensure the background task was dispatched with the generated task_id
    mock_delay.assert_called_once_with(data["task_id"])

async def test_get_report_not_found(client: AsyncClient):
    """Test retrieving a report that doesn't exist."""
    response = await client.get("/api/v1/reports/non_existent_id")
    
    assert response.status_code == 404
    assert response.json()["detail"] == "Report not found"

@patch("app.api.routes.AnalyticsService.get_metrics")
async def test_get_analytics_metrics(mock_get_metrics, client: AsyncClient):
    """Test fetching analytics metrics."""
    # Mock the service response to avoid hitting Redis/DB in this isolated API test
    mock_metrics = {
        "total_events": 100,
        "events_by_type": {"click": 60, "view": 40}
    }
    # get_metrics is an async function in the service, so we need to mock an async return
    mock_get_metrics.return_value = mock_metrics
    
    response = await client.get("/api/v1/analytics/metrics")
    
    assert response.status_code == 200
    assert response.json() == mock_metrics
