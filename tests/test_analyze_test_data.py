import argparse
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from pytest_insight.core.comparison import ComparisonResult
from pytest_insight.core.models import TestOutcome, TestResult, TestSession
from pytest_insight.utils.analyze_test_data import analyze_test_data
from rich.console import Console


@pytest.fixture
def mock_console():
    """Fixture providing a mocked rich Console."""
    return MagicMock(spec=Console)


@pytest.fixture
def mock_args():
    """Fixture providing mock command-line arguments."""
    args = MagicMock(spec=argparse.Namespace)
    args.path = None
    args.sut = None
    args.days = None
    args.test = None
    args.profile = None
    args.format = "text"
    args.compare = None
    args.trends = False
    args.list_profiles = False
    args.generate_sample = False
    args.version = False
    return args


@pytest.fixture
def mock_api():
    """Fixture providing a mocked InsightAPI."""
    mock = MagicMock()

    # Setup query mock
    query_mock = MagicMock()
    query_mock.filter_by_sut.return_value = query_mock
    query_mock.filter_by_test_name.return_value = query_mock
    query_mock.date_range.return_value = query_mock
    query_mock.in_last_days.return_value = query_mock
    query_mock.filter_by_version.return_value = query_mock

    # Setup mock sessions
    base_time = datetime.now(timezone.utc) - timedelta(days=1)
    sessions = [
        TestSession(
            sut_name="test-app",
            session_id="session-1",
            session_start_time=base_time,
            session_stop_time=base_time + timedelta(seconds=10),
            session_duration=10.0,
            test_results=[
                TestResult(
                    nodeid="test_module.py::test_func1",
                    outcome=TestOutcome.PASSED,
                    start_time=base_time,
                    duration=1.0,
                ),
                TestResult(
                    nodeid="test_module.py::test_func2",
                    outcome=TestOutcome.FAILED,
                    start_time=base_time + timedelta(seconds=1),
                    duration=2.0,
                ),
            ],
            rerun_test_groups=[],
            session_tags={"env": "test"},
        )
    ]
    query_mock.execute.return_value = sessions
    mock.query.return_value = query_mock

    # Setup compare mock
    compare_mock = MagicMock()

    # Create mock test results for base session
    base_test_results = [
        MagicMock(spec=TestResult),
        MagicMock(spec=TestResult),
        MagicMock(spec=TestResult),
        MagicMock(spec=TestResult),
    ]
    # Configure 3 passed tests and 1 failed test (75% pass rate)
    for i in range(3):
        base_test_results[i].outcome = MagicMock()
        base_test_results[i].outcome.value = "PASSED"
        base_test_results[i].duration = 1.5
    base_test_results[3].outcome = MagicMock()
    base_test_results[3].outcome.value = "FAILED"
    base_test_results[3].duration = 1.5

    # Create mock test results for target session
    target_test_results = [
        MagicMock(spec=TestResult),
        MagicMock(spec=TestResult),
        MagicMock(spec=TestResult),
        MagicMock(spec=TestResult),
    ]
    # Configure 2 passed tests and 2 failed tests (50% pass rate)
    for i in range(2):
        target_test_results[i].outcome = MagicMock()
        target_test_results[i].outcome.value = "PASSED"
        target_test_results[i].duration = 2.0
    for i in range(2, 4):
        target_test_results[i].outcome = MagicMock()
        target_test_results[i].outcome.value = "FAILED"
        target_test_results[i].duration = 2.0

    # Create mock base and target sessions
    base_session = MagicMock(spec=TestSession)
    base_session.test_results = base_test_results

    target_session = MagicMock(spec=TestSession)
    target_session.test_results = target_test_results

    # Setup comparison result with the new structure
    comparison_result = MagicMock(spec=ComparisonResult)
    comparison_result.base_results = base_session
    comparison_result.target_results = target_session
    comparison_result.new_failures = ["test_module.py::test_func3"]
    comparison_result.new_passes = ["test_module.py::test_func4"]

    compare_mock.execute.return_value = comparison_result
    mock.compare.return_value = compare_mock

    return mock


