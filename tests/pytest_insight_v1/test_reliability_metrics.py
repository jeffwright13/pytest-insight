"""Unit tests for the reliability metrics in TestInsights."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

from pytest_insight.core.insights import TestInsights
from pytest_insight.core.models import RerunTestGroup, TestOutcome, TestResult


class TestReliabilityMetrics:
    """Tests for the reliability metrics in TestInsights."""

    def test_reliability_index_calculation(self):
        """Test that reliability index is calculated correctly."""
        # Create mock sessions with rerun test groups
        session1 = MagicMock()
        session1.session_id = "session1"
        session1.test_results = [MagicMock() for _ in range(10)]  # 10 tests total

        # Create rerun test groups
        rerun_group1 = RerunTestGroup(nodeid="test1")
        current_time = datetime.now()
        test1_attempt1 = TestResult(
            nodeid="test1",
            outcome=TestOutcome.FAILED,
            start_time=current_time,
            duration=1.0,
        )
        test1_attempt2 = TestResult(
            nodeid="test1",
            outcome=TestOutcome.PASSED,
            start_time=current_time + timedelta(seconds=5),
            duration=1.0,
        )
        rerun_group1.add_test(test1_attempt1)
        rerun_group1.add_test(test1_attempt2)

        rerun_group2 = RerunTestGroup(nodeid="test2")
        test2_attempt1 = TestResult(
            nodeid="test2",
            outcome=TestOutcome.FAILED,
            start_time=current_time + timedelta(seconds=10),
            duration=1.0,
        )
        test2_attempt2 = TestResult(
            nodeid="test2",
            outcome=TestOutcome.FAILED,
            start_time=current_time + timedelta(seconds=15),
            duration=1.0,
        )
        rerun_group2.add_test(test2_attempt1)
        rerun_group2.add_test(test2_attempt2)

        session1.rerun_test_groups = [rerun_group1, rerun_group2]

        # Create insights with the mock session
        insights = TestInsights([session1])

        # Get reliability metrics
        metrics = insights.test_reliability_metrics()

        # Verify reliability index: 8/10 tests are stable (80%)
        assert metrics["reliability_index"] == 80.0

        # Verify rerun recovery rate: 1/2 rerun groups passed (50%)
        assert metrics["rerun_recovery_rate"] == 50.0

        # Verify unstable tests count
        assert metrics["total_unstable"] == 2

        # Verify health score penalty: 2/10 tests are unstable (20%)
        assert metrics["health_score_penalty"] == 20.0

        # Verify most unstable tests
        assert len(metrics["most_unstable"]) == 2

    def test_empty_sessions(self):
        """Test that reliability metrics handle empty sessions correctly."""
        # Create insights with empty sessions
        insights = TestInsights([])

        # Get reliability metrics
        metrics = insights.test_reliability_metrics()

        # Verify metrics with empty sessions
        assert metrics["reliability_index"] == 100.0
        assert metrics["rerun_recovery_rate"] == 100.0
        assert metrics["total_unstable"] == 0
        assert metrics["health_score_penalty"] == 0.0
        assert len(metrics["most_unstable"]) == 0

    def test_no_rerun_groups(self):
        """Test that reliability metrics handle sessions with no rerun groups correctly."""
        # Create mock session with no rerun groups
        session = MagicMock()
        session.session_id = "session1"
        session.test_results = [MagicMock() for _ in range(10)]  # 10 tests total
        session.rerun_test_groups = []

        # Create insights with the mock session
        insights = TestInsights([session])

        # Get reliability metrics
        metrics = insights.test_reliability_metrics()

        # Verify metrics with no rerun groups
        assert metrics["reliability_index"] == 100.0
        assert metrics["rerun_recovery_rate"] == 100.0
        assert metrics["total_unstable"] == 0
        assert metrics["health_score_penalty"] == 0.0
        assert len(metrics["most_unstable"]) == 0

    def test_multiple_sessions(self):
        """Test that reliability metrics handle multiple sessions correctly."""
        # Create first mock session
        session1 = MagicMock()
        session1.session_id = "session1"
        session1.test_results = [MagicMock() for _ in range(5)]  # 5 tests

        rerun_group1 = RerunTestGroup(nodeid="test1")
        current_time = datetime.now()
        test1_attempt1 = TestResult(
            nodeid="test1",
            outcome=TestOutcome.FAILED,
            start_time=current_time,
            duration=1.0,
        )
        test1_attempt2 = TestResult(
            nodeid="test1",
            outcome=TestOutcome.PASSED,
            start_time=current_time + timedelta(seconds=5),
            duration=1.0,
        )
        rerun_group1.add_test(test1_attempt1)
        rerun_group1.add_test(test1_attempt2)

        session1.rerun_test_groups = [rerun_group1]

        # Create second mock session
        session2 = MagicMock()
        session2.session_id = "session2"
        session2.test_results = [MagicMock() for _ in range(5)]  # 5 tests

        rerun_group2 = RerunTestGroup(nodeid="test2")
        test2_attempt1 = TestResult(
            nodeid="test2",
            outcome=TestOutcome.FAILED,
            start_time=current_time + timedelta(seconds=10),
            duration=1.0,
        )
        test2_attempt2 = TestResult(
            nodeid="test2",
            outcome=TestOutcome.FAILED,
            start_time=current_time + timedelta(seconds=15),
            duration=1.0,
        )
        rerun_group2.add_test(test2_attempt1)
        rerun_group2.add_test(test2_attempt2)

        session2.rerun_test_groups = [rerun_group2]

        # Create insights with both sessions
        insights = TestInsights([session1, session2])

        # Get reliability metrics
        metrics = insights.test_reliability_metrics()

        # Verify reliability index: 8/10 tests are stable (80%)
        assert metrics["reliability_index"] == 80.0

        # Verify rerun recovery rate: 1/2 rerun groups passed (50%)
        assert metrics["rerun_recovery_rate"] == 50.0

        # Verify unstable tests count
        assert metrics["total_unstable"] == 2

        # Verify health score penalty: 2/10 tests are unstable (20%)
        assert metrics["health_score_penalty"] == 20.0

        # Verify most unstable tests
        assert len(metrics["most_unstable"]) == 2
