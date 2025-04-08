"""Tests for the insights module."""

from datetime import datetime, timedelta

import pytest

from pytest_insight.core.insights import Insights
from pytest_insight.core.models import (
    RerunTestGroup,
    TestOutcome,
    TestResult,
    TestSession,
)


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

        monkeypatch.setattr("pytest_insight.core.insights.Analysis", MockAnalysis)

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

        monkeypatch.setattr("pytest_insight.core.insights.Analysis", MockAnalysis)

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
        assert (
            slow_tests["slowest_tests"][0][1] > slow_tests["slowest_tests"][1][1]
        )  # Sorted by duration

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

        monkeypatch.setattr("pytest_insight.core.insights.Analysis", MockAnalysis)

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

        monkeypatch.setattr("pytest_insight.core.insights.Analysis", MockAnalysis)

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

    def test_console_summary(self, monkeypatch, mocker, sample_sessions):
        """Test the console summary functionality."""
        # Create a mock Analysis instance with our sample sessions
        mock_analysis = mocker.MagicMock()
        mock_analysis._sessions = sample_sessions

        # Mock health_report to return a simple dict
        mock_analysis.health_report.return_value = {
            "health_score": {
                "overall_score": 85,
                "stability_score": 90,
                "performance_score": 80,
                "warning_score": 85,
            },
            "recommendations": ["Fix flaky tests", "Improve test performance"],
        }

        # Create insights with our mock analysis
        insights = Insights(analysis=mock_analysis)

        # Mock the component insights methods to return test data
        mock_test_insights = mocker.MagicMock()
        mock_test_insights.outcome_distribution.return_value = {
            "total_tests": 10,
            "outcomes": {
                TestOutcome.PASSED: {"count": 7},
                TestOutcome.FAILED: {"count": 2},
                TestOutcome.SKIPPED: {"count": 1},
            },
        }
        mock_test_insights.flaky_tests.return_value = {
            "total_flaky": 1,
            "most_flaky": [
                ("test_module.py::test_flaky", {"reruns": 2, "pass_rate": 0.5})
            ],
        }
        mock_test_insights.slowest_tests.return_value = {
            "slowest_tests": [
                ("test_module.py::test_one", 1.5),
                ("test_module.py::test_two", 2.5),
            ]
        }

        mock_session_insights = mocker.MagicMock()
        mock_session_insights.session_metrics.return_value = {
            "avg_duration": 5.0,
            "failure_rate": 0.2,
            "warning_rate": 0.1,
        }

        mock_trend_insights = mocker.MagicMock()
        mock_trend_insights.failure_trends.return_value = {
            "trend_percentage": 5.0,
            "improving": True,
        }

        # Replace the component insights with our mocks
        insights.tests = mock_test_insights
        insights.sessions = mock_session_insights
        insights.trends = mock_trend_insights

        # Get the summary
        summary = insights.console_summary()

        # Verify the summary contains the expected keys
        assert "health_score" in summary
        assert "stability_score" in summary
        assert "performance_score" in summary
        assert "warning_score" in summary
        assert "failure_rate" in summary
        assert "warning_rate" in summary
        assert "avg_duration" in summary
        assert "outcome_distribution" in summary
        assert "slowest_tests" in summary
        assert "failure_trend" in summary

    def test_insights_with_profiles(self, monkeypatch, mocker):
        """Test insights initialization with profiles."""
        # Create a mock storage
        mock_storage = mocker.MagicMock()

        # Mock the get_storage_instance function to return our mock storage directly
        mock_get_storage = mocker.patch(
            "pytest_insight.core.insights.get_storage_instance"
        )
        mock_get_storage.return_value = mock_storage

        # Mock the Analysis class
        mock_analysis = mocker.MagicMock()
        monkeypatch.setattr("pytest_insight.core.insights.Analysis", mock_analysis)

        # Initialize insights with profile
        insights = Insights(profile_name="test_profile")

        # Verify get_storage_instance was called with correct profile
        mock_get_storage.assert_called_once_with(profile_name="test_profile")

        # Verify Analysis was created with the mock storage
        mock_analysis.assert_called_once_with(storage=mock_storage)

        # Verify profile name was stored
        assert insights._profile_name == "test_profile"

    def test_with_profile_method(self, monkeypatch, mocker):
        """Test with_profile method."""
        # Create a mock storage
        mock_storage = mocker.MagicMock()

        # Mock the get_storage_instance function to return our mock storage directly
        mock_get_storage = mocker.patch(
            "pytest_insight.core.insights.get_storage_instance"
        )
        mock_get_storage.return_value = mock_storage

        # Mock the Analysis class
        mock_analysis = mocker.MagicMock()
        mock_analysis_instance = mocker.MagicMock()
        mock_analysis.return_value = mock_analysis_instance
        monkeypatch.setattr("pytest_insight.core.insights.Analysis", mock_analysis)

        # Create insights and call with_profile
        insights = Insights()
        result = insights.with_profile("test_profile")

        # Verify get_storage_instance was called with correct profile
        mock_get_storage.assert_called_once_with(profile_name="test_profile")

        # Verify Analysis was created with the mock storage
        mock_analysis.assert_called_with(storage=mock_storage)

        # Verify profile name was stored
        assert insights._profile_name == "test_profile"

        # Verify method returns self for chaining
        assert result is insights

    def test_with_query_preserves_profile(self, monkeypatch, mocker, sample_sessions):
        """Test with_query method preserves profile."""
        # Create a mock storage
        mock_storage = mocker.MagicMock()

        # Mock the get_storage_instance function to return our mock storage directly
        mock_get_storage = mocker.patch(
            "pytest_insight.core.insights.get_storage_instance"
        )
        mock_get_storage.return_value = mock_storage

        # Mock the Analysis class
        mock_analysis = mocker.MagicMock()
        mock_analysis_instance = mocker.MagicMock()
        mock_analysis_instance._sessions = sample_sessions

        # Mock the with_query method to return a new mock analysis
        filtered_analysis = mocker.MagicMock()
        filtered_analysis._sessions = sample_sessions
        mock_analysis_instance.with_query.return_value = filtered_analysis

        mock_analysis.return_value = mock_analysis_instance
        monkeypatch.setattr("pytest_insight.core.insights.Analysis", mock_analysis)

        # Create insights with profile and call with_query
        insights = Insights(profile_name="test_profile")
        result = insights.with_query(lambda q: q.for_sut("test-sut"))

        # Verify the profile was preserved in the new Insights instance
        assert result._profile_name == "test_profile"

    def test_convenience_functions(self, monkeypatch, mocker):
        """Test module-level convenience functions."""
        # Create a mock storage
        mock_storage = mocker.MagicMock()

        # Mock the get_storage_instance function to return our mock storage directly
        mock_get_storage = mocker.patch(
            "pytest_insight.core.insights.get_storage_instance"
        )
        mock_get_storage.return_value = mock_storage

        # Import the convenience functions
        from pytest_insight.core.insights import insights, insights_with_profile

        # Mock the Insights class
        mock_insights_class = mocker.MagicMock()
        monkeypatch.setattr(
            "pytest_insight.core.insights.Insights", mock_insights_class
        )

        # Test insights function
        insights(profile_name="test_profile")
        mock_insights_class.assert_called_with(
            analysis=None, profile_name="test_profile"
        )

        # Test insights_with_profile function
        insights_with_profile("test_profile")
        mock_insights_class.assert_called_with(profile_name="test_profile")