class TestAnalyzeTestData:
    """Test suite for analyze_test_data.py script."""

    @patch("pytest_insight.core.core_api.InsightAPI")
    @patch("pytest_insight.utils.analyze_test_data.Console")
    def test_analyze_data_with_profile_comparison(self, mock_console_class, mock_insight_api, mock_args, mock_api):
        """Test analyze_test_data function with profile comparison."""
        # Setup
        mock_console = mock_console_class.return_value
        mock_insight_api.return_value = mock_api
        mock_args.compare = "profile:other-profile"
        mock_args.profile = "current-profile"

        # Execute
        analyze_test_data(
            data_path=mock_args.path,
            sut_filter=mock_args.sut,
            days=mock_args.days,
            output_format=mock_args.format,
            test_pattern=mock_args.test,
            profile=mock_args.profile,
            compare_with=mock_args.compare,
            show_trends=mock_args.trends,
        )

        # Verify
        # 1. Verify InsightAPI was created with the current profile
        mock_insight_api.assert_any_call(profile="current-profile")

        # 2. Verify InsightAPI was created with the comparison profile
        mock_insight_api.assert_any_call(profile="other-profile")

        # 3. Verify comparison was performed
        mock_api.compare.assert_called_once()
        compare_mock = mock_api.compare.return_value
        compare_mock.execute.assert_called_once()

        # 4. Verify results were displayed
        assert mock_console.print.call_count > 0

        # Check that the profile comparison panel was printed
        panel_calls = [call for call in mock_console.print.call_args_list if "Panel" in str(call)]
        assert any("Comparison Analysis" in str(call) for call in panel_calls)

    @patch("pytest_insight.core.core_api.InsightAPI")
    @patch("pytest_insight.utils.analyze_test_data.Console")
    def test_analyze_data_with_profile_comparison_no_current_profile(
        self, mock_console_class, mock_insight_api, mock_args, mock_api
    ):
        """Test analyze_test_data function with profile comparison when no current profile is specified."""
        # Setup
        mock_insight_api.return_value = mock_api
        mock_args.compare = "profile:other-profile"
        mock_args.profile = None  # No current profile specified

        # Execute
        analyze_test_data(
            data_path=mock_args.path,
            sut_filter=mock_args.sut,
            days=mock_args.days,
            output_format=mock_args.format,
            test_pattern=mock_args.test,
            profile=mock_args.profile,
            compare_with=mock_args.compare,
            show_trends=mock_args.trends,
        )

        # Verify
        # 1. Verify InsightAPI was created with default settings for current data
        mock_insight_api.assert_any_call(profile=None)

        # 2. Verify InsightAPI was created with the comparison profile
        mock_insight_api.assert_any_call(profile="other-profile")

    @patch("pytest_insight.core.core_api.InsightAPI")
    @patch("pytest_insight.utils.analyze_test_data.Console")
    def test_analyze_data_with_profile_comparison_no_sessions(
        self, mock_console_class, mock_insight_api, mock_args, mock_api
    ):
        """Test analyze_test_data function with profile comparison when no sessions are found in comparison profile."""
        # Setup
        mock_console = mock_console_class.return_value
        mock_insight_api.return_value = mock_api
        mock_args.compare = "profile:empty-profile"

        # Make the comparison profile return no sessions
        compare_query = MagicMock()
        compare_query.filter_by_sut.return_value = compare_query
        compare_query.filter_by_test_name.return_value = compare_query
        compare_query.in_last_days.return_value = compare_query
        compare_query.execute.return_value = []  # Empty list of sessions

        # Create a second API instance for the comparison profile
        second_api = MagicMock()
        second_api.query.return_value = compare_query

        # Make the InsightAPI constructor return different instances
        mock_insight_api.side_effect = [mock_api, second_api]

        # Execute
        analyze_test_data(
            data_path=mock_args.path,
            sut_filter=mock_args.sut,
            days=mock_args.days,
            output_format=mock_args.format,
            test_pattern=mock_args.test,
            profile=mock_args.profile,
            compare_with=mock_args.compare,
            show_trends=mock_args.trends,
        )

        # Verify
        # 1. Verify warning message was displayed
        warning_calls = [
            call for call in mock_console.print.call_args_list if "No sessions found in profile" in str(call)
        ]
        assert len(warning_calls) > 0

    @patch("pytest_insight.core.core_api.InsightAPI")
    @patch("pytest_insight.utils.analyze_test_data.Console")
    def test_analyze_data_with_profile_comparison_error(
        self, mock_console_class, mock_insight_api, mock_args, mock_api
    ):
        """Test analyze_test_data function with profile comparison when an error occurs."""
        # Setup
        mock_console = mock_console_class.return_value
        mock_insight_api.return_value = mock_api
        mock_args.compare = "profile:error-profile"

        # Make the comparison raise an exception
        compare_mock = mock_api.compare.return_value
        compare_mock.execute.side_effect = Exception("Test error")

        # Execute
        analyze_test_data(
            data_path=mock_args.path,
            sut_filter=mock_args.sut,
            days=mock_args.days,
            output_format=mock_args.format,
            test_pattern=mock_args.test,
            profile=mock_args.profile,
            compare_with=mock_args.compare,
            show_trends=mock_args.trends,
        )

        # Verify
        # 1. Verify error message was displayed
        error_calls = [
            call for call in mock_console.print.call_args_list if "Error comparing with profile" in str(call)
        ]
        assert len(error_calls) > 0

    @patch("pytest_insight.core.core_api.InsightAPI")
    @patch("pytest_insight.utils.analyze_test_data.Console")
    def test_analyze_data_with_unknown_comparison_type(self, mock_console_class, mock_insight_api, mock_args, mock_api):
        """Test analyze_test_data function with an unknown comparison type."""
        # Setup
        mock_console = mock_console_class.return_value
        mock_insight_api.return_value = mock_api
        mock_args.compare = "unknown:value"

        # Execute
        analyze_test_data(
            data_path=mock_args.path,
            sut_filter=mock_args.sut,
            days=mock_args.days,
            output_format=mock_args.format,
            test_pattern=mock_args.test,
            profile=mock_args.profile,
            compare_with=mock_args.compare,
            show_trends=mock_args.trends,
        )

        # Verify
        # 1. Verify error message was displayed
        error_calls = [call for call in mock_console.print.call_args_list if "Unknown comparison type" in str(call)]
        assert len(error_calls) > 0

        # 2. Verify help message was displayed
        help_calls = [call for call in mock_console.print.call_args_list if "Valid formats" in str(call)]
        assert len(help_calls) > 0
        assert any("profile:name" in str(call) for call in help_calls)
