import json
import os
from datetime import timedelta
from pathlib import Path

import pytest
from pytest_insight.core.models import TestSession
from pytest_insight.core.storage import InMemoryStorage, JSONStorage, get_storage_instance


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

    # Mock environment variables with a side_effect function to handle different keys
    def mock_environ_get(key, default=None):
        if key == "PYTEST_INSIGHT_DB_PATH":
            return str(tmp_path / "sessions.json")
        elif key == "PYTEST_INSIGHT_PROFILE":
            return None
        else:
            return default

    mocker.patch("os.environ.get", side_effect=mock_environ_get)

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


@pytest.fixture
def profile_manager(tmp_path):
    """Fixture to create a ProfileManager with a temporary config file."""
    from pytest_insight.core.storage import ProfileManager

    config_path = tmp_path / "profiles.json"
    return ProfileManager(config_path=config_path)


class TestStorageProfile:
    """Tests for the StorageProfile class."""

    def test_storage_profile_creation(self):
        """Test creating a StorageProfile."""

        from pytest_insight.core.storage import StorageProfile

        # Create with defaults
        profile = StorageProfile("test-profile")
        assert profile.name == "test-profile"
        assert profile.storage_type == "json"
        expected_path = str(Path.home() / ".pytest_insight" / "test-profile.json")
        assert profile.file_path == expected_path

        # Create with custom values
        profile = StorageProfile("custom", "memory", "/custom/path")
        assert profile.name == "custom"
        assert profile.storage_type == "memory"
        assert profile.file_path == "/custom/path"

    def test_storage_profile_serialization(self):
        """Test serializing and deserializing a StorageProfile."""
        from pytest_insight.core.storage import StorageProfile

        # Create a profile
        profile = StorageProfile("test", "json", "/test/path")

        # Serialize to dict
        profile_dict = profile.to_dict()
        assert profile_dict["name"] == "test"
        assert profile_dict["storage_type"] == "json"
        assert profile_dict["file_path"] == "/test/path"

        # Deserialize from dict
        new_profile = StorageProfile.from_dict(profile_dict)
        assert new_profile.name == "test"
        assert new_profile.storage_type == "json"
        assert new_profile.file_path == "/test/path"


