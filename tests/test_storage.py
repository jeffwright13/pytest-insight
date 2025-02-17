from datetime import datetime, timedelta

import pytest

from pytest_insight.models import (
    TestSession,
)
from pytest_insight.storage import (
    InMemoryTestResultStorage,
    JSONTestResultStorage,
    TestSession,
)


@pytest.fixture
def temp_json_file(tmp_path):
    """Create a temporary JSON file for testing."""
    temp_file = tmp_path / "test_sessions.json"
    return temp_file


def test_save_and_load_session(temp_json_file, mocker):
    """Ensure sessions are saved and loaded correctly."""
    mocker.patch.object(JSONTestResultStorage, "FILE_PATH", temp_json_file)
    storage = JSONTestResultStorage()

    session = TestSession(
        sut_name="test_sut",
        session_id="123",
        session_start_time=datetime.utcnow(),
        session_stop_time=datetime.utcnow(),
        test_results=[],
    )

    storage.save_session(session)
    loaded_sessions = storage.load_sessions()

    assert len(loaded_sessions) == 1
    assert loaded_sessions[0].sut_name == "test_sut"


def test_storage_loads_persisted_sessions():
    """Ensure storage correctly retrieves previously saved sessions."""
    storage = InMemoryTestResultStorage()

    session1 = TestSession(
        "SUT-1",
        "session-001",
        datetime.utcnow(),
        datetime.utcnow(),
        timedelta(seconds=120),
    )
    session2 = TestSession(
        "SUT-1",
        "session-002",
        datetime.utcnow(),
        datetime.utcnow(),
        timedelta(seconds=90),
    )

    storage.save_session(session1)
    storage.save_session(session2)

    stored_sessions = storage.load_sessions()
    assert len(stored_sessions) == 2
    assert stored_sessions[0].session_id == "session-001"
    assert stored_sessions[1].session_id == "session-002"

    storage.clear_sessions()
    assert len(storage.load_sessions()) == 0
    assert storage.load_sessions() == []
    assert len(storage.load_sessions()) == 0


def test_storage_saves_sessions():
    """Ensure storage correctly saves and retrieves sessions."""
    storage = InMemoryTestResultStorage()

    session1 = TestSession(
        "SUT-1",
        "session-001",
        datetime.utcnow(),
        datetime.utcnow(),
        timedelta(seconds=120),
    )
    session2 = TestSession(
        "SUT-1",
        "session-002",
        datetime.utcnow(),
        datetime.utcnow(),
        timedelta(seconds=90),
    )
    storage.save_session(session1)
    storage.save_session(session2)
    stored_sessions = storage.load_sessions()
    assert len(stored_sessions) == 2
    assert stored_sessions[0] == session1
    assert stored_sessions[1] == session2
    assert len(storage.load_sessions()) == 2
    assert storage.load_sessions() == [session1, session2]


def test_storage_clears_sessions():
    """Ensure storage correctly clears all stored sessions."""
    storage = InMemoryTestResultStorage()

    session1 = TestSession(
        "SUT-1",
        "session-001",
        datetime.utcnow(),
        datetime.utcnow(),
        timedelta(seconds=120),
    )
    TestSession(
        "SUT-1",
        "session-002",
        datetime.utcnow(),
        datetime.utcnow(),
        timedelta(seconds=90),
    )
    storage.save_session(session1)

    storage.clear_sessions()
    assert len(storage.load_sessions()) == 0
    assert storage.load_sessions() == []


def test_storage_get_last_session():
    """Ensure storage correctly retrieves the most recent session."""
    storage = InMemoryTestResultStorage()

    session1 = TestSession(
        "SUT-1",
        "session-001",
        datetime.utcnow(),
        datetime.utcnow(),
        timedelta(seconds=120),
    )
    session2 = TestSession(
        "SUT-1",
        "session-002",
        datetime.utcnow(),
        datetime.utcnow(),
        timedelta(seconds=90),
    )
    storage.save_session(session1)
    storage.save_session(session2)
    last_session = storage.get_last_session()
    assert last_session == session2
    assert last_session is not None
    assert storage.get_last_session() == session2
    assert storage.get_last_session() is not None

    storage.clear_sessions()
    assert storage.get_last_session() is None


def test_get_session_by_id():
    """Ensure storage correctly retrieves a session by its ID."""
    storage = InMemoryTestResultStorage()

    session1 = TestSession(
        "SUT-1",
        "session-001",
        datetime.utcnow(),
        datetime.utcnow(),
        timedelta(seconds=120),
    )
    session2 = TestSession(
        "SUT-1",
        "session-002",
        datetime.utcnow(),
        datetime.utcnow(),
        timedelta(seconds=90),
    )
    storage.save_session(session1)
    storage.save_session(session2)
    retrieved_session = storage.get_session_by_id("session-001")
    assert retrieved_session == session1
    assert retrieved_session is not None
    assert storage.get_session_by_id("session-001") == session1
    assert storage.get_session_by_id("session-001") is not None
    assert storage.get_session_by_id("session-002") == session2
    assert storage.get_session_by_id("session-002") is not None
    assert storage.get_session_by_id("nonexistent-session") is None


def test_storage_json_saves_sessions():
    """Ensure JSON storage correctly saves and retrieves sessions."""
    JSONTestResultStorage()

    TestSession(
        "SUT-1",
        "session-001",
        datetime.utcnow(),
        datetime.utcnow(),
        timedelta(seconds=120),
    )
