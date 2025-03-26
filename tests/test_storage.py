import json
import os
from datetime import timedelta

import pytest
from pytest_insight.models import TestSession
from pytest_insight.storage import InMemoryStorage, JSONStorage, get_storage_instance


@pytest.fixture
def json_storage(tmp_path):
    """Fixture to create a JSONStorage instance with a temporary file."""
    storage_path = tmp_path / "sessions.json"
    return JSONStorage(file_path=storage_path)


@pytest.fixture
def in_memory_storage():
    """Fixture to create an InMemoryStorage instance."""
    return InMemoryStorage()


@pytest.mark.parametrize("storage_class", [InMemoryStorage, JSONStorage])
def test_save_and_load_session(storage_class, tmp_path, test_session_basic):
    """Test saving and loading a session in both storage types."""
    storage = storage_class(tmp_path / "sessions.json") if storage_class == JSONStorage else storage_class()

    assert storage.load_sessions() == []  # Should start empty

    storage.save_session(test_session_basic)
    assert len(storage.load_sessions()) == 1
    assert storage.load_sessions()[0].session_id == "test-123"


def test_clear_sessions_in_memory(in_memory_storage, test_session_basic):
    """Test clearing sessions in InMemoryStorage."""
    in_memory_storage.save_session(test_session_basic)
    assert len(in_memory_storage.load_sessions()) == 1

    in_memory_storage.clear_sessions()
    assert in_memory_storage.load_sessions() == []


def test_clear_sessions_json(json_storage, test_session_basic):
    """Test clearing sessions in JSONStorage."""
    json_storage.save_session(test_session_basic)
    assert len(json_storage.load_sessions()) == 1

    json_storage.clear_sessions()
    assert json_storage.load_sessions() == []


def test_get_last_session(json_storage, test_session_basic):
    """Test retrieving the last session."""
    assert json_storage.get_last_session() is None  # No sessions initially

    json_storage.save_session(test_session_basic)
    assert json_storage.get_last_session().session_id == "test-123"


def test_get_session_by_id(json_storage, test_session_basic):
    """Test retrieving a session by ID."""
    json_storage.save_session(test_session_basic)

    assert json_storage.get_session_by_id("test-123") is not None
    assert json_storage.get_session_by_id("wrong-id") is None


def test_get_storage_instance_json(mocker, tmp_path):
    """Test get_storage_instance correctly returns JSONStorage."""
    mocker.patch("os.environ.get", return_value=str(tmp_path / "sessions.json"))

    storage = get_storage_instance("json")
    assert isinstance(storage, JSONStorage)


def test_jsonstorage_handles_corrupt_data(mocker, json_storage):
    """Test JSONStorage gracefully handles corrupt data."""
    # Mock the _read_json_safely method to raise JSONDecodeError
    mocker.patch.object(
        json_storage,
        "_read_json_safely",
        side_effect=json.JSONDecodeError("Invalid JSON", "", 0),
    )

    # Should return empty list instead of crashing
    assert json_storage.load_sessions() == []


def test_atomic_write_operations(tmp_path, get_test_time):
    """Test atomic write operations using a temporary file."""
    # Create a storage instance
    storage_path = tmp_path / "sessions.json"
    storage = JSONStorage(file_path=storage_path)

    # Mock a test session
    session = TestSession(
        sut_name="atomic-test",
        session_id="atomic-test",
        session_start_time=get_test_time(),
        session_duration=30,
        test_results=[],
    )

    # Save the session
    storage.save_session(session)

    # Verify the file exists and contains valid JSON
    assert storage_path.exists()
    data = json.loads(storage_path.read_text())
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["session_id"] == "atomic-test"

    # Verify no temporary files are left behind
    temp_files = list(tmp_path.glob("tmp*"))
    assert not temp_files


def test_save_sessions_bulk(tmp_path, get_test_time):
    """Test saving multiple sessions at once."""
    # Create a storage instance
    storage_path = tmp_path / "sessions.json"
    storage = JSONStorage(file_path=storage_path)

    # Create multiple test sessions
    sessions = [
        TestSession(
            sut_name=f"bulk-test-{i}",
            session_id=f"bulk-test-{i}",
            session_start_time=get_test_time(i * 600),
            session_duration=30,
            test_results=[],
        )
        for i in range(5)
    ]

    # Save all sessions at once
    storage.save_sessions(sessions)

    # Verify all sessions were saved
    loaded_sessions = storage.load_sessions()
    assert len(loaded_sessions) == 5
    assert {s.session_id for s in loaded_sessions} == {f"bulk-test-{i}" for i in range(5)}


def test_handles_invalid_data_format(mocker, json_storage):
    """Test handling of invalid data format (non-list JSON)."""
    # Mock the _read_json_safely method instead of read_text
    mocker.patch.object(json_storage, "_read_json_safely", return_value={"not": "a list"})

    # Should handle gracefully and return empty list
    assert json_storage.load_sessions() == []


def test_handles_invalid_session_data(mocker, json_storage, get_test_time):
    """Test handling of invalid session data within a valid JSON list."""
    # Create a JSON list with one valid and one invalid session
    timestamp = get_test_time()
    mock_data = [
        {
            "sut_name": "valid",
            "session_id": "valid",
            "session_start_time": timestamp.isoformat(),
            "session_stop_time": (timestamp + timedelta(seconds=30)).isoformat(),
            "session_duration": 30,
            "test_results": [],
        },
        {"invalid_session": "missing required fields"},
    ]

    # Mock the _read_json_safely method
    mocker.patch.object(json_storage, "_read_json_safely", return_value=mock_data)

    # Should load the valid session and skip the invalid one
    sessions = json_storage.load_sessions()
    assert len(sessions) == 1
    assert sessions[0].session_id == "valid"


