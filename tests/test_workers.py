import pytest
from unittest.mock import patch, AsyncMock
from app.workers.tasks import evaluate_trace_task, _process_evaluation

@pytest.mark.asyncio
@patch("app.workers.tasks.TraceRepository")
@patch("app.workers.tasks.AsyncSessionLocal")
async def test_process_evaluation_success(mock_session_maker, mock_repo_class):
    # Setup mocks
    mock_session = AsyncMock()
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    mock_repo = AsyncMock()
    mock_repo_class.return_value = mock_repo
    
    # Run the inner async function directly
    # Since we have a 10% chance to fail in the code, we patch random to avoid flaky tests
    with patch("app.workers.tasks.random.random", return_value=0.5):
        await _process_evaluation("trace-123")
    
    mock_repo.update_evaluation_report.assert_called_once()
    kwargs = mock_repo.update_evaluation_report.call_args.kwargs
    assert kwargs["trace_id"] == "trace-123"
    assert kwargs["status"] == "SUCCESS"