class TestProfileManager:
    """Tests for the ProfileManager class."""

    def test_profile_manager_initialization(self, profile_manager):
        """Test initializing a ProfileManager."""
        # Default profile should be created
        profiles = profile_manager.list_profiles()
        assert "default" in profiles
        assert profile_manager.active_profile_name == "default"

    def test_create_profile(self, profile_manager):
        """Test creating a new profile."""
        # Create a new profile
        profile = profile_manager.create_profile("test", "json", "/test/path")
        assert profile.name == "test"
        assert profile.storage_type == "json"
        assert profile.file_path == "/test/path"

        # Profile should be in the list
        profiles = profile_manager.list_profiles()
        assert "test" in profiles
        assert profiles["test"].file_path == "/test/path"

        # Creating a duplicate profile should raise an error
        with pytest.raises(ValueError, match="Profile 'test' already exists"):
            profile_manager.create_profile("test", "memory")

    def test_get_profile(self, profile_manager):
        """Test getting a profile."""
        # Create a test profile
        profile_manager.create_profile("test", "json", "/test/path")

        # Get by name
        profile = profile_manager.get_profile("test")
        assert profile.name == "test"
        assert profile.file_path == "/test/path"

        # Get active profile
        profile = profile_manager.get_profile()
        assert profile.name == "default"

        # Get non-existent profile
        with pytest.raises(ValueError, match="Profile 'nonexistent' does not exist"):
            profile_manager.get_profile("nonexistent")

    def test_switch_profile(self, profile_manager):
        """Test switching between profiles."""
        # Create test profiles
        profile_manager.create_profile("test1", "json", "/test1/path")
        profile_manager.create_profile("test2", "memory", "/test2/path")

        # Switch to test1
        profile = profile_manager.switch_profile("test1")
        assert profile.name == "test1"
        assert profile_manager.active_profile_name == "test1"
        assert profile_manager.get_active_profile().name == "test1"

        # Switch to test2
        profile = profile_manager.switch_profile("test2")
        assert profile.name == "test2"
        assert profile_manager.active_profile_name == "test2"
        assert profile_manager.get_active_profile().name == "test2"

        # Switch to non-existent profile
        with pytest.raises(ValueError, match="Profile 'nonexistent' does not exist"):
            profile_manager.switch_profile("nonexistent")

    def test_delete_profile(self, profile_manager):
        """Test deleting a profile."""
        # Create test profiles
        profile_manager.create_profile("test1", "json", "/test1/path")
        profile_manager.create_profile("test2", "memory", "/test2/path")

        # Delete test1
        profile_manager.delete_profile("test1")
        profiles = profile_manager.list_profiles()
        assert "test1" not in profiles
        assert "test2" in profiles

        # Cannot delete default profile
        with pytest.raises(ValueError, match="Cannot delete the default profile"):
            profile_manager.delete_profile("default")

        # Switch to test2 and try to delete it
        profile_manager.switch_profile("test2")
        with pytest.raises(ValueError, match="Cannot delete the active profile"):
            profile_manager.delete_profile("test2")

    def test_profile_persistence(self, tmp_path):
        """Test that profiles are persisted to disk."""
        from pytest_insight.core.storage import ProfileManager

        # Create a profile manager and add profiles
        config_path = tmp_path / "profiles.json"
        manager1 = ProfileManager(config_path=config_path)
        manager1.create_profile("test1", "json", "/test1/path")
        manager1.create_profile("test2", "memory", "/test2/path")
        manager1.switch_profile("test1")

        # Create a new profile manager with the same config path
        manager2 = ProfileManager(config_path=config_path)

        # Profiles should be loaded
        profiles = manager2.list_profiles()
        assert "test1" in profiles
        assert "test2" in profiles
        assert profiles["test1"].file_path == "/test1/path"
        assert profiles["test2"].file_path == "/test2/path"
        assert manager2.active_profile_name == "test1"

    def test_env_var_override(self, profile_manager, monkeypatch):
        """Test environment variable override for active profile."""
        # Create test profiles
        profile_manager.create_profile("test1", "json", "/test1/path")
        profile_manager.create_profile("env-profile", "memory", "/env/path")

        # Set environment variable
        monkeypatch.setenv("PYTEST_INSIGHT_PROFILE", "env-profile")

        # Get profile should use env var
        profile = profile_manager.get_profile()
        assert profile.name == "env-profile"

        # Explicit name should override env var
        profile = profile_manager.get_profile("test1")
        assert profile.name == "test1"

        # Non-existent profile in env var
        monkeypatch.setenv("PYTEST_INSIGHT_PROFILE", "nonexistent")
        with pytest.raises(ValueError, match="Profile 'nonexistent' does not exist"):
            profile_manager.get_profile()

    def test_backup_profiles(self, tmp_path):
        """Test creating a backup of profiles."""
        from pytest_insight.core.storage import ProfileManager

        # Create a profile manager with a temporary config
        config_path = tmp_path / "profiles.json"
        manager = ProfileManager(config_path=config_path)

        # Create a profile to have something to backup
        manager.create_profile("test-profile", "json", "/test/path")

        # Create a backup
        backup_path = manager.backup_profiles()
        assert backup_path is not None
        assert backup_path.exists()
        assert "profiles_backup_" in backup_path.name
        assert backup_path.suffix == ".json"

    def test_list_backups(self, tmp_path):
        """Test listing available backups."""
        from pytest_insight.core.storage import ProfileManager

        # Create a profile manager with a temporary config
        config_path = tmp_path / "profiles.json"
        manager = ProfileManager(config_path=config_path)

        # Create multiple backups
        manager.backup_profiles()
        manager.backup_profiles()
        manager.backup_profiles()

        # List backups
        backups = manager.list_backups()

        # Verify backups are listed
        assert backups  # Simplified sequence length comparison

        # Verify backup information
        for backup in backups:
            assert "path" in backup
            assert "timestamp" in backup
            assert "size" in backup
            assert "filename" in backup

    def test_cleanup_old_backups(self, tmp_path):
        """Test cleaning up old backups."""
        from pytest_insight.core.storage import ProfileManager

        # Create a profile manager with a temporary config
        config_path = tmp_path / "profiles.json"
        manager = ProfileManager(config_path=config_path)

        # Create more backups than the max limit
        max_backups = 3

        # Create backups
        for _ in range(max_backups + 5):
            manager.backup_profiles()

        # Clean up old backups with a smaller limit
        manager._cleanup_old_backups(max_backups=max_backups)

        # Verify only max_backups remain
        backup_dir = config_path.parent / "backups"
        backup_files = list(backup_dir.glob("profiles_backup_*.json"))
        assert len(backup_files) <= max_backups

    def test_restore_from_backup(self, tmp_path):
        """Test restoring profiles from a backup."""
        from pytest_insight.core.storage import ProfileManager

        # Create a profile manager with a temporary config
        config_path = tmp_path / "profiles.json"
        manager = ProfileManager(config_path=config_path)

        # Create original profiles
        manager.create_profile("original1", "json", "/original1/path")
        manager.create_profile("original2", "memory")

        # Create a backup
        backup_path = manager.backup_profiles()
        assert backup_path is not None

        # Create new profiles (replacing the originals)
        manager.delete_profile("original1")
        manager.delete_profile("original2")
        manager.create_profile("new_profile", "json", "/new/path")

        # Verify new profile exists and old ones don't
        profiles = manager.list_profiles()
        assert "new_profile" in profiles
        assert "original1" not in profiles
        assert "original2" not in profiles

        # Restore from backup
        success = manager.restore_from_backup(backup_path)
        assert success

        # Verify original profiles are restored
        restored_profiles = manager.list_profiles()
        assert "original1" in restored_profiles
        assert "original2" in restored_profiles
        assert "new_profile" not in restored_profiles

    def test_restore_nonexistent_backup(self, tmp_path):
        """Test restoring from a non-existent backup file."""
        from pytest_insight.core.storage import ProfileManager

        # Create a profile manager with a temporary config
        config_path = tmp_path / "profiles.json"
        manager = ProfileManager(config_path=config_path)

        # Try to restore from a non-existent backup
        non_existent_path = tmp_path / "non_existent_backup.json"
        result = manager.restore_from_backup(non_existent_path)

        # Should return False for failure
        assert result is False

    def test_automatic_backup_on_save(self, tmp_path):
        """Test that backups are automatically created when saving profiles."""
        from pytest_insight.core.storage import ProfileManager

        # Create a profile manager with a temporary config
        config_path = tmp_path / "profiles.json"
        manager = ProfileManager(config_path=config_path)

        # Create a profile to trigger _save_profiles
        manager.create_profile("test_profile", "json", "/test/path")

        # Verify a backup was created
        backup_dir = config_path.parent / "backups"
        backup_files = list(backup_dir.glob("profiles_backup_*.json"))
        assert backup_files  # Simplified sequence length comparison

        # Create another profile to trigger another backup
        manager.create_profile("another_profile", "memory")

        # Verify another backup was created
        backup_files_after = list(backup_dir.glob("profiles_backup_*.json"))
        assert len(backup_files_after) > len(backup_files)  # More backups than before


