"""
Tests for the unified CLI interface located at pytest_insight/__main__.py
"""

# Standard library imports
import tempfile
from pathlib import Path
from unittest import mock
from unittest.mock import patch

# Third-party imports
import pytest

# Local imports
from pytest_insight.__main__ import app
from pytest_insight.core.storage import ProfileManager, StorageProfile
from typer.testing import CliRunner

# List to track any profile files created during testing
TEST_PROFILE_FILES = []


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture(autouse=True)
def cleanup_test_profiles():
    """Clean up any test profile files that might have been created."""
    yield
    # After each test, clean up any test profile files
    for file_path in TEST_PROFILE_FILES:
        try:
            if Path(file_path).exists():
                Path(file_path).unlink()
        except Exception:
            pass
    TEST_PROFILE_FILES.clear()


@pytest.fixture
def mock_profile_manager(temp_dir):
    """Create a mock profile manager for testing."""
    # Create a profile manager with test profiles
    mock_pm = mock.MagicMock(spec=ProfileManager)

    # Set up the list_profiles method to return test profiles
    test_profiles = {
        "test1": mock.MagicMock(spec=StorageProfile),
        "test2": mock.MagicMock(spec=StorageProfile),
    }

    # Configure the mock profiles with proper attributes
    test_profiles["test1"].name = "test1"
    test_profiles["test1"].storage_type = "json"
    test_profiles["test1"].file_path = str(temp_dir / "test1.json")

    test_profiles["test2"].name = "test2"
    test_profiles["test2"].storage_type = "memory"
    test_profiles["test2"].file_path = str(temp_dir / "test2.json")

    mock_pm.list_profiles.return_value = test_profiles

    # Set up the get_active_profile method
    mock_pm.get_active_profile.return_value = test_profiles["test1"]

    # Set up the get_profile method
    mock_pm.get_profile.side_effect = lambda name=None: (
        test_profiles["test1"]
        if name is None
        else test_profiles.get(name) or (lambda: ValueError(f"Profile '{name}' not found"))()
    )

    # Set up the _create_profile method
    def mock_create_profile(name, storage_type="json", file_path=None):
        profile = mock.MagicMock(spec=StorageProfile)
        profile.name = name
        profile.storage_type = storage_type
        profile.file_path = file_path or str(temp_dir / f"{name}.json")
        # Track the file path for cleanup
        TEST_PROFILE_FILES.append(profile.file_path)
        return profile

    mock_pm._create_profile.side_effect = mock_create_profile

    # Set up the switch_profile method
    def mock_switch(name):
        if name not in test_profiles:
            raise ValueError(f"Profile '{name}' not found")
        return test_profiles[name]

    mock_pm.switch_profile.side_effect = mock_switch

    # Set up the delete_profile method
    def mock_delete(name):
        if name == "test1":  # Active profile
            raise ValueError("Cannot delete the active profile")
        if name not in test_profiles:
            raise ValueError(f"Profile '{name}' not found")
        return None

    mock_pm.delete_profile.side_effect = mock_delete

    return mock_pm


@pytest.fixture
def mock_get_profile_manager(mock_profile_manager):
    """Mock the get_profile_manager function to return our test profile manager."""
    with mock.patch("pytest_insight.__main__.get_profile_manager", return_value=mock_profile_manager):
        yield


@pytest.fixture
def mock_storage_instance():
    """Create a mock storage instance."""
    mock_instance = mock.MagicMock()
    mock_instance.load_sessions.return_value = []
    return mock_instance


@pytest.fixture
def mock_get_storage_instance():
    """Mock the load_sessions function."""
    with mock.patch("pytest_insight.__main__.load_sessions") as mock_load_sessions:
        yield mock_load_sessions


@pytest.fixture
def mock_practice_data_generator():
    """Mock the PracticeDataGenerator class."""
    with mock.patch("pytest_insight.__main__.PracticeDataGenerator") as mock_generator:
        instance = mock.MagicMock()
        instance.target_path = Path("/mock/path/to/data.json")
        mock_generator.return_value = instance
        yield mock_generator


