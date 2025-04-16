import json
import os
from datetime import datetime
from pathlib import Path

import pytest

from pytest_insight.core.models import TestSession
from pytest_insight.core.storage import (
    InMemoryStorage,
    JSONStorage,
    get_storage_instance,
)


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
    storage = (
        storage_class(tmp_path / "sessions.json")
        if storage_class == JSONStorage
        else storage_class()
    )

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
    from pytest_insight.core.storage import ProfileManager

    # Create a profile manager with a test profile
    config_path = tmp_path / "profiles.json"
    profile_manager = ProfileManager(config_path=config_path)

    # Create a test profile
    profile_manager._create_profile(
        "test-profile", "json", str(tmp_path / "sessions.json")
    )

    # Mock get_profile_manager to return our test instance
    mocker.patch(
        "pytest_insight.core.storage.get_profile_manager", return_value=profile_manager
    )

    # Test with profile_name
    storage = get_storage_instance(profile_name="test-profile")
    assert isinstance(storage, JSONStorage)
    assert storage.file_path == tmp_path / "sessions.json"


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
    assert isinstance(data, dict)
    assert "sessions" in data
    assert len(data["sessions"]) == 1
    assert data["sessions"][0]["session_id"] == "atomic-test"

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
    assert {s.session_id for s in loaded_sessions} == {
        f"bulk-test-{i}" for i in range(5)
    }


def test_handles_invalid_data_format(mocker, json_storage):
    """Test handling of invalid data format (non-list JSON)."""
    # Mock the _read_json_safely method instead of read_text
    mocker.patch.object(
        json_storage, "_read_json_safely", return_value={"not": "a list"}
    )

    # Should handle gracefully and return empty list
    assert json_storage.load_sessions() == []


def test_handles_invalid_session_data(mocker, json_storage, get_test_time):
    """Test handling of invalid session data within a valid JSON list."""
    # Create one valid and one invalid session
    valid_session = TestSession(
        sut_name="valid-test",
        session_id="valid-test",
        session_start_time=get_test_time(),
        session_duration=30,
        test_results=[],
    )

    # Write directly to the storage file
    with open(json_storage.file_path, "w") as f:
        json.dump(
            {
                "sessions": [
                    valid_session.to_dict(),
                    {"invalid": "not a valid session"},
                ]
            },
            f,
        )

    # Mock print function to capture error messages
    print_mock = mocker.patch("builtins.print")

    # Should load the valid session and skip the invalid one
    sessions = json_storage.load_sessions()
    assert len(sessions) == 1
    assert sessions[0].session_id == "valid-test"

    # Verify error was printed
    print_mock.assert_any_call(
        mocker.ANY
    )  # Any call with string containing error message


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
    from pytest_insight.core.storage import ProfileManager

    # Create a profile manager with a test profile
    config_path = tmp_path / "profiles.json"
    profile_manager = ProfileManager(config_path=config_path)

    # Create a test profile
    env_profile_name = "env-profile"
    custom_path = str(tmp_path / "custom_storage.json")
    profile_manager._create_profile(env_profile_name, "json", custom_path)

    # Mock get_profile_manager to return our test instance
    mocker.patch(
        "pytest_insight.core.storage.get_profile_manager", return_value=profile_manager
    )

    # Mock environment variable for profile
    mocker.patch.dict(
        os.environ,
        {"PYTEST_INSIGHT_PROFILE": env_profile_name},
    )

    # Get storage instance without specifying profile (should use env var)
    storage = get_storage_instance()

    # Verify correct type and path
    assert isinstance(storage, JSONStorage)
    assert str(storage.file_path) == custom_path


