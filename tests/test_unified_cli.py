"""
Tests for the unified CLI interface.
"""

# Standard library imports
import tempfile
from pathlib import Path
from unittest import mock

# Third-party imports
import pytest

# Local imports
from pytest_insight.__main__ import app
from pytest_insight.core.storage import ProfileManager, StorageProfile
from typer.testing import CliRunner


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


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
def mock_get_storage_instance(mock_storage_instance):
    """Mock the get_storage_instance function."""
    with mock.patch(
        "pytest_insight.core.storage.get_storage_instance",
        return_value=mock_storage_instance,
    ):
        yield


@pytest.fixture
def mock_practice_data_generator():
    """Mock the PracticeDataGenerator class."""
    with mock.patch("pytest_insight.__main__.PracticeDataGenerator") as mock_generator:
        instance = mock.MagicMock()
        instance.target_path = Path("/mock/path/to/data.json")
        mock_generator.return_value = instance
        yield mock_generator


class TestProfileCommands:
    """Tests for the profile management commands."""

    def test_list_profiles(self, runner, mock_get_profile_manager):
        """Test the 'profile list' command."""
        with mock.patch("pytest_insight.__main__.list_profiles") as mock_list:
            # Create properly configured mock profiles
            profile1 = mock.MagicMock(spec=StorageProfile)
            profile1.name = "test1"
            profile1.storage_type = "json"
            profile1.file_path = "/path/to/test1.json"

            profile2 = mock.MagicMock(spec=StorageProfile)
            profile2.name = "test2"
            profile2.storage_type = "memory"
            profile2.file_path = "/path/to/test2.json"

            mock_list.return_value = {"test1": profile1, "test2": profile2}

            with mock.patch("pytest_insight.__main__.get_active_profile") as mock_active:
                active_profile = mock.MagicMock(spec=StorageProfile)
                active_profile.name = "test1"
                mock_active.return_value = active_profile

                result = runner.invoke(app, ["profile", "list"])
                assert result.exit_code == 0
                assert "test1" in result.stdout
                assert "test2" in result.stdout
                assert "*" in result.stdout  # Active profile marker

    def test_active_profile(self, runner, mock_get_profile_manager):
        """Test the 'profile active' command."""
        with mock.patch("pytest_insight.__main__.get_active_profile") as mock_active:
            profile = mock.MagicMock(spec=StorageProfile)
            profile.name = "test1"
            profile.storage_type = "json"
            profile.file_path = "/path/to/test1.json"
            mock_active.return_value = profile

            result = runner.invoke(app, ["profile", "active"])
            assert result.exit_code == 0
            assert "test1" in result.stdout
            assert "Active profile" in result.stdout

    def test_create_profile(self, runner, mock_get_profile_manager):
        """Test the 'profile create' command."""
        with mock.patch("pytest_insight.__main__.create_profile") as mock_create:
            profile = mock.MagicMock(spec=StorageProfile)
            profile.name = "test3"
            profile.storage_type = "json"
            profile.file_path = "/path/to/test3.json"
            mock_create.return_value = profile

            result = runner.invoke(app, ["profile", "create", "test3"])
            assert result.exit_code == 0
            assert "Created profile 'test3'" in result.stdout

    def test_create_profile_with_options(self, runner, mock_get_profile_manager):
        """Test creating a profile with custom options."""
        with mock.patch("pytest_insight.__main__.create_profile") as mock_create:
            profile = mock.MagicMock(spec=StorageProfile)
            profile.name = "test4"
            profile.storage_type = "memory"
            profile.file_path = "/custom/path.json"
            mock_create.return_value = profile

            with mock.patch("pytest_insight.__main__.switch_profile") as mock_switch:
                switched_profile = mock.MagicMock(spec=StorageProfile)
                switched_profile.name = "test4"
                mock_switch.return_value = switched_profile

                result = runner.invoke(
                    app,
                    [
                        "profile",
                        "create",
                        "test4",
                        "--type",
                        "memory",
                        "--path",
                        "/custom/path.json",
                        "--activate",
                    ],
                )
                assert result.exit_code == 0
                assert "Created profile 'test4'" in result.stdout
                assert "Activated profile 'test4'" in result.stdout

    def test_switch_profile(self, runner, mock_get_profile_manager):
        """Test the 'profile switch' command."""
        with mock.patch("pytest_insight.__main__.switch_profile") as mock_switch:
            profile = mock.MagicMock(spec=StorageProfile)
            profile.name = "test2"
            mock_switch.return_value = profile

            result = runner.invoke(app, ["profile", "switch", "test2"])
            assert result.exit_code == 0
            assert "Switched to profile 'test2'" in result.stdout

    def test_switch_nonexistent_profile(self, runner, mock_get_profile_manager):
        """Test switching to a nonexistent profile."""
        with mock.patch("pytest_insight.__main__.switch_profile") as mock_switch:
            mock_switch.side_effect = ValueError("Profile 'nonexistent' not found")

            result = runner.invoke(app, ["profile", "switch", "nonexistent"])
            assert result.exit_code == 1
            assert "Error" in result.stdout

    def test_delete_profile(self, runner, mock_get_profile_manager):
        """Test the 'profile delete' command with confirmation."""
        # Mock the confirmation prompt to return 'y'
        result = runner.invoke(app, ["profile", "delete", "test2"], input="y\n")
        assert result.exit_code == 0
        assert "Deleted profile 'test2'" in result.stdout

    def test_delete_profile_force(self, runner, mock_get_profile_manager):
        """Test the 'profile delete' command with --force flag."""
        result = runner.invoke(app, ["profile", "delete", "test2", "--force"])
        assert result.exit_code == 0
        assert "Deleted profile 'test2'" in result.stdout

    def test_delete_active_profile(self, runner, mock_get_profile_manager):
        """Test deleting the active profile (should fail)."""
        result = runner.invoke(app, ["profile", "delete", "test1", "--force"])
        assert result.exit_code == 1
        assert "Error" in result.stdout


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