class TestProfileCommands:
    """Test the profile management commands."""

    @pytest.fixture
    def mock_get_profile_manager(self):
        """Mock the get_profile_manager function to return a mock profile manager."""
        with mock.patch("pytest_insight.__main__.get_profile_manager") as mock_get_pm:
            # Create a mock profile manager
            mock_profile_manager = mock.MagicMock()
            mock_get_pm.return_value = mock_profile_manager
            yield mock_get_pm

    @pytest.fixture
    def mock_list_profiles(self):
        """Mock the list_profiles function."""
        with mock.patch("pytest_insight.__main__.list_profiles") as mock_list:
            yield mock_list

    @pytest.fixture
    def mock_get_active_profile(self):
        """Mock the get_active_profile function."""
        with mock.patch("pytest_insight.__main__.get_active_profile") as mock_active:
            yield mock_active

    @pytest.fixture
    def mock_create_profile(self):
        """Mock the create_profile function."""
        with mock.patch("pytest_insight.__main__.create_profile") as mock_create:
            yield mock_create

    @pytest.fixture
    def mock_switch_profile(self):
        """Mock the switch_profile function."""
        with mock.patch("pytest_insight.__main__.switch_profile") as mock_switch:
            yield mock_switch

    @pytest.fixture
    def mock_get_storage_instance(self):
        """Mock the load_sessions function."""
        with mock.patch("pytest_insight.__main__.load_sessions") as mock_load_sessions:
            yield mock_load_sessions

    def test_profile_create(self, runner, mock_create_profile):
        """Test the 'profile create' command."""
        # Test creating a JSON profile
        result = runner.invoke(app, ["profile", "create", "test-profile", "--type", "json"])
        assert result.exit_code == 0
        assert "Created profile" in result.stdout
        mock_create_profile.assert_called_once_with("test-profile", "json", None)

    def test_profile_delete(self, runner, mock_get_profile_manager):
        """Test the 'profile delete' command."""
        from pytest_insight.__main__ import get_profile_manager

        # Test deleting a profile
        result = runner.invoke(app, ["profile", "delete", "test-profile", "--force"])
        assert result.exit_code == 0
        assert "Deleted profile" in result.stdout
        get_profile_manager.return_value.delete_profile.assert_called_once_with("test-profile")

    def test_profile_switch(self, runner, mock_switch_profile):
        """Test the 'profile switch' command."""
        # Test switching profiles
        result = runner.invoke(app, ["profile", "switch", "test-profile"])
        assert result.exit_code == 0
        assert "Switched to profile" in result.stdout
        mock_switch_profile.assert_called_once_with("test-profile")

    def test_profile_list(self, runner, mock_list_profiles, mock_get_active_profile):
        """Test the 'profile list' command."""
        from pytest_insight.core.storage import StorageProfile

        # Create test profiles
        default_profile = mock.MagicMock(spec=StorageProfile)
        default_profile.name = "default"
        default_profile.storage_type = "json"
        default_profile.file_path = "/mock/path/default.json"

        test_profile = mock.MagicMock(spec=StorageProfile)
        test_profile.name = "test-profile"
        test_profile.storage_type = "json"
        test_profile.file_path = "/mock/path/test-profile.json"

        # Set up the profiles dictionary
        profiles = {
            "default": default_profile,
            "test-profile": test_profile,
        }

        # Set up the list_profiles function to return our test profiles
        mock_list_profiles.return_value = profiles

        # Mock the get_active_profile function to return the default profile
        mock_get_active_profile.return_value = default_profile

        # Test listing profiles
        with mock.patch("rich.print"):
            result = runner.invoke(app, ["profile", "list"])
            assert result.exit_code == 0
            mock_list_profiles.assert_called_once()

    def test_list_profiles_with_type_filter(self, runner, mock_list_profiles, mock_get_active_profile):
        """Test the 'profile list' command with type filter."""
        from pytest_insight.core.storage import StorageProfile

        # Create test profiles with different storage types
        json_profile = mock.MagicMock(spec=StorageProfile)
        json_profile.name = "test-json"
        json_profile.storage_type = "json"
        json_profile.file_path = "/mock/path/test-json.json"

        memory_profile = mock.MagicMock(spec=StorageProfile)
        memory_profile.name = "test-memory"
        memory_profile.storage_type = "memory"
        memory_profile.file_path = None

        # Set up the profiles dictionary
        all_profiles = {
            "test-json": json_profile,
            "test-memory": memory_profile,
        }

        # Set up the list_profiles function to return all profiles
        mock_list_profiles.return_value = all_profiles

        # Mock the get_active_profile method
        active_profile = mock.MagicMock(spec=StorageProfile)
        active_profile.name = "test-json"
        mock_get_active_profile.return_value = active_profile

        # Test JSON filter
        with mock.patch("rich.print"):
            result = runner.invoke(app, ["profile", "list", "--type", "json"])
            assert result.exit_code == 0
            mock_list_profiles.assert_called_once()
            # We can't directly test the filtering since it happens in the command function,
            # but we can check that the command executed successfully

        # Reset the mock for the next test
        mock_list_profiles.reset_mock()

        # Test memory filter
        with mock.patch("rich.print"):
            result = runner.invoke(app, ["profile", "list", "--type", "memory"])
            assert result.exit_code == 0
            mock_list_profiles.assert_called_once()

    def test_list_profiles_with_pattern_filter(self, runner, mock_list_profiles, mock_get_active_profile):
        """Test the 'profile list' command with pattern filter."""
        from pytest_insight.core.storage import StorageProfile

        # Create test profiles with different names
        test_abc = mock.MagicMock(spec=StorageProfile)
        test_abc.name = "test-abc"
        test_abc.storage_type = "json"
        test_abc.file_path = "/mock/path/test-abc.json"

        test_xyz = mock.MagicMock(spec=StorageProfile)
        test_xyz.name = "test-xyz"
        test_xyz.storage_type = "json"
        test_xyz.file_path = "/mock/path/test-xyz.json"

        # Set up the profiles dictionary
        all_profiles = {
            "test-abc": test_abc,
            "test-xyz": test_xyz,
        }

        # Set up the list_profiles function to return all profiles
        mock_list_profiles.return_value = all_profiles

        # Mock the get_active_profile method
        active_profile = mock.MagicMock(spec=StorageProfile)
        active_profile.name = "test-abc"
        mock_get_active_profile.return_value = active_profile

        # Test specific pattern filter
        with mock.patch("rich.print"):
            result = runner.invoke(app, ["profile", "list", "--pattern", "test-abc"])
            assert result.exit_code == 0
            mock_list_profiles.assert_called_once()

        # Reset the mock for the next test
        mock_list_profiles.reset_mock()

        # Test wildcard pattern filter
        with mock.patch("rich.print"):
            result = runner.invoke(app, ["profile", "list", "--pattern", "test-*"])
            assert result.exit_code == 0
            mock_list_profiles.assert_called_once()

    def test_clean_profiles(
        self,
        runner,
        mock_list_profiles,
        mock_get_active_profile,
        mock_get_profile_manager,
    ):
        """Test the 'profile clean' command for bulk deletion."""
        from pytest_insight.core.storage import StorageProfile

        profile_manager = mock_get_profile_manager.return_value

        # Create test profiles for bulk deletion testing
        active_profile = mock.MagicMock(spec=StorageProfile)
        active_profile.name = "active-profile"
        active_profile.storage_type = "json"
        active_profile.file_path = "/mock/path/active-profile.json"

        mem_profile1 = mock.MagicMock(spec=StorageProfile)
        mem_profile1.name = "mem-test1"
        mem_profile1.storage_type = "memory"
        mem_profile1.file_path = None

        mem_profile2 = mock.MagicMock(spec=StorageProfile)
        mem_profile2.name = "mem-test2"
        mem_profile2.storage_type = "memory"
        mem_profile2.file_path = None

        json_profile = mock.MagicMock(spec=StorageProfile)
        json_profile.name = "json-test"
        json_profile.storage_type = "json"
        json_profile.file_path = "/mock/path/json-test.json"

        # Set up the profiles dictionary
        all_profiles = {
            "active-profile": active_profile,
            "mem-test1": mem_profile1,
            "mem-test2": mem_profile2,
            "json-test": json_profile,
        }

        # Set up the list_profiles function to return all profiles
        mock_list_profiles.return_value = all_profiles

        # Set the active profile
        mock_get_active_profile.return_value = active_profile

        # Track which profiles are deleted
        deleted_profiles = []

        # Mock the delete_profile method
        def mock_delete_profile(name):
            if name == active_profile.name:
                raise ValueError("Cannot delete active profile")
            deleted_profiles.append(name)
            return None

        profile_manager.delete_profile.side_effect = mock_delete_profile

        # Test default (memory profiles) with force flag
        with mock.patch("typer.confirm", return_value=True):
            deleted_profiles.clear()
            result = runner.invoke(app, ["profile", "clean", "--force"])
            assert result.exit_code == 0
            mock_list_profiles.assert_called_once()
            # Check that the memory profiles were deleted
            assert set(deleted_profiles) == {"mem-test1", "mem-test2"}

        # Reset the mock for the next test
        mock_list_profiles.reset_mock()

        # Test with type filter
        with mock.patch("typer.confirm", return_value=True):
            deleted_profiles.clear()
            result = runner.invoke(app, ["profile", "clean", "--type", "json", "--force"])
            assert result.exit_code == 0
            mock_list_profiles.assert_called_once()
            # Check that the json profile was deleted, but not the active profile
            assert set(deleted_profiles) == {"json-test"}
            assert "active-profile" not in deleted_profiles

        # Reset the mock for the next test
        mock_list_profiles.reset_mock()

        # Test with pattern filter
        with mock.patch("typer.confirm", return_value=True):
            deleted_profiles.clear()
            result = runner.invoke(app, ["profile", "clean", "--pattern", "mem-*", "--force"])
            assert result.exit_code == 0
            mock_list_profiles.assert_called_once()
            # Check that the memory profiles were deleted
            assert set(deleted_profiles) == {"mem-test1", "mem-test2"}

        # Reset the mock for the next test
        mock_list_profiles.reset_mock()

        # Test dry run
        with mock.patch("typer.confirm", return_value=True):
            deleted_profiles.clear()
            result = runner.invoke(app, ["profile", "clean", "--dry-run"])
            assert result.exit_code == 0
            mock_list_profiles.assert_called_once()
            # Check that no profiles were actually deleted
            assert not deleted_profiles

    def test_profile_merge(self, runner, mock_list_profiles, mock_get_profile_manager, mock_create_profile):
        """Test the 'profile merge' command."""

        from pytest_insight.core.models import TestSession
        from pytest_insight.core.storage import StorageProfile

        # Create test profiles
        source1_profile = mock.MagicMock(spec=StorageProfile)
        source1_profile.name = "source1"
        source1_profile.storage_type = "json"
        source1_profile.file_path = "/mock/path/source1.json"

        source2_profile = mock.MagicMock(spec=StorageProfile)
        source2_profile.name = "source2"
        source2_profile.storage_type = "json"
        source2_profile.file_path = "/mock/path/source2.json"

        target_profile = mock.MagicMock(spec=StorageProfile)
        target_profile.name = "target"
        target_profile.storage_type = "json"
        target_profile.file_path = "/mock/path/target.json"

        # Set up the profiles dictionary
        all_profiles = {
            "source1": source1_profile,
            "source2": source2_profile,
            "target": target_profile,
        }

        # Mock the list_profiles function to return our test profiles
        mock_list_profiles.return_value = all_profiles

        # Create mock sessions for source profiles
        source1_sessions = {
            "session1": mock.MagicMock(spec=TestSession),
            "session2": mock.MagicMock(spec=TestSession),
        }

        source2_sessions = {
            "session3": mock.MagicMock(spec=TestSession),
            "session4": mock.MagicMock(spec=TestSession),
        }

        # Create mock sessions for target profile (to test merge strategies)
        target_sessions = {
            "session1": mock.MagicMock(spec=TestSession),  # Duplicate with source1
        }

        # Mock the load_sessions function to return our mock sessions
        def mock_load_sessions(profile_name):
            if profile_name == "source1":
                return source1_sessions
            elif profile_name == "source2":
                return source2_sessions
            elif profile_name == "target":
                return target_sessions
            return {}

        # Set up the mock profile manager
        profile_manager = mock_get_profile_manager
        profile_manager.save_session = mock.MagicMock()

        # Test 1: Merging with skip_existing strategy
        with mock.patch("pytest_insight.__main__.load_sessions", side_effect=mock_load_sessions):
            with mock.patch(
                "pytest_insight.__main__.get_profile_manager",
                return_value=profile_manager,
            ):
                with mock.patch("typer.confirm", return_value=True):
                    result = runner.invoke(
                        app,
                        [
                            "profile",
                            "merge",
                            "source1,source2",
                            "target",
                            "--strategy",
                            "skip_existing",
                        ],
                    )
                    assert result.exit_code == 0

                    # Verify sessions were saved to target
                    # session1 should be skipped (already exists), others should be saved
                    assert profile_manager.save_session.call_count == 3

                    # Check that the right sessions were saved
                    saved_sessions = []
                    for call in profile_manager.save_session.call_args_list:
                        args, kwargs = call
                        target_name, session, session_id = args
                        saved_sessions.append(session_id)

                    # session1 should be skipped, so not in saved_sessions
                    assert "session1" not in saved_sessions
                    assert "session2" in saved_sessions
                    assert "session3" in saved_sessions
                    assert "session4" in saved_sessions

        # Test 2: Merging with replace_existing strategy
        profile_manager.save_session.reset_mock()
        with mock.patch("pytest_insight.__main__.load_sessions", side_effect=mock_load_sessions):
            with mock.patch(
                "pytest_insight.__main__.get_profile_manager",
                return_value=profile_manager,
            ):
                with mock.patch("typer.confirm", return_value=True):
                    result = runner.invoke(
                        app,
                        [
                            "profile",
                            "merge",
                            "source1,source2",
                            "target",
                            "--strategy",
                            "replace_existing",
                        ],
                    )
                    assert result.exit_code == 0

                    # Verify sessions were saved to target
                    # All sessions should be saved, including session1 which replaces the existing one
                    assert profile_manager.save_session.call_count == 4

                    # Check that the right sessions were saved
                    saved_sessions = []
                    for call in profile_manager.save_session.call_args_list:
                        args, kwargs = call
                        target_name, session, session_id = args
                        saved_sessions.append(session_id)

                    # session1 should be replaced
                    assert "session1" in saved_sessions
                    assert "session2" in saved_sessions
                    assert "session3" in saved_sessions
                    assert "session4" in saved_sessions

        # Test 3: Merging with keep_both strategy
        profile_manager.save_session.reset_mock()
        with mock.patch("pytest_insight.__main__.load_sessions", side_effect=mock_load_sessions):
            with mock.patch(
                "pytest_insight.__main__.get_profile_manager",
                return_value=profile_manager,
            ):
                # Also mock uuid to get predictable session IDs
                with mock.patch("uuid.uuid4") as mock_uuid:
                    mock_uuid.return_value.hex = "abcdef1234567890"
                    with mock.patch("typer.confirm", return_value=True):
                        result = runner.invoke(
                            app,
                            [
                                "profile",
                                "merge",
                                "source1,source2",
                                "target",
                                "--strategy",
                                "keep_both",
                            ],
                        )
                        assert result.exit_code == 0

                        # Verify sessions were saved to target
                        # All sessions should be saved, with session1 renamed
                        assert profile_manager.save_session.call_count == 4

                        # Check that the right sessions were saved
                        saved_sessions = []
                        for call in profile_manager.save_session.call_args_list:
                            args, kwargs = call
                            target_name, session, session_id = args
                            saved_sessions.append(session_id)

                        # Original session1 should not be in saved_sessions, but a renamed version should be
                        assert "session1" not in saved_sessions
                        assert any(s.startswith("session1_source1_") for s in saved_sessions)
                        assert "session2" in saved_sessions
                        assert "session3" in saved_sessions
                        assert "session4" in saved_sessions

        # Test 4: Test with filter pattern
        profile_manager.save_session.reset_mock()
        with mock.patch("pytest_insight.__main__.load_sessions", side_effect=mock_load_sessions):
            with mock.patch(
                "pytest_insight.__main__.get_profile_manager",
                return_value=profile_manager,
            ):
                with mock.patch("typer.confirm", return_value=True):
                    result = runner.invoke(
                        app,
                        [
                            "profile",
                            "merge",
                            "source1,source2",
                            "target",
                            "--filter",
                            "session[34]*",
                        ],
                    )
                    assert result.exit_code == 0

                    # Verify sessions were saved to target
                    # Only sessions matching the pattern should be saved
                    assert profile_manager.save_session.call_count == 2

                    # Check that the right sessions were saved
                    saved_sessions = []
                    for call in profile_manager.save_session.call_args_list:
                        args, kwargs = call
                        target_name, session, session_id = args
                        saved_sessions.append(session_id)

                    # Only session3 and session4 should be saved
                    assert "session1" not in saved_sessions
                    assert "session2" not in saved_sessions
                    assert "session3" in saved_sessions
                    assert "session4" in saved_sessions

        # Test 5: Test with create target option
        profile_manager.save_session.reset_mock()
        with mock.patch("pytest_insight.__main__.load_sessions", side_effect=mock_load_sessions):
            with mock.patch(
                "pytest_insight.__main__.get_profile_manager",
                return_value=profile_manager,
            ):
                with mock.patch("typer.confirm", return_value=True):
                    # Remove target from available profiles
                    new_profiles = all_profiles.copy()
                    del new_profiles["target"]
                    mock_list_profiles.return_value = new_profiles

                    # Mock the create_profile function
                    mock_create_profile.return_value = target_profile

                    result = runner.invoke(
                        app,
                        [
                            "profile",
                            "merge",
                            "source1,source2",
                            "target",
                            "--create",
                            "--type",
                            "json",
                        ],
                    )
                    assert result.exit_code == 0

                    # Verify target profile was created
                    mock_create_profile.assert_called_once_with("target", "json")

                    # Verify sessions were saved to target
                    assert profile_manager.save_session.call_count > 0


