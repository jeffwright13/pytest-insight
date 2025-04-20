import pytest

pytestmark = pytest.mark.skip(reason="storage not implemented")

import json
import os

import pytest
from pytest_insight.utils.test_data import random_test_session, random_test_sessions


@pytest.fixture
def temp_json_storage(tmp_path):
    """Fixture: JSONStorage with a temporary file."""
    storage_path = tmp_path / "sessions.json"
    return JSONStorage(file_path=storage_path)


@pytest.fixture
def temp_in_memory_storage():
    """Fixture: InMemoryStorage instance."""
    return InMemoryStorage()


@pytest.fixture
def basic_test_session():
    """Fixture: A valid random TestSession object."""
    return random_test_session()


@pytest.fixture
def many_test_sessions():
    """Fixture: List of valid random TestSession objects."""
    return random_test_sessions(3)


def test_save_and_load_session_json(temp_json_storage, basic_test_session):
    """Test saving and loading a session in JSONStorage."""
    storage = temp_json_storage
    assert storage.load_sessions() == []
    storage.save_session(basic_test_session)
    loaded = storage.load_sessions()
    assert len(loaded) == 1
    assert loaded[0].session_id == basic_test_session.session_id


def test_save_and_load_session_memory(temp_in_memory_storage, basic_test_session):
    """Test saving and loading a session in InMemoryStorage."""
    storage = temp_in_memory_storage
    assert storage.load_sessions() == []
    storage.save_session(basic_test_session)
    loaded = storage.load_sessions()
    assert len(loaded) == 1
    assert loaded[0].session_id == basic_test_session.session_id


def test_clear_sessions_json(temp_json_storage, basic_test_session):
    """Test clearing sessions in JSONStorage."""
    storage = temp_json_storage
    storage.save_session(basic_test_session)
    assert len(storage.load_sessions()) == 1
    storage.clear_sessions()
    assert storage.load_sessions() == []


def test_clear_sessions_memory(temp_in_memory_storage, basic_test_session):
    """Test clearing sessions in InMemoryStorage."""
    storage = temp_in_memory_storage
    storage.save_session(basic_test_session)
    assert len(storage.load_sessions()) == 1
    storage.clear_sessions()
    assert storage.load_sessions() == []


def test_get_last_session_json(temp_json_storage, basic_test_session):
    """Test retrieving the last session in JSONStorage."""
    storage = temp_json_storage
    assert storage.get_last_session() is None
    storage.save_session(basic_test_session)
    assert storage.get_last_session().session_id == basic_test_session.session_id


def test_get_session_by_id_json(temp_json_storage, basic_test_session):
    """Test retrieving a session by ID in JSONStorage."""
    storage = temp_json_storage
    storage.save_session(basic_test_session)
    assert storage.get_session_by_id(basic_test_session.session_id) is not None
    assert storage.get_session_by_id("nonexistent") is None


def test_get_storage_instance_json(monkeypatch, tmp_path, basic_test_session):
    """Test get_storage_instance returns JSONStorage for a profile."""
    config_path = tmp_path / "profiles.json"
    profile_manager = ProfileManager(config_path=config_path)
    profile_manager._create_profile("test-profile", "json", str(tmp_path / "sessions.json"))
    monkeypatch.setattr("pytest_insight.storage.get_profile_manager", lambda: profile_manager)
    storage = get_storage_instance(profile_name="test-profile")
    assert isinstance(storage, JSONStorage)
    assert str(storage.file_path) == str(tmp_path / "sessions.json")


def test_jsonstorage_handles_corrupt_data(monkeypatch, temp_json_storage):
    """Test JSONStorage handles corrupt JSON gracefully."""
    storage = temp_json_storage
    # Write invalid JSON
    with open(storage.file_path, "w") as f:
        f.write("{ invalid json }")
    # Should return empty list
    assert storage.load_sessions() == []


def test_atomic_write_operations(tmp_path, basic_test_session):
    """Test atomic write operations in JSONStorage."""
    storage_path = tmp_path / "atomic.json"
    storage = JSONStorage(file_path=storage_path)
    storage.save_session(basic_test_session)
    assert os.path.exists(storage_path)
    # Simulate atomic write by checking file exists after save
    loaded = storage.load_sessions()
    assert len(loaded) == 1
    assert loaded[0].session_id == basic_test_session.session_id