def test_get_storage_instance_invalid_type(mocker, tmp_path):
    """Test get_storage_instance with invalid storage type."""
    from pytest_insight.core.storage import ProfileManager

    # Create a profile manager with a test profile
    config_path = tmp_path / "profiles.json"
    profile_manager = ProfileManager(config_path=config_path)

    # Create a test profile with invalid storage type
    profile_manager._create_profile(
        "invalid-profile", "invalid_type", str(tmp_path / "invalid.json")
    )

    # Mock get_profile_manager to return our test instance
    mocker.patch(
        "pytest_insight.core.storage.get_profile_manager", return_value=profile_manager
    )

    # Mock environment variable to be empty
    mocker.patch.dict("os.environ", {"PYTEST_INSIGHT_PROFILE": ""})

    # Ensure the active profile is set to our invalid profile
    profile_manager.switch_profile("invalid-profile")

    # Should raise ValueError when trying to get storage with invalid profile
    with pytest.raises(ValueError, match="Unsupported storage type"):
        get_storage_instance()


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

        from datetime import datetime

        from pytest_insight.core.storage import StorageProfile

        # Create with defaults
        profile = StorageProfile("test-profile")
        assert profile.name == "test-profile"
        assert profile.storage_type == "json"
        expected_path = str(
            Path.home() / ".pytest_insight" / "profiles" / "test-profile.json"
        )
        assert profile.file_path == expected_path

        # Check timestamp and user fields are set
        assert isinstance(profile.created, datetime)
        assert isinstance(profile.last_modified, datetime)
        assert profile.created_by is not None
        assert profile.last_modified_by is not None
        assert (
            profile.created_by == profile.last_modified_by
        )  # Same user for new profile

        # Create with custom values
        profile = StorageProfile("custom", "memory", "/custom/path")
        assert profile.name == "custom"
        assert profile.storage_type == "memory"
        assert profile.file_path == "/custom/path"

    def test_storage_profile_with_timestamp_and_user_info(self):
        """Test creating a StorageProfile with timestamp and user information."""
        from datetime import datetime

        from pytest_insight.core.storage import StorageProfile

        # Create a profile with custom timestamp and user info
        created = datetime(2025, 1, 1)
        last_modified = datetime(2025, 1, 2)
        created_by = "test-creator"
        last_modified_by = "test-modifier"

        profile = StorageProfile(
            "test-timestamps",
            "json",
            "/test/path",
            created=created,
            last_modified=last_modified,
            created_by=created_by,
            last_modified_by=last_modified_by,
        )

        # Verify values were set correctly
        assert profile.created == created
        assert profile.last_modified == last_modified
        assert profile.created_by == created_by
        assert profile.last_modified_by == last_modified_by

    def test_storage_profile_serialization(self):
        """Test serializing and deserializing a StorageProfile."""
        from datetime import datetime

        from pytest_insight.core.storage import StorageProfile

        # Create a profile with timestamp and user info
        created = datetime(2025, 1, 1)
        last_modified = datetime(2025, 1, 2)
        created_by = "test-creator"
        last_modified_by = "test-modifier"

        profile = StorageProfile(
            "test",
            "json",
            "/test/path",
            created=created,
            last_modified=last_modified,
            created_by=created_by,
            last_modified_by=last_modified_by,
        )

        # Serialize to dict
        profile_dict = profile.to_dict()
        assert profile_dict["name"] == "test"
        assert profile_dict["storage_type"] == "json"
        assert profile_dict["file_path"] == "/test/path"
        assert profile_dict["created"] == created.isoformat()
        assert profile_dict["last_modified"] == last_modified.isoformat()
        assert profile_dict["created_by"] == created_by
        assert profile_dict["last_modified_by"] == last_modified_by

        # Deserialize from dict
        new_profile = StorageProfile.from_dict(profile_dict)
        assert new_profile.name == "test"
        assert new_profile.storage_type == "json"
        assert new_profile.file_path == "/test/path"
        assert new_profile.created == created
        assert new_profile.last_modified == last_modified
        assert new_profile.created_by == created_by
        assert new_profile.last_modified_by == last_modified_by

    def test_storage_profile_backward_compatibility(self):
        """Test backward compatibility with profiles that have old field names."""
        from datetime import datetime

        from pytest_insight.core.storage import StorageProfile

        # Create a profile dict with the old field name (last_modified instead of last_modified)
        created_at_str = "2025-01-01T00:00:00"
        last_modified_str = "2025-01-02T00:00:00"

        profile_dict = {
            "name": "legacy-profile",
            "storage_type": "json",
            "file_path": "/legacy/path",
            "created": created_at_str,
            "last_modified": last_modified_str,  # Old field name
            "created_by": "test-creator",
            # Missing last_modified_by
        }

        # Deserialize from dict
        profile = StorageProfile.from_dict(profile_dict)

        # Verify fields were correctly mapped
        assert profile.name == "legacy-profile"
        assert profile.storage_type == "json"
        assert profile.file_path == "/legacy/path"
        assert isinstance(profile.created, datetime)
        assert isinstance(profile.last_modified, datetime)
        assert profile.created.isoformat() == created_at_str
        assert profile.last_modified.isoformat() == last_modified_str
        assert profile.created_by == "test-creator"
        assert profile.last_modified_by is not None  # Should be set to default value


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
        profile = profile_manager._create_profile("test", "json", "/test/path")
        assert profile.name == "test"
        assert profile.storage_type == "json"
        assert profile.file_path == "/test/path"

        # Profile should be in the list
        profiles = profile_manager.list_profiles()
        assert "test" in profiles
        assert profiles["test"].file_path == "/test/path"

        # Creating a duplicate profile should raise an error
        with pytest.raises(ValueError, match="Profile 'test' already exists"):
            profile_manager._create_profile("test", "memory")

    def test_get_profile(self, profile_manager):
        """Test getting a profile."""
        # Create a test profile
        profile_manager._create_profile("test", "json", "/test/path")

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
        profile_manager._create_profile("test1", "json", "/test1/path")
        profile_manager._create_profile("test2", "memory", "/test2/path")

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
        profile_manager._create_profile("test1", "json", "/test1/path")
        profile_manager._create_profile("test2", "memory", "/test2/path")

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
        manager1._create_profile("test1", "json", "/test1/path")
        manager1._create_profile("test2", "memory", "/test2/path")
        manager1.switch_profile("test1")

        # Create a new profile manager with the same config path
        manager2 = ProfileManager(config_path=config_path)

        # Verify that the JSON profile was loaded
        profiles = manager2.list_profiles()
        assert "test1" in profiles
        assert profiles["test1"].storage_type == "json"
        assert profiles["test1"].file_path == "/test1/path"

        # Memory profiles are not persisted, so test2 should not be in the loaded profiles
        assert "test2" not in profiles

        # Verify active profile was persisted
        assert manager2.get_active_profile().name == "test1"

    def test_env_var_override(self, profile_manager, monkeypatch):
        """Test environment variable override for active profile."""
        # Create test profiles
        profile_manager._create_profile("test1", "json", "/test1/path")
        profile_manager._create_profile("env-profile", "memory", "/env/path")

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
        manager._create_profile("test-profile", "json", "/test/path")

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
        manager._create_profile("original1", "json", "/original1/path")
        manager._create_profile("original2", "memory")

        # Create a backup
        backup_path = manager.backup_profiles()
        assert backup_path is not None

        # Create new profiles (replacing the originals)
        manager.delete_profile("original1")
        manager.delete_profile("original2")
        manager._create_profile("new_profile", "json", "/new/path")

        # Verify new profile exists and old ones don't
        profiles = manager.list_profiles()
        assert "new_profile" in profiles
        assert "original1" not in profiles
        assert "original2" not in profiles

        # Restore from backup
        success = manager.restore_from_backup(backup_path)
        assert success

        # Verify original JSON profile is restored
        # Memory profiles are not persisted in backups, so original2 won't be restored
        restored_profiles = manager.list_profiles()
        assert "original1" in restored_profiles
        assert "original2" not in restored_profiles  # Memory profiles are not persisted
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
        manager._create_profile("test_profile", "json", "/test/path")

        # Verify a backup was created
        backup_dir = config_path.parent / "backups"
        backup_files = list(backup_dir.glob("profiles_backup_*.json"))
        assert backup_files  # Simplified sequence length comparison

        # Create another profile to trigger another backup
        manager._create_profile("another_profile", "memory")

        # Verify another backup was created
        backup_files_after = list(backup_dir.glob("profiles_backup_*.json"))
        assert len(backup_files_after) > len(backup_files)  # More backups than before

    def test_memory_profiles_not_persisted(self, tmp_path):
        """Test that in-memory profiles are not persisted to the configuration file."""
        from pytest_insight.core.storage import ProfileManager

        # Create a profile manager with a test config file
        config_path = tmp_path / "profiles.json"
        profile_manager = ProfileManager(config_path=config_path)

        # Create a JSON profile (should be persisted)
        json_profile_name = "test-json-profile"
        profile_manager._create_profile(
            json_profile_name, "json", str(tmp_path / "json-sessions.json")
        )

        # Create an in-memory profile (should not be persisted)
        memory_profile_name = "test-memory-profile"
        profile_manager._create_profile(memory_profile_name, "memory")

        # Verify both profiles are available during the session
        assert profile_manager.get_profile(json_profile_name) is not None
        assert profile_manager.get_profile(memory_profile_name) is not None

        # Create a new profile manager instance that reads from the same config file
        # This simulates restarting the application
        new_profile_manager = ProfileManager(config_path=config_path)

        # Verify the JSON profile was persisted
        assert json_profile_name in new_profile_manager.profiles

        # Verify the in-memory profile was NOT persisted
        assert memory_profile_name not in new_profile_manager.profiles

    def test_list_profiles_with_type_filter(self, tmp_path):
        """Test filtering profiles by storage type."""
        from pytest_insight.core.storage import ProfileManager

        # Create a profile manager with a test config file
        config_path = tmp_path / "profiles.json"
        profile_manager = ProfileManager(config_path=config_path)

        # Create profiles with different storage types
        profile_manager._create_profile(
            "json-profile-1", "json", str(tmp_path / "json1.json")
        )
        profile_manager._create_profile(
            "json-profile-2", "json", str(tmp_path / "json2.json")
        )
        profile_manager._create_profile("memory-profile-1", "memory")
        profile_manager._create_profile("memory-profile-2", "memory")

        # Test filtering by JSON type
        json_profiles = profile_manager.list_profiles(storage_type="json")
        # Note: There's a default profile with storage_type="json" that's created automatically
        assert "default" in json_profiles
        assert "json-profile-1" in json_profiles
        assert "json-profile-2" in json_profiles
        assert "memory-profile-1" not in json_profiles
        assert "memory-profile-2" not in json_profiles

        # Test filtering by memory type
        memory_profiles = profile_manager.list_profiles(storage_type="memory")
        assert len(memory_profiles) == 2
        assert "memory-profile-1" in memory_profiles
        assert "memory-profile-2" in memory_profiles
        assert "json-profile-1" not in memory_profiles
        assert "json-profile-2" not in memory_profiles
        assert "default" not in memory_profiles

    def test_list_profiles_with_pattern_filter(self, tmp_path):
        """Test filtering profiles by name pattern."""
        from pytest_insight.core.storage import ProfileManager

        # Create a profile manager with a test config file
        config_path = tmp_path / "profiles.json"
        profile_manager = ProfileManager(config_path=config_path)

        # Create profiles with different name patterns
        profile_manager._create_profile(
            "test-abc-1", "json", str(tmp_path / "abc1.json")
        )
        profile_manager._create_profile(
            "test-abc-2", "json", str(tmp_path / "abc2.json")
        )
        profile_manager._create_profile(
            "test-xyz-1", "json", str(tmp_path / "xyz1.json")
        )
        profile_manager._create_profile(
            "other-profile", "json", str(tmp_path / "other.json")
        )

        # Test filtering by pattern
        abc_profiles = profile_manager.list_profiles(pattern="test-abc*")
        assert len(abc_profiles) == 2
        assert "test-abc-1" in abc_profiles
        assert "test-abc-2" in abc_profiles
        assert "test-xyz-1" not in abc_profiles
        assert "other-profile" not in abc_profiles

        # Test filtering by more specific pattern
        specific_profiles = profile_manager.list_profiles(pattern="test-abc-1")
        assert len(specific_profiles) == 1
        assert "test-abc-1" in specific_profiles
        assert "test-abc-2" not in specific_profiles

        # Test filtering by combined pattern
        test_profiles = profile_manager.list_profiles(pattern="test-*")
        assert len(test_profiles) == 3
        assert "test-abc-1" in test_profiles
        assert "test-abc-2" in test_profiles
        assert "test-xyz-1" in test_profiles
        assert "other-profile" not in test_profiles

    def test_bulk_delete_profiles(self, tmp_path):
        """Test bulk deletion of profiles by type and pattern."""
        from pytest_insight.core.storage import ProfileManager

        # Create a profile manager with a test config file
        config_path = tmp_path / "profiles.json"
        profile_manager = ProfileManager(config_path=config_path)

        # Create various profiles for testing bulk deletion
        profile_manager._create_profile(
            "active-profile", "json", str(tmp_path / "active.json")
        )
        profile_manager._create_profile(
            "json-test-1", "json", str(tmp_path / "json1.json")
        )
        profile_manager._create_profile(
            "json-test-2", "json", str(tmp_path / "json2.json")
        )
        profile_manager._create_profile("memory-test-1", "memory")
        profile_manager._create_profile("memory-test-2", "memory")
        profile_manager._create_profile("memory-other", "memory")

        # Set the active profile
        profile_manager.switch_profile("active-profile")

        # Test bulk deletion of memory profiles
        memory_profiles_before = profile_manager.list_profiles(storage_type="memory")
        assert len(memory_profiles_before) == 3

        # Delete all memory profiles
        deleted_memory = []
        for name in list(memory_profiles_before.keys()):
            try:
                profile_manager.delete_profile(name)
                deleted_memory.append(name)
            except ValueError:
                # Skip active profile
                pass

        memory_profiles_after = profile_manager.list_profiles(storage_type="memory")
        assert len(memory_profiles_after) == 0
        assert "memory-test-1" in deleted_memory
        assert "memory-test-2" in deleted_memory
        assert "memory-other" in deleted_memory

        # Test bulk deletion by pattern
        json_test_profiles_before = profile_manager.list_profiles(
            storage_type="json", pattern="json-test*"
        )
        assert len(json_test_profiles_before) == 2

        # Delete JSON profiles matching pattern
        deleted_json = []
        for name in list(json_test_profiles_before.keys()):
            try:
                profile_manager.delete_profile(name)
                deleted_json.append(name)
            except ValueError:
                # Skip active profile
                pass

        json_test_profiles_after = profile_manager.list_profiles(
            storage_type="json", pattern="json-test*"
        )
        assert len(json_test_profiles_after) == 0
        assert "json-test-1" in deleted_json
        assert "json-test-2" in deleted_json

        # Verify active profile is still there
        assert "active-profile" in profile_manager.profiles

        # Verify attempting to delete active profile raises error
        with pytest.raises(ValueError, match="Cannot delete the active profile"):
            profile_manager.delete_profile("active-profile")


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
        monkeypatch.setattr(
            "pytest_insight.core.storage.get_profile_manager", lambda: profile_manager
        )

        # Create test profiles
        profile_manager._create_profile(
            "json-profile", "json", str(tmp_path / "json-db.json")
        )
        profile_manager._create_profile("memory-profile", "memory")

        # Get storage with json profile
        storage = get_storage_instance(profile_name="json-profile")
        assert isinstance(storage, JSONStorage)
        assert storage.file_path == tmp_path / "json-db.json"

        # Get storage with memory profile
        storage = get_storage_instance(profile_name="memory-profile")
        assert isinstance(storage, InMemoryStorage)

        # Get default storage when no profile specified (should use default profile)
        # First, ensure default profile exists with json storage
        if "default" not in profile_manager.list_profiles():
            profile_manager._create_profile(
                "default", "json", str(tmp_path / "default-db.json")
            )
        else:
            # Update the default profile to use our test path
            default_profile = profile_manager.get_profile("default")
            default_profile.file_path = str(tmp_path / "default-db.json")
            profile_manager._save_profiles()

        # Make default the active profile
        profile_manager.switch_profile("default")

        storage = get_storage_instance()
        assert isinstance(storage, JSONStorage)
        assert Path(storage.file_path) == tmp_path / "default-db.json"

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
        monkeypatch.setattr(
            "pytest_insight.core.storage.get_profile_manager", lambda: profile_manager
        )

        # Create test profile
        profile_manager._create_profile(
            "env-profile", "json", str(tmp_path / "env-db.json")
        )

        # Set environment variable
        monkeypatch.setenv("PYTEST_INSIGHT_PROFILE", "env-profile")

        # Get storage should use env profile
        storage = get_storage_instance()
        assert isinstance(storage, JSONStorage)
        assert storage.file_path == tmp_path / "env-db.json"

        # Explicit profile should override env var
        profile_manager._create_profile(
            "explicit-profile", "json", str(tmp_path / "explicit-db.json")
        )
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
        monkeypatch.setattr(
            "pytest_insight.core.storage.get_profile_manager", lambda: profile_manager
        )

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