class TestGenerateCommands:
    """Tests for the data generation commands."""

    def test_generate_practice_data(self, runner, mock_get_profile_manager, mock_practice_data_generator):
        """Test the 'generate practice' command."""
        result = runner.invoke(app, ["generate", "practice", "--days", "3", "--targets", "2"])
        assert result.exit_code == 0
        assert "Generated practice data" in result.stdout

        # Verify the generator was called with correct parameters
        mock_practice_data_generator.assert_called_once()
        args, kwargs = mock_practice_data_generator.call_args
        assert kwargs["days"] == 3
        assert kwargs["targets_per_base"] == 2

    def test_generate_practice_data_with_profile(self, runner, mock_get_profile_manager, mock_practice_data_generator):
        """Test generating practice data with a specific profile."""
        result = runner.invoke(app, ["generate", "practice", "--profile", "test1", "--days", "5"])
        assert result.exit_code == 0

        # Verify the generator was called with correct parameters
        mock_practice_data_generator.assert_called_once()
        args, kwargs = mock_practice_data_generator.call_args
        assert kwargs["storage_profile"] == "test1"
        assert kwargs["days"] == 5


class TestAnalyzeCommands:
    """Tests for the analysis commands."""

    def test_analyze_insights(self, runner, mock_get_profile_manager, mock_get_storage_instance):
        """Test the 'analyze insights' command."""
        result = runner.invoke(app, ["analyze"])
        assert result.exit_code == 0
        assert "Using profile: default" in result.stdout

    def test_analyze_insights_with_profile(self, runner, mock_get_profile_manager, mock_get_storage_instance):
        """Test analyzing insights with a specific profile."""
        result = runner.invoke(app, ["analyze", "--profile", "test1"])
        assert result.exit_code == 0
        assert "Using profile: test1" in result.stdout


