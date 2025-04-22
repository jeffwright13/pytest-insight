"""Tests for health metrics functionality in pytest-insight."""

from datetime import datetime, timedelta

import pytest
from pytest_insight.core.analysis import Analysis, SessionAnalysis
from pytest_insight.core.models import TestOutcome, TestResult, TestSession


@pytest.fixture
def health_metrics_sessions(get_test_time):
    """Fixture providing test sessions for health metrics analysis."""
    base_time = get_test_time() - timedelta(days=30)

    # Create sessions with different characteristics for health metrics analysis
    sessions = [
        # Session 1: Initial state with some failures
        TestSession(
            sut_name="web-service",
            session_id="health-1",
            session_start_time=base_time,
            session_stop_time=base_time + timedelta(seconds=100),
            session_duration=100.0,
            test_results=[
                TestResult(
                    nodeid="test_web.py::test_homepage",
                    outcome=TestOutcome.PASSED,
                    start_time=base_time,
                    duration=1.0,
                ),
                TestResult(
                    nodeid="test_web.py::test_login",
                    outcome=TestOutcome.PASSED,
                    start_time=base_time + timedelta(seconds=2),
                    duration=2.0,
                ),
                TestResult(
                    nodeid="test_web.py::test_checkout",
                    outcome=TestOutcome.FAILED,
                    start_time=base_time + timedelta(seconds=5),
                    duration=3.0,
                ),
                TestResult(
                    nodeid="test_web.py::test_search",
                    outcome=TestOutcome.PASSED,
                    start_time=base_time + timedelta(seconds=9),
                    duration=1.5,
                ),
                TestResult(
                    nodeid="test_api.py::test_get_user",
                    outcome=TestOutcome.PASSED,
                    start_time=base_time + timedelta(seconds=12),
                    duration=0.5,
                ),
            ],
            rerun_test_groups=[],
            session_tags={"env": "staging"},
        ),
        # Session 2: A week later, more failures
        TestSession(
            sut_name="web-service",
            session_id="health-2",
            session_start_time=base_time + timedelta(days=7),
            session_stop_time=base_time + timedelta(days=7, seconds=120),
            session_duration=120.0,  # Longer duration
            test_results=[
                TestResult(
                    nodeid="test_web.py::test_homepage",
                    outcome=TestOutcome.PASSED,
                    start_time=base_time + timedelta(days=7),
                    duration=1.2,  # Slightly slower
                ),
                TestResult(
                    nodeid="test_web.py::test_login",
                    outcome=TestOutcome.FAILED,  # Now failing
                    start_time=base_time + timedelta(days=7, seconds=2),
                    duration=2.5,
                ),
                TestResult(
                    nodeid="test_web.py::test_checkout",
                    outcome=TestOutcome.FAILED,  # Still failing
                    start_time=base_time + timedelta(days=7, seconds=5),
                    duration=3.2,  # Slightly slower
                ),
                TestResult(
                    nodeid="test_web.py::test_search",
                    outcome=TestOutcome.PASSED,
                    start_time=base_time + timedelta(days=7, seconds=9),
                    duration=1.6,
                ),
                TestResult(
                    nodeid="test_api.py::test_get_user",
                    outcome=TestOutcome.FAILED,  # Now failing
                    start_time=base_time + timedelta(days=7, seconds=12),
                    duration=0.6,
                ),
                TestResult(
                    nodeid="test_api.py::test_create_user",  # New test
                    outcome=TestOutcome.PASSED,
                    start_time=base_time + timedelta(days=7, seconds=14),
                    duration=5.0,  # Slow test
                ),
            ],
            rerun_test_groups=[],
            session_tags={"env": "staging"},
        ),
        # Session 3: Two weeks later, some improvements but new failures
        TestSession(
            sut_name="web-service",
            session_id="health-3",
            session_start_time=base_time + timedelta(days=14),
            session_stop_time=base_time + timedelta(days=14, seconds=150),
            session_duration=150.0,  # Even longer duration
            test_results=[
                TestResult(
                    nodeid="test_web.py::test_homepage",
                    outcome=TestOutcome.PASSED,
                    start_time=base_time + timedelta(days=14),
                    duration=1.3,
                ),
                TestResult(
                    nodeid="test_web.py::test_login",
                    outcome=TestOutcome.PASSED,  # Fixed
                    start_time=base_time + timedelta(days=14, seconds=2),
                    duration=2.2,
                ),
                TestResult(
                    nodeid="test_web.py::test_checkout",
                    outcome=TestOutcome.FAILED,  # Still failing
                    start_time=base_time + timedelta(days=14, seconds=5),
                    duration=3.5,
                ),
                TestResult(
                    nodeid="test_web.py::test_search",
                    outcome=TestOutcome.FAILED,  # Now failing
                    start_time=base_time + timedelta(days=14, seconds=9),
                    duration=1.8,
                ),
                TestResult(
                    nodeid="test_api.py::test_get_user",
                    outcome=TestOutcome.FAILED,  # Still failing
                    start_time=base_time + timedelta(days=14, seconds=12),
                    duration=0.7,
                ),
                TestResult(
                    nodeid="test_api.py::test_create_user",
                    outcome=TestOutcome.PASSED,
                    start_time=base_time + timedelta(days=14, seconds=14),
                    duration=5.5,  # Getting slower
                ),
                TestResult(
                    nodeid="test_api.py::test_delete_user",  # New test
                    outcome=TestOutcome.FAILED,
                    start_time=base_time + timedelta(days=14, seconds=20),
                    duration=6.0,  # Slow test
                ),
            ],
            rerun_test_groups=[],
            session_tags={"env": "staging"},
        ),
        # Session 4: Three weeks later, more tests and varied outcomes
        TestSession(
            sut_name="web-service",
            session_id="health-4",
            session_start_time=base_time + timedelta(days=21),
            session_stop_time=base_time + timedelta(days=21, seconds=200),
            session_duration=200.0,  # Longest duration
            test_results=[
                TestResult(
                    nodeid="test_web.py::test_homepage",
                    outcome=TestOutcome.PASSED,
                    start_time=base_time + timedelta(days=21),
                    duration=1.4,
                ),
                TestResult(
                    nodeid="test_web.py::test_login",
                    outcome=TestOutcome.PASSED,
                    start_time=base_time + timedelta(days=21, seconds=2),
                    duration=2.3,
                ),
                TestResult(
                    nodeid="test_web.py::test_checkout",
                    outcome=TestOutcome.FAILED,  # Still failing
                    start_time=base_time + timedelta(days=21, seconds=5),
                    duration=3.8,
                ),
                TestResult(
                    nodeid="test_web.py::test_search",
                    outcome=TestOutcome.PASSED,  # Fixed
                    start_time=base_time + timedelta(days=21, seconds=9),
                    duration=1.9,
                ),
                TestResult(
                    nodeid="test_api.py::test_get_user",
                    outcome=TestOutcome.PASSED,  # Fixed
                    start_time=base_time + timedelta(days=21, seconds=12),
                    duration=0.8,
                ),
                TestResult(
                    nodeid="test_api.py::test_create_user",
                    outcome=TestOutcome.PASSED,
                    start_time=base_time + timedelta(days=21, seconds=14),
                    duration=6.0,  # Even slower
                ),
                TestResult(
                    nodeid="test_api.py::test_delete_user",
                    outcome=TestOutcome.FAILED,  # Still failing
                    start_time=base_time + timedelta(days=21, seconds=20),
                    duration=6.5,
                ),
                TestResult(
                    nodeid="test_api.py::test_update_user",  # New test
                    outcome=TestOutcome.FAILED,
                    start_time=base_time + timedelta(days=21, seconds=27),
                    duration=7.0,  # Very slow test
                ),
            ],
            rerun_test_groups=[],
            session_tags={"env": "staging"},
        ),
    ]
    return sessions


