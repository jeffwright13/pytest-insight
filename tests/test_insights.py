"""Tests for the insights module."""

from datetime import datetime, timedelta

import pytest
from pytest_insight.insights import Insights
from pytest_insight.models import RerunTestGroup, TestOutcome, TestResult, TestSession


@pytest.fixture
def sample_test_results():
    """Create sample test results for testing."""
    now = datetime.now()
    return [
        TestResult(
            nodeid="test_module.py::test_one",
            outcome=TestOutcome.PASSED,
            start_time=now,
            duration=1.5,
            has_warning=False,
        ),
        TestResult(
            nodeid="test_module.py::test_two",
            outcome=TestOutcome.FAILED,
            start_time=now + timedelta(seconds=2),
            duration=2.5,
            has_warning=True,
        ),
        TestResult(
            nodeid="test_module.py::test_three",
            outcome=TestOutcome.SKIPPED,
            start_time=now + timedelta(seconds=5),
            duration=0.1,
            has_warning=False,
        ),
    ]


@pytest.fixture
def sample_rerun_group():
    """Create a sample rerun group for testing."""
    now = datetime.now()
    rerun_group = RerunTestGroup(nodeid="test_module.py::test_flaky")

    # First run - failed with rerun outcome
    rerun_group.add_test(
        TestResult(
            nodeid="test_module.py::test_flaky",
            outcome=TestOutcome.RERUN,
            start_time=now,
            duration=1.0,
        )
    )

    # Second run - passed
    rerun_group.add_test(
        TestResult(
            nodeid="test_module.py::test_flaky",
            outcome=TestOutcome.PASSED,
            start_time=now + timedelta(seconds=2),
            duration=1.0,
        )
    )

    return rerun_group


@pytest.fixture
def sample_session(sample_test_results, sample_rerun_group):
    """Create a sample test session for testing."""
    now = datetime.now()
    return TestSession(
        session_id="test-session-1",
        sut_name="test-sut",
        session_start_time=now,
        session_stop_time=now + timedelta(seconds=10),
        test_results=sample_test_results,
        rerun_test_groups=[sample_rerun_group],
    )


@pytest.fixture
def sample_sessions(sample_session):
    """Create multiple sample sessions for testing."""
    now = datetime.now()

    # Create a second session with different timing and outcomes
    session2 = TestSession(
        session_id="test-session-2",
        sut_name="test-sut",
        session_start_time=now - timedelta(days=1),
        session_stop_time=now - timedelta(days=1) + timedelta(seconds=8),
        test_results=[
            TestResult(
                nodeid="test_module.py::test_one",
                outcome=TestOutcome.FAILED,  # Different outcome
                start_time=now - timedelta(days=1),
                duration=2.0,  # Different duration
                has_warning=True,  # Different warning
            ),
            TestResult(
                nodeid="test_module.py::test_two",
                outcome=TestOutcome.PASSED,  # Different outcome
                start_time=now - timedelta(days=1) + timedelta(seconds=3),
                duration=1.8,
                has_warning=False,
            ),
        ],
    )

    return [sample_session, session2]


class TestInsightsModuleTests:
    """Tests for the Insights module."""

    def test_insights_initialization(self, monkeypatch, sample_sessions):
        """Test that Insights initializes correctly."""

        # Mock the Analysis class to avoid storage dependencies
        class MockAnalysis:
            def __init__(self):
                self._sessions = sample_sessions

        monkeypatch.setattr("pytest_insight.insights.Analysis", MockAnalysis)

        insights = Insights()
        assert insights.tests is not None
        assert insights.sessions is not None
        assert insights.trends is not None
        assert len(insights.analysis._sessions) == 2

    def test_test_insights(self, monkeypatch, sample_sessions):
        """Test TestInsights functionality."""

        # Mock the Analysis class
        class MockAnalysis:
            def __init__(self):
                self._sessions = sample_sessions

        monkeypatch.setattr("pytest_insight.insights.Analysis", MockAnalysis)

        insights = Insights()

        # Test outcome distribution
        outcome_dist = insights.tests.outcome_distribution()
        assert outcome_dist["total_tests"] == 5  # Total tests across both sessions
        assert len(outcome_dist["outcomes"]) == 3  # PASSED, FAILED, SKIPPED

        # Test flaky tests detection
        flaky = insights.tests.flaky_tests()
        assert flaky["total_flaky"] == 1

        # Test slowest tests
        slow_tests = insights.tests.slowest_tests(limit=3)
        assert len(slow_tests["slowest_tests"]) == 3
        assert slow_tests["slowest_tests"][0][1] > slow_tests["slowest_tests"][1][1]  # Sorted by duration

    def test_session_insights(self, monkeypatch, sample_sessions):
        """Test SessionInsights functionality."""

        # Mock the Analysis class
        class MockAnalysis:
            def __init__(self):
                self._sessions = sample_sessions

            def compare_health(self, base_sessions, target_sessions):
                return {
                    "base_health": {"health_score": {"overall_score": 80}},
                    "target_health": {"health_score": {"overall_score": 85}},
                    "health_difference": 5,
                    "improved": True,
                }

        monkeypatch.setattr("pytest_insight.insights.Analysis", MockAnalysis)

        insights = Insights()

        # Test session metrics
        metrics = insights.sessions.session_metrics()
        assert metrics["total_sessions"] == 2
        assert "avg_duration" in metrics
        assert "failure_rate" in metrics

    def test_trend_insights(self, monkeypatch, sample_sessions):
        """Test TrendInsights functionality."""

        # Mock the Analysis class
        class MockAnalysis:
            def __init__(self):
                self._sessions = sample_sessions

            def compare_health(self, base_sessions, target_sessions):
                return {
                    "base_health": {"health_score": {"overall_score": 80}},
                    "target_health": {"health_score": {"overall_score": 85}},
                    "health_difference": 5,
                    "improved": True,
                }

        monkeypatch.setattr("pytest_insight.insights.Analysis", MockAnalysis)

        insights = Insights()

        # Test duration trends
        duration_trends = insights.trends.duration_trends()
        assert "daily_durations" in duration_trends
        assert "trend_percentage" in duration_trends

        # Test time comparison
        time_comp = insights.trends.time_comparison()
        assert "early_period" in time_comp
        assert "late_period" in time_comp
        assert "health_difference" in time_comp

    def test_console_summary(self, monkeypatch, sample_sessions):
        """Test the console summary functionality."""

        # Mock the Analysis class
        class MockAnalysis:
            def __init__(self):
                self._sessions = sample_sessions

            def health_report(self):
                return {"health_score": {"overall_score": 85}}

            def compare_health(self, base_sessions, target_sessions):
                return {
                    "base_health": {"health_score": {"overall_score": 80}},
                    "target_health": {"health_score": {"overall_score": 85}},
                    "health_difference": 5,
                    "improved": True,
                }

        monkeypatch.setattr("pytest_insight.insights.Analysis", MockAnalysis)

        insights = Insights()
        summary = insights.console_summary()

        assert "health_score" in summary
        assert "failure_rate" in summary
        assert "outcome_distribution" in summary
        assert "slowest_tests" in summary
        assert "failure_trend" in summary
