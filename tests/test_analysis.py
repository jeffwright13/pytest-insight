from datetime import timedelta

import pytest
from pytest_insight.analysis import Analysis
from pytest_insight.models import TestOutcome, TestResult, TestSession
from pytest_insight.query import Query


@pytest.fixture
def analysis_sessions(get_test_time):
    """Fixture providing test sessions for analysis testing."""
    base_time = get_test_time() - timedelta(days=30)

    # Create sessions with different characteristics for analysis
    sessions = [
        # Session 1: Mostly passing tests
        TestSession(
            sut_name="api-service",
            session_id="analysis-1",
            session_start_time=base_time,
            session_stop_time=base_time + timedelta(seconds=10),
            session_duration=10.0,
            test_results=[
                TestResult(
                    nodeid="test_api.py::test_get",
                    outcome=TestOutcome.PASSED,
                    start_time=base_time,
                    duration=1.0,
                ),
                TestResult(
                    nodeid="test_api.py::test_post",
                    outcome=TestOutcome.PASSED,
                    start_time=base_time + timedelta(seconds=1),
                    duration=2.0,
                ),
                TestResult(
                    nodeid="test_api.py::test_delete",
                    outcome=TestOutcome.FAILED,
                    start_time=base_time + timedelta(seconds=3),
                    duration=1.5,
                ),
            ],
            rerun_test_groups=[],
            session_tags={"python": "3.9", "os": "linux"},
        ),
        # Session 2: Some failing tests
        TestSession(
            sut_name="api-service",
            session_id="analysis-2",
            session_start_time=base_time + timedelta(days=7),
            session_stop_time=base_time + timedelta(days=7, seconds=12),
            session_duration=12.0,
            test_results=[
                TestResult(
                    nodeid="test_api.py::test_get",
                    outcome=TestOutcome.PASSED,
                    start_time=base_time + timedelta(days=7),
                    duration=1.2,  # Slightly slower
                ),
                TestResult(
                    nodeid="test_api.py::test_post",
                    outcome=TestOutcome.FAILED,  # Now failing
                    start_time=base_time + timedelta(days=7, seconds=1),
                    duration=2.5,  # Slower
                ),
                TestResult(
                    nodeid="test_api.py::test_delete",
                    outcome=TestOutcome.FAILED,  # Still failing
                    start_time=base_time + timedelta(days=7, seconds=3),
                    duration=1.5,
                ),
            ],
            rerun_test_groups=[],
            session_tags={"python": "3.9", "os": "linux"},
        ),
        # Session 3: Different SUT
        TestSession(
            sut_name="db-service",
            session_id="analysis-3",
            session_start_time=base_time + timedelta(days=14),
            session_stop_time=base_time + timedelta(days=14, seconds=8),
            session_duration=8.0,
            test_results=[
                TestResult(
                    nodeid="test_db.py::test_connect",
                    outcome=TestOutcome.PASSED,
                    start_time=base_time + timedelta(days=14),
                    duration=0.5,
                ),
                TestResult(
                    nodeid="test_db.py::test_query",
                    outcome=TestOutcome.PASSED,
                    start_time=base_time + timedelta(days=14, seconds=1),
                    duration=1.0,
                ),
            ],
            rerun_test_groups=[],
            session_tags={"python": "3.10", "os": "linux"},
        ),
    ]
    return sessions