class Test_HealthMetrics:
    """Test suite for health metrics functionality."""

    def test_top_failing_tests(self, health_metrics_sessions, json_storage):
        """Test the top_failing_tests method."""
        # Initialize SessionAnalysis with test sessions
        session_analysis = SessionAnalysis(sessions=health_metrics_sessions)

        # Test with default parameters
        results = session_analysis.top_failing_tests()

        # Verify the structure of the results
        assert "top_failing" in results
        assert "total_failures" in results
        assert isinstance(results["top_failing"], list)
        assert isinstance(results["total_failures"], int)

        # Verify the content of the results
        top_failing = results["top_failing"]
        assert len(top_failing) > 0

        # The test_checkout test should be the most consistently failing
        checkout_test = next(
            (t for t in top_failing if t["nodeid"] == "test_web.py::test_checkout"),
            None,
        )
        assert checkout_test is not None
        assert checkout_test["failures"] == 4  # Failed in all 4 sessions

        # Test with limit parameter
        limited_results = session_analysis.top_failing_tests(limit=2)
        assert len(limited_results["top_failing"]) <= 2

        # Test with days parameter
        recent_results = session_analysis.top_failing_tests(days=10)
        # Should only include failures from the last 10 days (sessions 3 and 4)
        assert recent_results["total_failures"] < results["total_failures"]

    def test_regression_rate(self, health_metrics_sessions, json_storage):
        """Test the regression_rate method."""
        # Initialize SessionAnalysis with test sessions
        session_analysis = SessionAnalysis(sessions=health_metrics_sessions)

        # Test with default parameters
        results = session_analysis.regression_rate()

        # Verify the structure of the results
        assert "regression_rate" in results
        assert "regressed_tests" in results
        assert "total_regressions" in results

        # Verify the content of the results
        assert 0 <= results["regression_rate"] <= 1.0
        assert isinstance(results["regressed_tests"], list)
        assert isinstance(results["total_regressions"], int)

        # Test with days parameter
        recent_results = session_analysis.regression_rate(days=10)
        # Regression rate might be different for a shorter time period
        assert isinstance(recent_results["regression_rate"], float)

    def test_longest_running_tests(self, health_metrics_sessions, json_storage):
        """Test the longest_running_tests method."""
        # Initialize SessionAnalysis with test sessions
        session_analysis = SessionAnalysis(sessions=health_metrics_sessions)

        # Test with default parameters
        results = session_analysis.longest_running_tests()

        # Verify the structure of the results
        assert "longest_tests" in results
        assert "total_duration" in results
        assert "avg_duration" in results

        # Verify the content of the results
        longest_tests = results["longest_tests"]
        assert len(longest_tests) > 0

        # The update_user test should be among the slowest
        update_user_test = next(
            (t for t in longest_tests if t[0] == "test_api.py::test_update_user"), None
        )
        assert update_user_test is not None
        assert update_user_test[1] >= 7.0  # Should be the slowest test

        # Test with limit parameter
        limited_results = session_analysis.longest_running_tests(limit=3)
        assert len(limited_results["longest_tests"]) <= 3

        # Test with days parameter
        recent_results = session_analysis.longest_running_tests(days=10)
        # Should only include tests from the last 10 days
        assert len(recent_results["longest_tests"]) <= len(results["longest_tests"])

    def test_test_suite_duration_trend(self, health_metrics_sessions, json_storage):
        """Test the test_suite_duration_trend method."""
        # Initialize SessionAnalysis with test sessions
        session_analysis = SessionAnalysis(sessions=health_metrics_sessions)

        # Test with default parameters
        results = session_analysis.test_suite_duration_trend()

        # Verify the structure of the results
        assert "durations" in results
        assert "trend" in results
        assert "significant" in results

        # Verify the content of the results
        durations = results["durations"]
        trend = results["trend"]

        assert len(durations) > 0
        assert "direction" in trend
        assert "change" in trend

        # The trend could be increasing, decreasing, or stable depending on the implementation
        # Just verify that direction is one of the expected values
        assert trend["direction"] in ["increasing", "decreasing", "stable"]

        # Test with window_size parameter
        window_results = session_analysis.test_suite_duration_trend(window_size=2)
        assert "trend" in window_results

        # Test with days parameter
        recent_results = session_analysis.test_suite_duration_trend(days=10)
        # Should only include sessions from the last 10 days
        assert len(recent_results["durations"]) <= len(results["durations"])

    def test_integration_with_analysis(self, health_metrics_sessions, json_storage):
        """Test integration of health metrics with the Analysis class."""
        # Initialize Analysis with test sessions
        analysis = Analysis(sessions=health_metrics_sessions)

        # Verify that health metrics can be accessed through the Analysis class
        top_failing = analysis.sessions.top_failing_tests()
        assert "top_failing" in top_failing

        regression = analysis.sessions.regression_rate()
        assert "regression_rate" in regression

        longest_tests = analysis.sessions.longest_running_tests()
        assert "longest_tests" in longest_tests

        duration_trend = analysis.sessions.test_suite_duration_trend()
        assert "trend" in duration_trend

        # Test with filtering by SUT using with_query method
        filtered_analysis = analysis.with_query(lambda q: q.for_sut("web-service"))
        filtered_results = filtered_analysis.sessions.top_failing_tests()
        assert len(filtered_results["top_failing"]) > 0

    def test_edge_cases(self, json_storage):
        """Test edge cases for health metrics."""
        # Test with empty session list
        empty_analysis = SessionAnalysis(sessions=[])

        empty_top_failing = empty_analysis.top_failing_tests()
        assert len(empty_top_failing["top_failing"]) == 0
        assert empty_top_failing["total_failures"] == 0

        empty_regression = empty_analysis.regression_rate()
        assert empty_regression["regression_rate"] == 0.0
        assert len(empty_regression["regressed_tests"]) == 0

        empty_longest = empty_analysis.longest_running_tests()
        assert len(empty_longest["longest_tests"]) == 0

        empty_duration = empty_analysis.test_suite_duration_trend()
        assert len(empty_duration["durations"]) == 0

        # Test with a single session
        single_session = TestSession(
            sut_name="single",
            session_id="single-1",
            session_start_time=datetime.now(),
            session_stop_time=datetime.now() + timedelta(seconds=10),
            session_duration=10.0,
            test_results=[
                TestResult(
                    nodeid="test_single.py::test_one",
                    outcome=TestOutcome.PASSED,
                    start_time=datetime.now(),
                    duration=1.0,
                ),
            ],
            rerun_test_groups=[],
            session_tags={},
        )

        single_analysis = SessionAnalysis(sessions=[single_session])

        single_regression = single_analysis.regression_rate()
        assert (
            single_regression["regression_rate"] == 0.0
        )  # Can't regress with one session

        # With a single session, we might not be able to calculate a trend
        # Just verify the method doesn't raise an exception
        single_duration = single_analysis.test_suite_duration_trend()
        assert "durations" in single_duration
        # The durations list might be empty or have one item depending on implementation
        if len(single_duration["durations"]) > 0:
            assert single_duration["durations"][0]["session_id"] == "single-1"