class TestMainCommand:
    """Tests for the main command and help texts."""

    def test_main_help(self, runner):
        """Test the main help command."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "pytest-insight" in result.stdout
        assert "profile" in result.stdout
        assert "generate" in result.stdout
        assert "analyze" in result.stdout

    def test_no_args_shows_help(self, runner):
        """Test that running the CLI without arguments shows help."""
        result = runner.invoke(app)
        assert result.exit_code == 0
        # Verify the output contains the same content as the help command
        assert "pytest-insight" in result.stdout
        assert "profile" in result.stdout
        assert "generate" in result.stdout
        assert "analyze" in result.stdout
        assert "dashboard" in result.stdout
        assert "api-explorer" in result.stdout

    def test_profile_help(self, runner):
        """Test the profile help command."""
        result = runner.invoke(app, ["profile", "--help"])
        assert result.exit_code == 0
        assert "Manage storage profiles" in result.stdout
        assert "list" in result.stdout
        assert "create" in result.stdout
        assert "switch" in result.stdout
        assert "active" in result.stdout
        assert "delete" in result.stdout

    def test_generate_help(self, runner):
        """Test the generate help command."""
        result = runner.invoke(app, ["generate", "--help"])
        assert result.exit_code == 0
        assert "Generate practice test data" in result.stdout
        assert "practice" in result.stdout

    def test_analyze_help(self, runner):
        """Test the analyze help command."""
        result = runner.invoke(app, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "Analyze test sessions" in result.stdout

    def test_dashboard_help(self, runner):
        """Test the dashboard help command."""
        result = runner.invoke(app, ["dashboard", "--help"])
        assert result.exit_code == 0
        assert "dashboard" in result.stdout
        assert "launch" in result.stdout

    def test_api_explorer_help(self, runner):
        """Test the api-explorer help command."""
        result = runner.invoke(app, ["api-explorer", "--help"])
        assert result.exit_code == 0
        assert "api-explorer" in result.stdout
        assert "launch" in result.stdout


class TestDashboardCommands:
    """Tests for the dashboard commands."""

    @patch("pytest_insight.cli.cli_dashboard.subprocess.run")
    @patch("pytest_insight.cli.cli_dashboard._run_dashboard")
    def test_dashboard_launch(self, mock_run_dashboard, mock_subprocess_run, runner, mock_get_profile_manager):
        """Test the 'dashboard launch' command."""
        result = runner.invoke(app, ["dashboard", "launch"])
        assert result.exit_code == 0
        mock_run_dashboard.assert_called_once_with(8501, None, True)
        mock_subprocess_run.assert_not_called()  # Ensure subprocess.run is not called

    @patch("pytest_insight.cli.cli_dashboard.subprocess.run")
    @patch("pytest_insight.cli.cli_dashboard._run_dashboard")
    def test_dashboard_launch_with_profile(
        self, mock_run_dashboard, mock_subprocess_run, runner, mock_get_profile_manager
    ):
        """Test the 'dashboard launch' command with a profile."""
        result = runner.invoke(app, ["dashboard", "launch", "--profile", "test1"])
        assert result.exit_code == 0
        mock_run_dashboard.assert_called_once_with(8501, "test1", True)
        mock_subprocess_run.assert_not_called()  # Ensure subprocess.run is not called


class TestAPIExplorerCommands:
    """Tests for the API Explorer commands."""

    @patch("webbrowser.open")
    @patch("uvicorn.run")
    @patch("pytest_insight.cli.cli_api_explorer._run_api_explorer")
    def test_api_explorer_launch(
        self,
        mock_run_api_explorer,
        mock_uvicorn_run,
        mock_webbrowser_open,
        runner,
        mock_get_profile_manager,
    ):
        """Test the 'api-explorer launch' command."""
        result = runner.invoke(app, ["api-explorer", "launch"])
        assert result.exit_code == 0
        mock_run_api_explorer.assert_called_once_with(8000, None, True)
        mock_uvicorn_run.assert_not_called()  # Ensure uvicorn.run is not called
        mock_webbrowser_open.assert_not_called()  # Ensure webbrowser.open is not called

    @patch("webbrowser.open")
    @patch("uvicorn.run")
    @patch("pytest_insight.cli.cli_api_explorer._run_api_explorer")
    def test_api_explorer_launch_with_profile(
        self,
        mock_run_api_explorer,
        mock_uvicorn_run,
        mock_webbrowser_open,
        runner,
        mock_get_profile_manager,
    ):
        """Test the 'api-explorer launch' command with a profile."""
        result = runner.invoke(app, ["api-explorer", "launch", "--profile", "test1"])
        assert result.exit_code == 0
        mock_run_api_explorer.assert_called_once_with(8000, "test1", True)
        mock_uvicorn_run.assert_not_called()  # Ensure uvicorn.run is not called
        mock_webbrowser_open.assert_not_called()  # Ensure webbrowser.open is not called

    @patch("webbrowser.open")
    @patch("uvicorn.run")
    @patch("pytest_insight.cli.cli_api_explorer._run_api_explorer")
    def test_api_explorer_launch_with_port(
        self,
        mock_run_api_explorer,
        mock_uvicorn_run,
        mock_webbrowser_open,
        runner,
        mock_get_profile_manager,
    ):
        """Test the 'api-explorer launch' command with a custom port."""
        result = runner.invoke(app, ["api-explorer", "launch", "--port", "8080"])
        assert result.exit_code == 0
        mock_run_api_explorer.assert_called_once_with(8080, None, True)
        mock_uvicorn_run.assert_not_called()  # Ensure uvicorn.run is not called
        mock_webbrowser_open.assert_not_called()  # Ensure webbrowser.open is not called
