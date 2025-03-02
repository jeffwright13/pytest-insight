from pytest_insight.constants import DEFAULT_STORAGE_TYPE, StorageType
from pytest_insight.plugin import pytest_addoption


class TestPytestPlugin:
    def test_invalid_storage_type_value(self, mocker):
        mock_parser = mocker.Mock()
        mock_group = mocker.Mock()
        mock_parser.getgroup.return_value = mock_group

        pytest_addoption(mock_parser)

        # Verify the choices passed to addoption
        calls = mock_group.addoption.call_args_list
        storage_type_call = next(call for call in calls if call[0][0] == "--insight-storage-type")
        choices = storage_type_call[1]["choices"]

        assert "invalid_type" not in choices
        assert all(choice in [t.value for t in StorageType] for choice in choices)

    # Parser adds 'pytest-insight' option group successfully
    def test_parser_adds_insight_group(self, mocker):
        mock_parser = mocker.Mock()
        mock_group = mocker.Mock()
        mock_parser.getgroup.return_value = mock_group

        pytest_addoption(mock_parser)

        mock_parser.getgroup.assert_called_once_with("pytest-insight")
        assert mock_group.addoption.call_count == 4
        mock_group.addoption.assert_any_call("--insight", action="store_true", help="Enable pytest-insight")

    # Empty string passed as '--insight-sut' value
    def test_empty_insight_sut_value(self, mocker):
        mock_parser = mocker.Mock()
        mock_group = mocker.Mock()
        mock_parser.getgroup.return_value = mock_group

        pytest_addoption(mock_parser)

        mock_group.addoption.assert_any_call(
            "--insight-sut", action="store", default="default_sut", help="Name of the system under test"
        )

    # '--insight' flag is added as a boolean option
    def test_insight_flag_added_as_boolean_option(self, mocker):
        mock_parser = mocker.Mock()
        mock_group = mocker.Mock()
        mock_parser.getgroup.return_value = mock_group

        pytest_addoption(mock_parser)

        mock_parser.getgroup.assert_called_once_with("pytest-insight")
        mock_group.addoption.assert_any_call("--insight", action="store_true", help="Enable pytest-insight")

    # '--insight-sut' option accepts string value with default 'default_sut'
    def test_insight_sut_option_default_value(self, mocker):
        mock_parser = mocker.Mock()
        mock_group = mocker.Mock()
        mock_parser.getgroup.return_value = mock_group

        pytest_addoption(mock_parser)

        mock_group.addoption.assert_any_call(
            "--insight-sut", action="store", default="default_sut", help="Name of the system under test"
        )

    # '--insight-storage-type' option accepts valid storage type values
    def test_insight_storage_type_option_accepts_valid_values(self, mocker):
        mock_parser = mocker.Mock()
        mock_group = mocker.Mock()
        mock_parser.getgroup.return_value = mock_group

        pytest_addoption(mock_parser)

        mock_parser.getgroup.assert_called_once_with("pytest-insight")
        mock_group.addoption.assert_any_call(
            "--insight-storage-type",
            action="store",
            choices=["local", "json", "remote", "database"],
            default="json",
            help="Storage type for test sessions (default: json)",
        )

    # '--insight-json-path' option accepts file path string value
    def test_insight_json_path_option_accepts_file_path(self, mocker):
        mock_parser = mocker.Mock()
        mock_group = mocker.Mock()
        mock_parser.getgroup.return_value = mock_group

        pytest_addoption(mock_parser)

        mock_parser.getgroup.assert_called_once_with("pytest-insight")
        mock_group.addoption.assert_any_call(
            "--insight-json-path",
            action="store",
            default=None,
            help="Path to JSON storage file for test sessions (use 'none' to disable saving results)",
        )

    # Non-existent path passed to '--insight-json-path'
    def test_non_existent_insight_json_path(self, mocker):
        mock_parser = mocker.Mock()
        mock_group = mocker.Mock()
        mock_parser.getgroup.return_value = mock_group

        pytest_addoption(mock_parser)

        mock_parser.getgroup.assert_called_once_with("pytest-insight")
        mock_group.addoption.assert_any_call(
            "--insight-json-path",
            action="store",
            default=None,
            help="Path to JSON storage file for test sessions (use 'none' to disable saving results)",
        )

    # Default storage type matches constant DEFAULT_STORAGE_TYPE
    def test_default_storage_type(self, mocker):
        mock_parser = mocker.Mock()
        mock_group = mocker.Mock()
        mock_parser.getgroup.return_value = mock_group

        pytest_addoption(mock_parser)

        mock_group.addoption.assert_any_call(
            "--insight-storage-type",
            action="store",
            choices=[t.value for t in StorageType],
            default=DEFAULT_STORAGE_TYPE.value,
            help=f"Storage type for test sessions (default: {DEFAULT_STORAGE_TYPE.value})",
        )

    # Storage type choices match all enum values from StorageType
    def test_storage_type_choices_match_enum_values(self, mocker):
        mock_parser = mocker.Mock()
        mock_group = mocker.Mock()
        mock_parser.getgroup.return_value = mock_group

        pytest_addoption(mock_parser)

        expected_choices = [t.value for t in StorageType]
        mock_group.addoption.assert_any_call(
            "--insight-storage-type",
            action="store",
            choices=expected_choices,
            default=DEFAULT_STORAGE_TYPE.value,
            help=f"Storage type for test sessions (default: {DEFAULT_STORAGE_TYPE.value})",
        )

    # Help text contains accurate default value descriptions
    def test_help_text_contains_accurate_default_values(self, mocker):
        mock_parser = mocker.Mock()
        mock_group = mocker.Mock()
        mock_parser.getgroup.return_value = mock_group

        pytest_addoption(mock_parser)

        mock_group.addoption.assert_any_call(
            "--insight-sut", action="store", default="default_sut", help="Name of the system under test"
        )
        mock_group.addoption.assert_any_call(
            "--insight-storage-type",
            action="store",
            choices=["local", "json", "remote", "database"],
            default="json",
            help="Storage type for test sessions (default: json)",
        )
        mock_group.addoption.assert_any_call(
            "--insight-json-path",
            action="store",
            default=None,
            help="Path to JSON storage file for test sessions (use 'none' to disable saving results)",
        )

    # Group name matches plugin name for consistency
    def test_group_name_matches_plugin_name(self, mocker):
        mock_parser = mocker.Mock()
        mock_group = mocker.Mock()
        mock_parser.getgroup.return_value = mock_group

        pytest_addoption(mock_parser)

        mock_parser.getgroup.assert_called_once_with("pytest-insight")

    # Option names follow consistent '--insight-' prefix pattern
    def test_option_names_have_insight_prefix(self, mocker):
        mock_parser = mocker.Mock()
        mock_group = mocker.Mock()
        mock_parser.getgroup.return_value = mock_group

        pytest_addoption(mock_parser)

        expected_options = ["--insight", "--insight-sut", "--insight-storage-type", "--insight-json-path"]

        actual_options = [call[0][0] for call in mock_group.addoption.call_args_list]
        assert all(option.startswith("--insight") for option in actual_options)
        assert set(expected_options) == set(actual_options)