class Test_Analysis:
    """Test suite for Analysis class."""

    def test_basic_analysis(self, analysis_sessions, json_storage):
        """Test basic analysis functionality."""
        # Initialize Analysis with sessions
        analysis = Analysis(storage=json_storage, sessions=analysis_sessions)

        # Test health report generation
        health_report = analysis.health_report()
        assert "health_score" in health_report
        assert "session_metrics" in health_report
        assert "trends" in health_report

        # Test stability report
        stability_report = analysis.stability_report()
        assert "stability" in stability_report
        assert "failure_rate" in stability_report

        # Test performance report
        performance_report = analysis.performance_report()
        assert "performance" in performance_report
        assert "session_metrics" in performance_report

    def test_with_query_filtering(self, analysis_sessions, json_storage):
        """Test filtering with the with_query method.

        Demonstrates:
        1. Query Integration:
           - Using Query's filtering capabilities with Analysis
           - Preserving session context in filtered results
           - Maintaining the fluent interface pattern

        2. Two-Level Design:
           - Session-level filtering (SUT, tags)
           - Test-level filtering (outcome, duration)
           - Preserving full session context
        """
        # Initialize Analysis with sessions
        analysis = Analysis(storage=json_storage, sessions=analysis_sessions)

        # Filter by SUT
        filtered_analysis = analysis.with_query(lambda q: q.for_sut("api-service"))

        # Verify filtering worked
        assert len(filtered_analysis._sessions) == 2  # Only the api-service sessions

        # Test more complex query with test-level filtering
        complex_filtered = analysis.with_query(lambda q: q.filter_by_test().with_outcome(TestOutcome.FAILED).apply())

        # Verify test-level filtering worked while preserving session context
        assert len(complex_filtered._sessions) == 2  # Sessions with failed tests

        # Generate report from filtered sessions
        report = complex_filtered.stability_report()
        assert "stability" in report
        assert "failure_rate" in report

    def test_compare_health(self, analysis_sessions, json_storage):
        """Test health comparison between session sets.

        Demonstrates:
        1. Comparative Analysis:
           - Comparing metrics between session sets
           - Identifying trends and changes
           - Calculating improvement scores

        2. Context Preservation:
           - Maintaining full session context in comparisons
           - Preserving test relationships
        """
        # Initialize Analysis with sessions
        analysis = Analysis(storage=json_storage, sessions=analysis_sessions)

        # Split sessions manually for testing
        api_sessions = analysis.with_query(lambda q: q.for_sut("api-service"))._sessions
        db_sessions = analysis.with_query(lambda q: q.for_sut("db-service"))._sessions

        # Compare health between different SUTs
        comparison = analysis.compare_health(base_sessions=api_sessions, target_sessions=db_sessions)

        # Verify comparison structure
        assert "base_health" in comparison
        assert "target_health" in comparison
        assert "health_difference" in comparison
        assert isinstance(comparison["improved"], bool)

        # Test automatic splitting when no sessions provided
        auto_comparison = analysis.compare_health()
        assert "base_health" in auto_comparison
        assert "target_health" in auto_comparison

    def test_integration_with_query(self, analysis_sessions, json_storage):
        """Test integration with Query class.

        Demonstrates:
        1. Component Integration:
           - Seamless integration between Query and Analysis
           - Maintaining consistent session context
           - Preserving the fluent interface pattern

        2. Filtering Capabilities:
           - Using Query's full filtering capabilities
           - Applying multiple filters in sequence
           - Preserving session context in filtered results
        """
        # Create a query and use its results with Analysis
        query = Query(storage=json_storage)
        query_result = query.for_sut("api-service").execute(sessions=analysis_sessions)

        # Use query results with Analysis
        analysis = Analysis(sessions=query_result.sessions)
        report = analysis.health_report()

        # Verify integration worked
        assert "health_score" in report
        assert "session_metrics" in report

        # Test chaining with multiple filters
        filtered_analysis = Analysis(sessions=analysis_sessions).with_query(
            lambda q: q.for_sut("api-service").filter_by_test().with_nodeid_containing("test_get").apply()
        )

        # Verify chained filtering worked
        assert len(filtered_analysis._sessions) > 0
        performance_report = filtered_analysis.performance_report()
        assert "performance" in performance_report

    def test_error_handling(self, json_storage):
        """Test error handling in Analysis class.

        Demonstrates proper error handling for:
        1. Empty session lists
        2. Invalid comparison attempts
        3. Missing data scenarios
        """
        # Initialize Analysis with no sessions
        analysis = Analysis(storage=json_storage, sessions=[])

        # Test compare_health with no sessions
        with pytest.raises(ValueError, match="No sessions available for comparison"):
            analysis.compare_health()

        # Health report should still work with empty sessions
        health_report = analysis.health_report()
        assert "health_score" in health_report
        assert "session_metrics" in health_report