def test_load_sessions(mocker, tmp_path, get_test_time):
    """Test loading sessions."""
    # Create a storage instance
    storage_path = tmp_path / "sessions.json"
    storage = JSONStorage(file_path=storage_path)

    # Create test sessions
    sessions = []
    for i in range(3):
        session = TestSession(
            sut_name=f"test-{i}",
            session_id=f"test-{i}",
            session_start_time=get_test_time(i * 600),
            session_duration=30,
            test_results=[],
        )
        sessions.append(session)

    # Save sessions directly to the storage file
    with open(storage_path, "w") as f:
        json.dump(
            {
                "sessions": [s.to_dict() for s in sessions],
            },
            f,
        )

    # Load sessions
    loaded_sessions = storage.load_sessions()

    # Verify all sessions were loaded
    assert len(loaded_sessions) == 3
    assert {s.session_id for s in loaded_sessions} == {f"test-{i}" for i in range(3)}


def test_load_sessions_streaming(mocker, tmp_path, get_test_time):
    """Test loading sessions with streaming parser."""
    import importlib.util

    if importlib.util.find_spec("ijson") is None:
        pytest.skip("ijson not available, skipping streaming test")

    # Create a storage instance
    storage_path = tmp_path / "sessions.json"
    storage = JSONStorage(file_path=storage_path)

    # Create test sessions
    sessions = []
    for i in range(5):
        session = TestSession(
            sut_name=f"streaming-test-{i}",
            session_id=f"streaming-test-{i}",
            session_start_time=get_test_time(i * 600),
            session_duration=30,
            test_results=[],
        )
        sessions.append(session)

    # Save sessions directly using _write_json_safely
    storage._write_json_safely({"sessions": [s.to_dict() for s in sessions]})

    # Mock the _load_sessions_streaming method to ensure it's called
    streaming_mock = mocker.patch.object(
        storage, "_load_sessions_streaming", return_value=sessions
    )

    # Load sessions with streaming
    loaded_sessions = storage.load_sessions(use_streaming=True)

    # Verify streaming method was called
    streaming_mock.assert_called_once_with(1000)

    # Verify all sessions were loaded
    assert len(loaded_sessions) == 5
    assert {s.session_id for s in loaded_sessions} == {
        f"streaming-test-{i}" for i in range(5)
    }


