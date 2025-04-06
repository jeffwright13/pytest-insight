from datetime import timedelta

import pytest
from pytest_insight.core.analysis import Analysis
from pytest_insight.core.models import TestOutcome, TestResult, TestSession
from pytest_insight.core.query import Query


@pytest.fixture
def analysis_sessions(get_test_time):
    """Fixture providing test sessions for analysis."""
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
        profile_name = "test_integration_profile"
        json_storage.profile_name = profile_name  # Add profile_name to storage for reference
        query = Query(profile_name=profile_name)

        # Mock the execute method to return our test sessions
        original_execute = query.execute
        query.execute = lambda sessions=None: original_execute(sessions=analysis_sessions)

        # Use query results with Analysis
        query_result = query.for_sut("api-service").execute()
        analysis = Analysis(sessions=query_result.sessions, profile_name=profile_name)

        # Verify sessions were filtered correctly
        assert len(analysis._sessions) == 2  # Only api-service sessions

        # Test chaining query with analysis
        health_report = (
            Analysis(profile_name=profile_name)
            .with_query(lambda q: q.for_sut("api-service").with_outcome(TestOutcome.FAILED))
            .health_report()
        )

        # Verify health report contains expected metrics
        assert "health_score" in health_report
        assert "session_metrics" in health_report

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

    def test_analysis_with_profiles(self, analysis_sessions, mocker):
        """Test analysis initialization with profiles."""
        # Mock the storage to control its behavior
        mock_storage = mocker.MagicMock()

        # Mock the get_storage_instance function to return our mock storage directly
        mock_get_storage = mocker.patch("pytest_insight.core.analysis.get_storage_instance")
        mock_get_storage.return_value = mock_storage

        # Initialize analysis with profile
        analysis = Analysis(profile_name="test_profile")

        # Verify get_storage_instance was called with correct profile
        mock_get_storage.assert_called_once_with(profile_name="test_profile")

        # Verify storage was correctly set
        assert analysis.storage == mock_storage
        assert analysis._profile_name == "test_profile"

    def test_with_profile_method(self, analysis_sessions, mocker):
        """Test the with_profile method."""
        # Mock the storage to control its behavior
        mock_storage = mocker.MagicMock()

        # Mock the get_storage_instance function to return our mock storage directly
        mock_get_storage = mocker.patch("pytest_insight.core.analysis.get_storage_instance")
        mock_get_storage.return_value = mock_storage

        # Create analysis and call with_profile
        analysis = Analysis()
        result = analysis.with_profile("test_profile")

        # Verify get_storage_instance was called with correct profiles
        assert mock_get_storage.call_count == 2
        mock_get_storage.assert_any_call(profile_name=None)
        mock_get_storage.assert_any_call(profile_name="test_profile")

        # Verify storage was correctly set after with_profile
        assert analysis.storage == mock_storage
        assert analysis._profile_name == "test_profile"

        # Verify method returns self for chaining
        assert result is analysis

    def test_with_query_with_profile(self, analysis_sessions, mocker):
        """Test combining with_query and with_profile methods."""
        # Mock the storage to control its behavior
        mock_storage = mocker.MagicMock()
        mock_storage.profile_name = "test_profile"  # Add profile_name to mock storage

        # Mock the get_storage_instance function to return our mock storage directly
        mock_get_storage = mocker.patch("pytest_insight.core.analysis.get_storage_instance")
        mock_get_storage.return_value = mock_storage

        # Mock the Query class to verify profile parameters are passed
        mock_query = mocker.patch("pytest_insight.core.analysis.Query")
        mock_query_instance = mocker.MagicMock()
        mock_query.return_value = mock_query_instance

        # Mock execute to return sessions
        mock_query_result = mocker.MagicMock()
        mock_query_result.sessions = analysis_sessions
        mock_query_instance.execute.return_value = mock_query_result

        # Create analysis with profile and call with_query
        analysis = Analysis(profile_name="test_profile")
        analysis.with_query(lambda q: q.for_sut("api-service"))

        # Verify Query was called with correct profile at least once
        mock_query.assert_any_call(profile_name="test_profile")

    def test_convenience_functions(self, mocker):
        """Test module-level convenience functions."""
        # Mock the Analysis class
        mock_analysis = mocker.patch("pytest_insight.core.analysis.Analysis")

        # Import the convenience functions
        from pytest_insight.core.analysis import analysis, analysis_with_profile

        # Test analysis function
        analysis(profile_name="test_profile")
        mock_analysis.assert_called_with(profile_name="test_profile", sessions=None, show_progress=True)

        # Test analysis_with_profile function
        analysis_with_profile("test_profile")
        mock_analysis.assert_called_with(profile_name="test_profile", show_progress=True)