class TestStorageWithProfiles:
    """Tests for storage integration with profiles."""

    def test_get_storage_instance_with_profile(self, tmp_path, monkeypatch):
        """Test get_storage_instance with profile name."""
        from pytest_insight.core.storage import (
            InMemoryStorage,
            JSONStorage,
            ProfileManager,
            get_storage_instance,
        )

        # Create a profile manager with a temporary config
        config_path = tmp_path / "profiles.json"
        profile_manager = ProfileManager(config_path=config_path)

        # Patch the get_profile_manager function to return our test instance
        monkeypatch.setattr("pytest_insight.core.storage.get_profile_manager", lambda: profile_manager)

        # Create test profiles
        profile_manager.create_profile("json-profile", "json", str(tmp_path / "json-db.json"))
        profile_manager.create_profile("memory-profile", "memory")

        # Get storage with json profile
        storage = get_storage_instance(profile_name="json-profile")
        assert isinstance(storage, JSONStorage)
        assert storage.file_path == tmp_path / "json-db.json"

        # Get storage with memory profile
        storage = get_storage_instance(profile_name="memory-profile")
        assert isinstance(storage, InMemoryStorage)

        # Profile overrides direct parameters
        storage = get_storage_instance(storage_type="memory", profile_name="json-profile")
        assert isinstance(storage, JSONStorage)  # Profile takes precedence

        # Direct parameters used when no profile specified
        storage = get_storage_instance(storage_type="memory")
        assert isinstance(storage, InMemoryStorage)

    def test_env_var_profile_override(self, tmp_path, monkeypatch):
        """Test environment variable override for profile in get_storage_instance."""
        from pytest_insight.core.storage import (
            JSONStorage,
            ProfileManager,
            get_storage_instance,
        )

        # Create a profile manager with a temporary config
        config_path = tmp_path / "profiles.json"
        profile_manager = ProfileManager(config_path=config_path)

        # Patch the get_profile_manager function to return our test instance
        monkeypatch.setattr("pytest_insight.core.storage.get_profile_manager", lambda: profile_manager)

        # Create test profile
        profile_manager.create_profile("env-profile", "json", str(tmp_path / "env-db.json"))

        # Set environment variable
        monkeypatch.setenv("PYTEST_INSIGHT_PROFILE", "env-profile")

        # Get storage should use env profile
        storage = get_storage_instance()
        assert isinstance(storage, JSONStorage)
        assert storage.file_path == tmp_path / "env-db.json"

        # Explicit profile should override env var
        profile_manager.create_profile("explicit-profile", "json", str(tmp_path / "explicit-db.json"))
        storage = get_storage_instance(profile_name="explicit-profile")
        assert storage.file_path == tmp_path / "explicit-db.json"

    def test_convenience_functions(self, tmp_path, monkeypatch):
        """Test convenience functions for profile management."""
        from pytest_insight.core.storage import (
            ProfileManager,
            create_profile,
            get_active_profile,
            list_profiles,
            switch_profile,
        )

        # Create a profile manager with a temporary config
        config_path = tmp_path / "profiles.json"
        profile_manager = ProfileManager(config_path=config_path)

        # Patch the get_profile_manager function to return our test instance
        monkeypatch.setattr("pytest_insight.core.storage.get_profile_manager", lambda: profile_manager)

        # Create profiles using the convenience functions
        # These will use our mocked profile manager
        profile1 = create_profile("profile1", "json", "/profile1/path")
        assert profile1.name == "profile1"

        profile2 = create_profile("profile2", "memory")
        assert profile2.name == "profile2"

        # List profiles
        profiles = list_profiles()
        assert "default" in profiles
        assert "profile1" in profiles
        assert "profile2" in profiles

        # Switch profile
        active = switch_profile("profile1")
        assert active.name == "profile1"

        # Get active profile
        active = get_active_profile()
        assert active.name == "profile1"
