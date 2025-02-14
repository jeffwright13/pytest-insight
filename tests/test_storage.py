from datetime import datetime, timedelta

from pytest_insight.models import (
    TestSession,
)
from pytest_insight.storage import InMemoryTestResultStorage


def test_storage_loads_persisted_sessions():
    """Ensure storage correctly retrieves previously saved sessions."""
    storage = InMemoryTestResultStorage()

    session1 = TestSession("SUT-1", "session-001", datetime.utcnow(), datetime.utcnow(), timedelta(seconds=120))
    session2 = TestSession("SUT-1", "session-002", datetime.utcnow(), datetime.utcnow(), timedelta(seconds=90))

    storage.save_session(session1)
    storage.save_session(session2)

    stored_sessions = storage.load_sessions()
    assert len(stored_sessions) == 2
    assert stored_sessions[0].session_id == "session-001"
    assert stored_sessions[1].session_id == "session-002"
