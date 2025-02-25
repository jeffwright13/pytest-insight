import shutil
from datetime import datetime

from pytest_insight.models import TestSession
from pytest_insight.storage import InMemoryStorage


# ✅ Test: Saving and Loading Sessions (JSON)
def test_save_and_load_session(json_storage, mock_session_no_reruns):
    """Ensure sessions are saved and loaded correctly."""
    json_storage.save_session(mock_session_w_reruns)
    loaded_sessions = json_storage.load_sessions()

    assert len(loaded_sessions) == 1
    assert loaded_sessions[0].sut_name == "test_sut"
    assert loaded_sessions[0].session_id == "123"


def test_save_and_load_session(json_storage, mock_session_w_reruns):
    """Ensure sessions are saved and loaded correctly."""
    json_storage.save_session(mock_session_w_reruns)
    loaded_sessions = json_storage.load_sessions()

    assert len(loaded_sessions) == 1
    assert loaded_sessions[0].sut_name == "test-sut"  # Updated to match mock
    assert loaded_sessions[0].session_id == "test-session-123"  # Updated to match mock


# ✅ Test: InMemory Storage Works Correctly
def test_storage_saves_sessions():
    """Ensure in-memory storage correctly saves and retrieves sessions."""
    storage = InMemoryStorage()
    session1 = TestSession("SUT-1", "session-001", datetime.utcnow(), datetime.utcnow())
    session2 = TestSession("SUT-1", "session-002", datetime.utcnow(), datetime.utcnow())

    storage.save_session(session1)
    storage.save_session(session2)

    stored_sessions = storage.load_sessions()
    assert len(stored_sessions) == 2
    assert stored_sessions[0] == session1
    assert stored_sessions[1] == session2


# ✅ Test: Clearing Sessions
def test_storage_clears_sessions():
    """Ensure storage correctly clears all stored sessions."""
    storage = InMemoryStorage()
    session = TestSession("SUT-1", "session-001", datetime.utcnow(), datetime.utcnow())
    storage.save_session(session)

    storage.clear_sessions()
    assert storage.load_sessions() == []


# ✅ Test: Retrieving the Last Session
def test_storage_get_last_session():
    """Ensure storage correctly retrieves the most recent session."""
    storage = InMemoryStorage()
    session1 = TestSession("SUT-1", "session-001", datetime.utcnow(), datetime.utcnow())
    session2 = TestSession("SUT-1", "session-002", datetime.utcnow(), datetime.utcnow())

    storage.save_session(session1)
    storage.save_session(session2)

    assert storage.get_last_session() == session2
    storage.clear_sessions()
    assert storage.get_last_session() is None


# ✅ Test: Retrieving a Session by ID
def test_get_session_by_id():
    """Ensure storage correctly retrieves a session by its ID."""
    storage = InMemoryStorage()
    session1 = TestSession("SUT-1", "session-001", datetime.utcnow(), datetime.utcnow())
    session2 = TestSession("SUT-1", "session-002", datetime.utcnow(), datetime.utcnow())

    storage.save_session(session1)
    storage.save_session(session2)

    assert storage.get_session_by_id("session-001") == session1
    assert storage.get_session_by_id("session-002") == session2
    assert storage.get_session_by_id("nonexistent") is None


# ✅ Test: Handling Corrupt JSON Files
def test_json_storage_corrupt_file(json_storage, temp_json_file):
    """Ensure JSON storage detects and handles corrupt files correctly."""
    # Write invalid JSON content to simulate corruption
    temp_json_file.write_text("{invalid_json: True}")

    # Load sessions (should trigger error handling)
    sessions = json_storage.load_sessions()
    assert sessions == []  # Should return an empty list


# ✅ Test: Backup Recovery from Corrupt JSON
def test_json_storage_recovers_from_backup(json_storage, temp_json_file, mock_session_w_reruns, mocker):
    """Ensure storage recovers data from the backup file if corruption is detected."""

    backup_file = temp_json_file.with_suffix(".backup")
    mocker.patch("pytest_insight.storage.JSONStorage.BACKUP_PATH", new=backup_file)

    # Step 1: Save a valid session
    json_storage.save_session(mock_session_w_reruns)

    # Step 2: Manually create a backup
    shutil.copy(temp_json_file, backup_file)

    assert backup_file.exists(), "Backup file should exist before corruption"

    # Step 3: Corrupt the main file
    temp_json_file.write_text("{invalid_json: True}")

    # Step 4: Attempt to load (should recover from backup)
    recovered_sessions = json_storage.load_sessions()

    assert len(recovered_sessions) == 1, "Should recover one session from backup"
    recovered = recovered_sessions[0]
    assert recovered.sut_name == "test-sut"
    assert recovered.session_id == "test-session-123"

    # Cleanup
    backup_file.unlink(missing_ok=True)


# ✅ Test: JSON File Locking Works Correctly
def test_json_file_locking(json_storage, temp_json_file, mock_session_w_reruns, mocker):
    """Ensure JSON file locking prevents concurrent write issues."""
    mock_flock = mocker.patch("fcntl.flock")

    json_storage.save_session(mock_session_w_reruns)
    json_storage.load_sessions()

    # Ensure fcntl.flock was called for locking/unlocking
    assert mock_flock.call_count >= 2  # Should be at least one lock for read, one for write


def test_json_storage_handles_empty_file(json_storage, temp_json_file):
    """Ensure JSON storage handles empty files gracefully."""
    temp_json_file.write_text("")  # Create an empty file
    sessions = json_storage.load_sessions()
    assert sessions == []  # Should return an empty list
    assert not temp_json_file.exists()  # Ensure the empty file is deleted
    assert not json_storage.BACKUP_PATH.exists()  # Ensure no backup is created


# ✅ Test: JSON Storage Handles Non-List JSON
def test_json_storage_handles_non_list_json(json_storage, temp_json_file):
    """Ensure JSON storage handles non-list JSON content gracefully."""
    temp_json_file.write_text('{"key": "value"}')
    sessions = json_storage.load_sessions()
    assert sessions == []  # This is correct - invalid format returns empty list
    assert temp_json_file.exists()  # File isn't deleted, just ignored


# ✅ Test: JSON Storage Handles Non-Dict List Items
def test_json_storage_handles_non_dict_list_items(json_storage, temp_json_file):
    """Ensure JSON storage handles lists with non-dict items gracefully."""
    temp_json_file.write_text("[1, 2, 3]")
    sessions = json_storage.load_sessions()
    assert sessions == []  # Non-dict items are filtered out
    assert temp_json_file.exists()  # File isn't deleted


# ✅ Test: JSON Storage Handles sessions w/o RerunTestGroup
def test_json_storage_handles_sessions_without_rerun_groups(json_storage, temp_json_file, mock_session_no_reruns):
    """Ensure JSON storage handles sessions without RerunTestGroup gracefully."""
    temp_json_file.write_text("[1, 2, 3]")  # Create a list of non-dict items
    json_storage.save_session(mock_session_no_reruns)
    sessions = json_storage.load_sessions()
    assert len(sessions) == 1
    assert temp_json_file.exists()


# ✅ Test: JSON Storage Handles sessions w/ RerunTestGroup
def test_json_storage_handles_sessions_with_rerun_groups(json_storage, temp_json_file, mock_session_w_reruns):
    """Ensure JSON storage handles sessions with RerunTestGroup gracefully."""
    json_storage.save_session(mock_session_w_reruns)
    sessions = json_storage.load_sessions()
    assert len(sessions) == 1  # Only one session is saved
    assert sessions[0].sut_name == "test-sut"