def test_load_sessions_with_invalid_session_data(mocker, tmp_path):
    """Test loading sessions with some invalid session data."""
    # Create a storage instance
    storage_path = tmp_path / "sessions.json"
    storage = JSONStorage(file_path=storage_path)

    # Create test data with one valid and one invalid session
    sessions_data = {
        "sessions": [
            {
                "sut_name": "valid-session",
                "session_id": "valid-session",
                "session_start_time": "2023-01-01T00:00:00+00:00",
                "session_stop_time": "2023-01-01T00:00:30+00:00",
                "session_duration": 30,
                "test_results": [],
            },
            {
                "invalid_session": "missing required fields",
            },
        ]
    }

    # Save sessions directly
    with open(storage_path, "w") as f:
        json.dump(sessions_data, f)

    # Capture print output
    print_mock = mocker.patch("builtins.print")

    # Load sessions
    loaded_sessions = storage.load_sessions()

    # Verify only valid session was loaded
    assert len(loaded_sessions) == 1
    assert loaded_sessions[0].session_id == "valid-session"

    # Verify error was printed
    print_mock.assert_any_call(
        mocker.ANY
    )  # Any call with string containing error message


def test_load_sessions_fallback_when_ijson_not_available(
    mocker, tmp_path, get_test_time
):
    """Test fallback to standard loading when ijson is not available."""
    # Create a storage instance
    storage_path = tmp_path / "sessions.json"
    storage = JSONStorage(file_path=storage_path)

    # Create test sessions
    sessions = []
    for i in range(3):
        session = TestSession(
            sut_name=f"fallback-test-{i}",
            session_id=f"fallback-test-{i}",
            session_start_time=get_test_time(i * 600),
            session_duration=30,
            test_results=[],
        )
        sessions.append(session)

    # Save sessions directly to the file
    session_data = {"sessions": [s.to_dict() for s in sessions]}
    with open(storage_path, "w") as f:
        json.dump(session_data, f)

    # Mock importlib.util.find_spec to simulate ijson not being available
    mocker.patch("importlib.util.find_spec", return_value=None)

    # Mock print function to capture warnings
    warning_mock = mocker.patch("builtins.print")

    # Try to load sessions with streaming (should fall back to regular loading)
    loaded_sessions = storage.load_sessions(use_streaming=True)

    # Verify warning was printed
    warning_mock.assert_any_call(
        "Warning: ijson not installed. Falling back to standard JSON loading."
    )

    # Verify all sessions were loaded correctly using the fallback method
    assert len(loaded_sessions) == 3
    assert {s.session_id for s in loaded_sessions} == {
        f"fallback-test-{i}" for i in range(3)
    }