def test_bulk_save_sessions_json(temp_json_storage, many_test_sessions):
    """Test saving multiple sessions at once in JSONStorage."""
    storage = temp_json_storage
    storage.save_sessions(many_test_sessions)
    loaded = storage.load_sessions()
    assert len(loaded) == len(many_test_sessions)
    loaded_ids = {s.session_id for s in loaded}
    expected_ids = {s.session_id for s in many_test_sessions}
    assert loaded_ids == expected_ids


def test_handles_invalid_data_format_json(temp_json_storage):
    """Test handling of invalid data format (non-list JSON) in JSONStorage."""
    storage = temp_json_storage
    # Write a dict instead of a list
    with open(storage.file_path, "w") as f:
        json.dump({"not": "a list"}, f)
    assert storage.load_sessions() == []


def test_storage_profile_creation():
    """Test creating a StorageProfile."""
    profile = StorageProfile("profile1", "json", "file.json")
    assert profile.name == "profile1"
    assert profile.storage_type == "json"
    assert profile.file_path == "file.json"


def test_storage_profile_serialization():
    """Test serializing and deserializing a StorageProfile."""
    profile = StorageProfile("profile2", "json", "file2.json")
    d = profile.to_dict()
    profile2 = StorageProfile.from_dict(d)
    assert profile2.name == profile.name
    assert profile2.storage_type == profile.storage_type
    assert profile2.file_path == profile.file_path


def test_profile_manager_create_and_get(tmp_path):
    """Test creating and retrieving profiles with ProfileManager."""
    config_path = tmp_path / "profiles.json"
    manager = ProfileManager(config_path=config_path)
    profile = manager._create_profile("test-profile", "json", str(tmp_path / "sessions.json"))
    assert profile.name == "test-profile"
    assert manager.get_profile("test-profile").name == "test-profile"


def test_profile_manager_delete(tmp_path):
    """Test deleting a profile with ProfileManager."""
    config_path = tmp_path / "profiles.json"
    manager = ProfileManager(config_path=config_path)
    manager._create_profile("to-delete", "json", str(tmp_path / "del.json"))
    manager.delete_profile("to-delete")
    assert "to-delete" not in manager.profiles


def test_profile_manager_list_profiles(tmp_path):
    """Test listing profiles in ProfileManager."""
    config_path = tmp_path / "profiles.json"
    manager = ProfileManager(config_path=config_path)
    manager._create_profile("p1", "json", str(tmp_path / "p1.json"))
    manager._create_profile("p2", "json", str(tmp_path / "p2.json"))
    profiles = manager.list_profiles()
    assert "p1" in profiles and "p2" in profiles


def test_profile_manager_switch_profile(tmp_path):
    """Test switching active profile in ProfileManager."""
    config_path = tmp_path / "profiles.json"
    manager = ProfileManager(config_path=config_path)
    manager._create_profile("main", "json", str(tmp_path / "main.json"))
    manager._create_profile("other", "json", str(tmp_path / "other.json"))
    manager.switch_profile("other")
    assert manager.active_profile_name == "other"


def test_profile_manager_backup_and_restore(tmp_path):
    """Test backup and restore of profiles in ProfileManager."""
    config_path = tmp_path / "profiles.json"
    manager = ProfileManager(config_path=config_path)
    manager._create_profile("b1", "json", str(tmp_path / "b1.json"))
    backup_path = manager.backup_profiles()
    assert backup_path.exists()
    # Simulate restore
    manager.delete_profile("b1")
    assert "b1" not in manager.profiles
    manager.restore_from_backup(backup_path)
    assert "b1" in manager.profiles


def test_get_storage_instance_invalid_type(monkeypatch, tmp_path):
    """Test get_storage_instance with invalid storage type raises ValueError."""
    config_path = tmp_path / "profiles.json"
    profile_manager = ProfileManager(config_path=config_path)
    profile_manager._create_profile("bad", "invalid", str(tmp_path / "bad.json"))
    monkeypatch.setattr("pytest_insight.storage.get_profile_manager", lambda: profile_manager)
    with pytest.raises(ValueError):
        get_storage_instance(profile_name="bad")
