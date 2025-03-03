# import pytest
# from pytest_mock import MockerFixture

# from pytest_insight.models import TestSession, TestResult, TestOutcome
# from pytest_insight.filters import TestFilter

# class Test_TestFilter:
#     """Test suite for TestFilter functionality."""

#     def test_filter_initialization(self, mock_session_no_reruns):
#         """Test basic initialization of TestFilter with no criteria."""
#         test_filter = TestFilter()
#         assert test_filter is not None
#         # Start with simplest possible test - filter accepts everything
#         assert test_filter.matches(mock_session_no_reruns)


from datetime import datetime, timedelta

from pytest_insight.filters import TestFilter
from pytest_insight.models import TestResult, TestSession


class Test_TestFilter:
    """Test suite for TestFilter functionality."""

    def test_filter_initialization(self, mock_session_no_reruns):
        """Test basic initialization of TestFilter."""
        test_filter = TestFilter()
        filtered = test_filter.filter_sessions([mock_session_no_reruns])
        assert len(filtered) == 1
        assert filtered[0] == mock_session_no_reruns

    def test_sut_filter(self, mock_session_no_reruns):
        """Test filtering by SUT name."""
        test_filter = TestFilter(sut="test_sut")
        filtered = test_filter.filter_sessions([mock_session_no_reruns])
        assert len(filtered) == 1
        assert filtered[0].sut_name == "test_sut"

    def test_days_filter(self, mock_session_no_reruns):
        """Test filtering by days."""
        test_filter = TestFilter(days=7)
        filtered = test_filter.filter_sessions([mock_session_no_reruns])
        assert len(filtered) == 1

        # Test old session gets filtered out
        old_session = TestSession(
            sut_name="test_sut",
            session_id="old-123",
            session_start_time=datetime.now() - timedelta(days=10),
            session_stop_time=datetime.now() - timedelta(days=10),
            test_results=[],
            rerun_test_groups=[],
        )
        filtered = test_filter.filter_sessions([old_session])
        assert len(filtered) == 0

    def test_outcome_filter(self, mock_test_result_pass, mock_test_result_fail):
        """Test filtering by test outcome."""
        test_filter = TestFilter(outcome="PASSED")
        filtered = test_filter.filter_results([mock_test_result_pass, mock_test_result_fail])
        assert len(filtered) == 1
        assert filtered[0].outcome == "PASSED"

    def test_warnings_filter(self, mock_test_result_pass):
        """Test filtering by warning presence."""
        # Create result with warning
        warning_result = TestResult(
            nodeid="test_warn.py::test_warning",
            outcome="PASSED",
            start_time=datetime.now(),
            duration=1.0,
            has_warning=True,
        )

        test_filter = TestFilter(has_warnings=True)
        filtered = test_filter.filter_results(
            [
                mock_test_result_pass,  # no warning
                warning_result,
            ]
        )
        assert len(filtered) == 1
        assert filtered[0].has_warning

    def test_nodeid_contains_filter(self, mock_test_result_pass):
        """Test filtering by nodeid pattern."""
        test_filter = TestFilter(nodeid_contains="test_case")
        filtered = test_filter.filter_results([mock_test_result_pass])
        assert len(filtered) == 1
        assert "test_case" in filtered[0].nodeid

    def test_multiple_filters(self, mock_session_no_reruns, mock_test_result_pass):
        """Test combining multiple filters."""
        test_filter = TestFilter(sut="test_sut", days=7, outcome="PASSED")

        # First filter sessions
        filtered_sessions = test_filter.filter_sessions([mock_session_no_reruns])
        assert len(filtered_sessions) == 1

        # Then filter results within session
        filtered_results = test_filter.filter_results([mock_test_result_pass])
        assert len(filtered_results) == 1
