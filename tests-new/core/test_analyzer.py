import re
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from unittest.mock import patch

import pytest

from pytest_insight.core.analyzer import InsightAnalyzer, SessionFilter
from pytest_insight.models import TestResult, TestSession
from pytest_insight.storage import InMemoryStorage

@pytest.fixture
def start_time():
    """Fixture providing consistent start time."""
    return datetime.strptime("2021-01-01T00:00:00", "%Y-%m-%dT%H:%M:%S")

@pytest.fixture
def storage(start_time):
    """Fixture providing storage with test data."""
    return InMemoryStorage(sessions=[
        TestSession(
            sut_name="api",
            session_id="session-1",
            session_start_time=start_time,
            session_duration=2.0,
            test_results=[
                TestResult(
                    nodeid="test_api.py::test_get",
                    outcome="passed",
                    start_time=start_time,
                    duration=1.0
                ),
                TestResult(
                    nodeid="test_api.py::test_post",
                    outcome="failed",
                    start_time=start_time,
                    duration=1.0
                ),
            ]
        ),
        TestSession(
            sut_name="api",
            session_id="session-2",
            session_start_time=start_time,
            session_duration=3.0,
            test_results=[
                TestResult(
                    nodeid="test_users.py::test_login",
                    outcome="passed",
                    start_time=start_time,
                    duration=1.0
                ),
                TestResult(
                    nodeid="test_users.py::test_logout",
                    outcome="failed",
                    start_time=start_time,
                    duration=1.0
                ),
                TestResult(
                    nodeid="test_api.py::test_get",
                    outcome="skipped",
                    start_time=start_time,
                    duration=1.0
                ),
            ]
        )
    ])

class TestSessionFiltering:
    """Test suite for session filtering functionality."""

    def test_get_sessions_filters_by_nodeid_pattern(self, storage):
        """Test filtering sessions by test node ID pattern."""
        analyzer = InsightAnalyzer(storage)

        # Test exact match
        sessions = analyzer.get_sessions(
            SessionFilter(nodeid="test_api.py::test_get")
        )
        assert len(sessions) == 2

        # Test pattern match
        sessions = analyzer.get_sessions(
            SessionFilter(nodeid=re.compile("test_api.*"))
        )
        assert len(sessions) == 2

    def test_get_sessions_filters_by_outcome(self, storage):
        """Test filtering sessions by test outcome."""
        analyzer = InsightAnalyzer(storage)

        sessions = analyzer.get_sessions(
            SessionFilter(outcome="failed")
        )
        assert len(sessions) == 2

    def test_get_sessions_filters_by_sut(self, storage):
        """Test filtering sessions by SUT."""
        analyzer = InsightAnalyzer(storage)

        sessions = analyzer.get_sessions(
            SessionFilter(sut="api")
        )
        assert len(sessions) == 2

        sessions = analyzer.get_sessions(
            SessionFilter(sut="nonexistent")
        )
        assert len(sessions) == 0

    def test_get_sessions_with_time_window(self, storage, start_time):
        """Test filtering sessions by time window."""
        analyzer = InsightAnalyzer(storage)

        # Mock datetime.now() to return a fixed time
        mock_now = start_time + timedelta(hours=1)  # 1 hour after start_time

        with patch('pytest_insight.core.analyzer.datetime') as mock_datetime:
            mock_datetime.now.return_value = mock_now

            # Sessions within window
            sessions = analyzer.get_sessions(
                SessionFilter(timespan=timedelta(days=1))
            )
            assert len(sessions) == 2  # Both sessions should be within 1 day window

            # Sessions outside window
            sessions = analyzer.get_sessions(
                SessionFilter(timespan=timedelta(minutes=30))  # 30 min window
            )
            assert len(sessions) == 0  # No sessions in last 30 minutes

class TestAnalytics:
    """Test suite for analytics functionality."""

    def test_calculate_failure_rate(self, storage):
        """Test failure rate calculation."""
        analyzer = InsightAnalyzer(storage)

        # Get results for specific test
        results = analyzer.get_test_results(
            SessionFilter(nodeid="test_api.py::test_get")
        )

        # Verify we only got the exact test we wanted
        assert all(r.nodeid == "test_api.py::test_get" for r in results)
        assert len(results) == 2  # One passed, one skipped

        # Calculate failure rate (should be 0.0 as none failed)
        assert analyzer.calculate_failure_rate(results) == 0.0

        # Test with a failing test
        results = analyzer.get_test_results(
            SessionFilter(nodeid="test_api.py::test_post")
        )
        assert len(results) == 1  # One failed
        assert analyzer.calculate_failure_rate(results) == 1.0

    def test_calculate_failure_rate_with_skipped(self, storage):
        """Test failure rate calculation ignores skipped tests."""
        analyzer = InsightAnalyzer(storage)

        # Test with only skipped tests
        results = [
            TestResult(
                nodeid="test_skip.py::test_case",
                outcome="skipped",
                start_time=datetime.now(),
                duration=1.0
            )
        ]
        assert analyzer.calculate_failure_rate(results) == 0.0

    def test_detect_trends(self, storage):
        """Test trend detection in test metrics."""
        analyzer = InsightAnalyzer(storage)

        # Create increasing duration trend
        results = [
            TestResult(
                nodeid="test_1",
                outcome="passed",
                start_time=datetime.now() + timedelta(minutes=i),
                duration=1.0 + i * 0.5
            )
            for i in range(5)
        ]

        trends = analyzer.detect_trends(results, metric="duration")
        assert trends["trend"] == "increasing"
        assert len(trends["data_points"]) == 5