def test_get_profile_metadata(tmp_path):
    """Test retrieving profile metadata."""
    from pytest_insight.core.storage import (
        ProfileManager,
        StorageProfile,
        get_profile_metadata,
    )

    # Create a profile manager with a test config file
    config_path = tmp_path / "profiles.json"
    profile_manager = ProfileManager(config_path=config_path)

    # Create test profiles with timestamp and user info
    profile1 = StorageProfile(
        "profile1",
        "json",
        str(tmp_path / "profile1.json"),
        created=datetime(2025, 1, 1),
        last_modified=datetime(2025, 1, 2),
        created_by="creator1",
        last_modified_by="modifier1",
    )

    profile2 = StorageProfile(
        "profile2",
        "json",
        str(tmp_path / "profile2.json"),
        created=datetime(2025, 1, 3),
        last_modified=datetime(2025, 1, 4),
        created_by="creator2",
        last_modified_by="modifier2",
    )

    # Add profiles to manager
    profile_manager.profiles = {"profile1": profile1, "profile2": profile2}
    profile_manager.active_profile_name = "profile1"

    # Save profiles to disk
    profile_manager._save_profiles()

    # Mock get_profile_manager to return our test instance
    from unittest.mock import patch

    with patch(
        "pytest_insight.core.storage.get_profile_manager", return_value=profile_manager
    ):
        # Test getting metadata for all profiles
        all_metadata = get_profile_metadata()

        assert all_metadata["active_profile"] == "profile1"
        assert all_metadata["profiles_count"] == 2
        assert "last_modified" in all_metadata
        assert "modified_by" in all_metadata

        # Check profile1 metadata
        profile1_data = all_metadata["profiles"]["profile1"]
        assert profile1_data["storage_type"] == "json"
        assert isinstance(profile1_data["created"], datetime)
        assert isinstance(profile1_data["last_modified"], datetime)
        assert profile1_data["created_by"] == "creator1"
        # The last_modified_by will be updated to the current user by _save_profiles
        # So we should not expect it to be "modifier1" anymore

        # Check profile2 metadata
        profile2_data = all_metadata["profiles"]["profile2"]
        assert profile2_data["storage_type"] == "json"
        assert isinstance(profile2_data["created"], datetime)
        assert isinstance(profile2_data["last_modified"], datetime)
        assert profile2_data["created_by"] == "creator2"
        # The last_modified_by will be updated to the current user by _save_profiles
        # So we should not expect it to be "modifier2" anymore

        # Test getting metadata for a specific profile
        profile1_metadata = get_profile_metadata("profile1")

        assert profile1_metadata["active_profile"] == "profile1"
        assert "profile" in profile1_metadata
        assert profile1_metadata["profile"]["name"] == "profile1"
        assert profile1_metadata["profile"]["storage_type"] == "json"
        assert isinstance(profile1_metadata["profile"]["created"], datetime)
        assert isinstance(profile1_metadata["profile"]["last_modified"], datetime)
        assert profile1_metadata["profile"]["created_by"] == "creator1"
        # The last_modified_by will be updated to the current user by _save_profiles
        # So we should not expect it to be "modifier1" anymore

        # Test getting metadata for a non-existent profile
        nonexistent_metadata = get_profile_metadata("nonexistent")
        assert "error" in nonexistent_metadata
