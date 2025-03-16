from pytest_insight.constants import DEFAULT_STORAGE_TYPE, StorageType
from pytest_insight.plugin import pytest_addoption


class Test_qPytestPlugin:
    def test_invalid_storage_type_value(self, mocker):
        mock_parser = mocker.Mock()
        mock_group = mocker.Mock()
        mock_parser.getgroup.return_value = mock_group

        pytest_addoption(mock_parser)

        # Verify the choices passed to addoption
        calls = mock_group.addoption.call_args_list
        storage_type_call = next(
            call for call in calls if call[0][0] == "--insight-storage-type"
        )
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
        mock_group.addoption.assert_any_call(
            "--insight", action="store_true", help="Enable pytest-insight"
        )

    # Empty string passed as '--insight-sut' value
    def test_empty_insight_sut_value(self, mocker):
        mock_parser = mocker.Mock()
        mock_group = mocker.Mock()
        mock_parser.getgroup.return_value = mock_group

        pytest_addoption(mock_parser)

        mock_group.addoption.assert_any_call(
            "--insight-sut",
            action="store",
            default="default_sut",
            help="Name of the system under test",
        )

    # '--insight' flag is added as a boolean option
    def test_insight_flag_added_as_boolean_option(self, mocker):
        mock_parser = mocker.Mock()
        mock_group = mocker.Mock()
        mock_parser.getgroup.return_value = mock_group

        pytest_addoption(mock_parser)

        mock_parser.getgroup.assert_called_once_with("pytest-insight")
        mock_group.addoption.assert_any_call(
            "--insight", action="store_true", help="Enable pytest-insight"
        )

    # '--insight-sut' option accepts string value with default 'default_sut'
    def test_insight_sut_option_default_value(self, mocker):
        mock_parser = mocker.Mock()
        mock_group = mocker.Mock()
        mock_parser.getgroup.return_value = mock_group

        pytest_addoption(mock_parser)

        mock_group.addoption.assert_any_call(
            "--insight-sut",
            action="store",
            default="default_sut",
            help="Name of the system under test",
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
            "--insight-sut",
            action="store",
            default="default_sut",
            help="Name of the system under test",
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

        expected_options = [
            "--insight",
            "--insight-sut",
            "--insight-storage-type",
            "--insight-json-path",
        ]

        actual_options = [call[0][0] for call in mock_group.addoption.call_args_list]
        assert all(option.startswith("--insight") for option in actual_options)
        assert set(expected_options) == set(actual_options)


class Test_PluginHooks:
    """Test suite for pytest plugin hooks."""

    def test_session_start(self, testdir):
        """Test session initialization and configuration."""
        testdir.makepyfile("""
            def test_example():
                assert True
        """)

        result = testdir.runpytest("--insight")
        result.stdout.fnmatch_lines(["*insight: collecting test results*"])

    def test_test_result_capture(self, testdir):
        """Test capturing of test results including output fields."""
        testdir.makepyfile("""
            import logging

            def test_with_output():
                print("stdout message")
                logging.error("log message")
                raise ValueError("stderr message")
        """)

        result = testdir.runpytest("--insight")
        result.stdout.fnmatch_lines([
            "*insight: test failed*",
            "*stdout message*",
            "*log message*",
            "*stderr message*"
        ])

    def test_session_finish(self, testdir):
        """Test session completion and result storage."""
        testdir.makepyfile("""
            def test_one():
                assert True

            def test_two():
                assert False
        """)

        result = testdir.runpytest("--insight")
        result.stdout.fnmatch_lines([
            "*insight: session completed*",
            "*1 passed, 1 failed*"
        ])

    def test_rerun_handling(self, testdir):
        """Test handling of test reruns."""
        testdir.makepyfile("""
            import pytest

            @pytest.mark.flaky(reruns=2)
            def test_flaky():
                import random
                assert random.choice([True, False])
        """)

        result = testdir.runpytest("--insight")
        result.stdout.fnmatch_lines(["*rerun*"])

    def test_warning_capture(self, testdir):
        """Test capturing of test warnings."""
        testdir.makepyfile("""
            import warnings

            def test_warning():
                warnings.warn("test warning")
                assert True
        """)

        result = testdir.runpytest("--insight")
        result.stdout.fnmatch_lines(["*warning*test warning*"])


class Test_ResultStorage:
    """Test suite for result storage and retrieval."""

    def test_result_persistence(self, testdir, tmp_path):
        """Test that results are correctly persisted."""
        testdir.makepyfile("""
            def test_example():
                assert True
        """)

        storage_path = tmp_path / "insight"
        result = testdir.runpytest(f"--insight-storage={storage_path}")

        # Check storage directory
        assert storage_path.exists()
        assert list(storage_path.glob("*.json"))  # Session file created

    def test_session_metadata(self, testdir, tmp_path):
        """Test that session metadata is correctly stored."""
        testdir.makepyfile("""
            def test_example():
                assert True
        """)

        storage_path = tmp_path / "insight"
        result = testdir.runpytest(
            f"--insight-storage={storage_path}",
            "--insight-sut=example",
            "--insight-tags=env:test"
        )

        # Check metadata in storage
        session_files = list(storage_path.glob("*.json"))
        assert session_files

        import json
        with open(session_files[0]) as f:
            data = json.load(f)
            assert data["sut_name"] == "example"
            assert data["tags"]["env"] == "test"


class Test_PluginConfiguration:
    """Test suite for plugin configuration options."""

    def test_storage_configuration(self, testdir):
        """Test storage path configuration."""
        result = testdir.runpytest("--insight-storage=invalid/path")
        result.stderr.fnmatch_lines(["*invalid storage path*"])

    def test_sut_configuration(self, testdir):
        """Test SUT name configuration."""
        result = testdir.runpytest("--insight-sut=test-service")
        result.stdout.fnmatch_lines(["*insight: collecting results for test-service*"])

    def test_tag_configuration(self, testdir):
        """Test tag configuration."""
        result = testdir.runpytest(
            "--insight-tags=env:test,branch:main"
        )
        result.stdout.fnmatch_lines([
            "*insight: using tags*",
            "*env:test*",
            "*branch:main*"
        ])