def test_backup_on_json_decode_error(mocker, tmp_path):
    """Test that a backup is created when JSON decode error occurs."""
    # Create a storage instance with a real file
    storage_path = tmp_path / "corrupt.json"
    storage_path.write_text("{corrupt json")

    storage = JSONStorage(file_path=storage_path)

    # Attempt to load sessions (should create backup)
    sessions = storage.load_sessions()
    assert sessions == []

    # Verify backup file was created
    backup_files = list(tmp_path.glob("*.bak"))
    assert len(backup_files) == 1
    assert backup_files[0].read_text() == "{corrupt json"


def test_clear_method_uses_atomic_operations(mocker, json_storage):
    """Test that clear() method uses atomic operations."""
    # Spy on _write_json_safely
    spy = mocker.spy(json_storage, "_write_json_safely")

    # Call clear
    json_storage.clear()

    # Verify _write_json_safely was called with empty list
    spy.assert_called_once_with([])


def test_concurrent_access_simulation(tmp_path, get_test_time):
    """Simulate concurrent access to the storage file."""
    storage_path = tmp_path / "concurrent.json"
    storage1 = JSONStorage(file_path=storage_path)
    storage2 = JSONStorage(file_path=storage_path)

    # Create test sessions
    session1 = TestSession(
        sut_name="concurrent-1",
        session_id="concurrent-1",
        session_start_time=get_test_time(),
        session_duration=30,
        test_results=[],
    )

    session2 = TestSession(
        sut_name="concurrent-2",
        session_id="concurrent-2",
        session_start_time=get_test_time(1),
        session_duration=30,
        test_results=[],
    )

    # Save sessions from different storage instances
    storage1.save_session(session1)
    storage2.save_session(session2)

    # Both sessions should be saved
    loaded_sessions = storage1.load_sessions()
    assert len(loaded_sessions) == 2
    assert {s.session_id for s in loaded_sessions} == {"concurrent-1", "concurrent-2"}


def test_get_storage_instance_with_env_vars(mocker, tmp_path):
    """Test get_storage_instance with environment variables."""
    # Use tmp_path instead of /custom to avoid permission issues
    custom_path = str(tmp_path / "custom_storage.json")

    # Mock environment variables
    mocker.patch.dict(
        os.environ,
        {"PYTEST_INSIGHT_STORAGE_TYPE": "json", "PYTEST_INSIGHT_DB_PATH": custom_path},
    )

    # Get storage instance
    storage = get_storage_instance()

    # Verify correct type and path
    assert isinstance(storage, JSONStorage)
    assert str(storage.file_path) == custom_path


def test_get_storage_instance_invalid_type():
    """Test get_storage_instance with invalid storage type."""
    with pytest.raises(ValueError, match="Unsupported storage type"):
        get_storage_instance("invalid_type")


def test_selective_clear_sessions_json(json_storage, get_test_time):
    """Test selectively clearing specific sessions in JSONStorage."""
    # Create multiple test sessions
    sessions = []
    for i in range(5):
        session = TestSession(
            sut_name=f"clear-test-{i}",
            session_id=f"clear-test-{i}",
            session_start_time=get_test_time(i * 600),
            session_duration=30,
            test_results=[],
        )
        json_storage.save_session(session)
        sessions.append(session)

    # Verify all sessions were saved
    assert len(json_storage.load_sessions()) == 5

    # Selectively clear sessions 1 and 3
    sessions_to_clear = [sessions[1], sessions[3]]
    removed_count = json_storage.clear_sessions(sessions_to_clear)

    # Verify correct number of sessions were removed
    assert removed_count == 2

    # Verify the right sessions remain
    remaining_sessions = json_storage.load_sessions()
    assert len(remaining_sessions) == 3
    remaining_ids = {s.session_id for s in remaining_sessions}
    assert remaining_ids == {"clear-test-0", "clear-test-2", "clear-test-4"}

    # Clear all remaining sessions
    removed_count = json_storage.clear_sessions()
    assert removed_count == 3
    assert len(json_storage.load_sessions()) == 0


def test_selective_clear_sessions_in_memory(in_memory_storage, get_test_time):
    """Test selectively clearing specific sessions in InMemoryStorage."""
    # Create multiple test sessions
    sessions = []
    for i in range(5):
        session = TestSession(
            sut_name=f"clear-test-{i}",
            session_id=f"clear-test-{i}",
            session_start_time=get_test_time(i * 600),
            session_duration=30,
            test_results=[],
        )
        in_memory_storage.save_session(session)
        sessions.append(session)

    # Verify all sessions were saved
    assert len(in_memory_storage.load_sessions()) == 5

    # Selectively clear sessions 0, 2, and 4
    sessions_to_clear = [sessions[0], sessions[2], sessions[4]]
    removed_count = in_memory_storage.clear_sessions(sessions_to_clear)

    # Verify correct number of sessions were removed
    assert removed_count == 3

    # Verify the right sessions remain
    remaining_sessions = in_memory_storage.load_sessions()
    assert len(remaining_sessions) == 2
    remaining_ids = {s.session_id for s in remaining_sessions}
    assert remaining_ids == {"clear-test-1", "clear-test-3"}
