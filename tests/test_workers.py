from unittest.mock import patch

import pytest

from app.domain.models import Event, Report
from app.workers.tasks import process_report_async

pytestmark = pytest.mark.asyncio

@patch("app.workers.tasks.AsyncSessionLocal")
async def test_process_report_async_success(mock_session_factory, db_session):
    """Test the core async logic of the report worker on success."""
    # We patch AsyncSessionLocal inside tasks.py to yield our test db_session
    mock_session_factory.return_value.__aenter__.return_value = db_session
    
    # Setup test data
    task_id = "test_task_123"
    report = Report(id=task_id, status="PENDING")
    
    event1 = Event(user_id="u1", event_type="login", payload={})
    event2 = Event(user_id="u2", event_type="login", payload={})
    
    db_session.add_all([report, event1, event2])
    await db_session.commit()
    
    # Run the worker function
    await process_report_async(task_id)
    
    # Verify the report state in the database
    updated_report = await db_session.get(Report, task_id)
    assert updated_report.status == "SUCCESS"
    assert updated_report.result_summary == {"login": 2}

@patch("app.workers.tasks.AsyncSessionLocal")
async def test_process_report_async_failure(mock_session_factory, db_session):
    """Test the worker correctly updates status to FAILURE when an exception occurs."""
    mock_session_factory.return_value.__aenter__.return_value = db_session
    
    task_id = "test_task_fail"
    report = Report(id=task_id, status="PENDING")
    db_session.add(report)
    await db_session.commit()
    
    # We patch the repository to force an exception
    with patch("app.workers.tasks.ReportRepository.update_report") as mock_update:
        # The first call is to set STARTED, the second sets SUCCESS. 
        # We will make the database throw an error during the aggregation query.
        with patch("app.workers.tasks.select") as mock_select:
            mock_select.side_effect = Exception("Database connection failed")
            
            with pytest.raises(Exception, match="Database connection failed"):
                await process_report_async(task_id)
        
        # Verify it tried to save the failure
        mock_update.assert_called_with(task_id, status="FAILURE", summary={"error": "Database connection failed"})
