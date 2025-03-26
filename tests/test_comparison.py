from datetime import timedelta

import pytest
from pytest_insight.comparison import Comparison, ComparisonError, ComparisonResult
from pytest_insight.models import TestOutcome, TestResult, TestSession
from pytest_insight.query import Query


@pytest.fixture
def base_session(get_test_time):
    """Fixture providing a base test session."""
    base_time = get_test_time() - timedelta(days=7)
    return TestSession(
        sut_name="api-service",
        session_id="base-123",
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
                outcome=TestOutcome.FAILED,
                start_time=base_time + timedelta(seconds=1),
                duration=2.0,
            ),
        ],
        rerun_test_groups=[],
        session_tags={"python": "3.9", "os": "linux"},
    )


@pytest.fixture
def target_session(get_test_time):
    """Fixture providing a target test session with changes."""
    target_time = get_test_time()
    return TestSession(
        sut_name="api-service",
        session_id="target-123",
        session_start_time=target_time,
        session_stop_time=target_time + timedelta(seconds=10),
        session_duration=10.0,
        test_results=[
            TestResult(
                nodeid="test_api.py::test_get",
                outcome=TestOutcome.FAILED,  # Changed outcome
                start_time=target_time,
                duration=2.0,  # Slower
            ),
            TestResult(
                nodeid="test_api.py::test_post",
                outcome=TestOutcome.PASSED,  # Fixed
                start_time=target_time + timedelta(seconds=1),
                duration=1.0,  # Faster
            ),
        ],
        rerun_test_groups=[],
        session_tags={"python": "3.10", "os": "linux"},
    )


class Test_Comparison:
    """Test suite for Comparison class."""

    def test_basic_comparison(self, base_session, target_session):
        """Test basic comparison functionality."""
        comparison = Comparison().between_suts("api-service", "api-service").execute([base_session, target_session])

        assert isinstance(comparison, ComparisonResult)

        # Debugging output
        print("\n===== DEBUG: test_basic_comparison =====")
        print("Base session test results:")
        for test in base_session.test_results:
            print(f"  {test.nodeid} - {test.outcome}")

        print("\nTarget session test results:")
        for test in target_session.test_results:
            print(f"  {test.nodeid} - {test.outcome}")

        print("\nComparison result:")
        print(f"  New Failures: {comparison.new_failures}")
        print(f"  New Passes: {comparison.new_passes}")
        print(f"  Outcome Changes: {comparison.outcome_changes}")
        print("=======================================\n")

        # Assertions
        assert "test_api.py::test_get" in comparison.new_failures
        assert "test_api.py::test_post" in comparison.new_passes

    def test_environment_comparison(self, base_session, target_session):
        """Test comparing across environments."""
        comparison = (
            Comparison().with_environment({"python": "3.9"}, {"python": "3.10"}).execute([base_session, target_session])
        )

        assert isinstance(comparison, ComparisonResult)
        assert comparison.has_changes

    def test_date_window_comparison(self, base_session, target_session, get_test_time):
        """Test comparing within time window."""
        now = get_test_time()
        comparison = (
            Comparison()
            .apply_to_both(lambda q: q.date_range(now - timedelta(days=14), now - timedelta(days=7)))
            .execute([base_session, target_session])
        )

        assert len(comparison.base_session.test_results) > 0
        assert comparison.base_session.session_id == base_session.session_id

    def test_performance_changes(self, base_session, target_session):
        """Test performance change detection."""
        comparison = Comparison().execute([base_session, target_session])

        assert "test_api.py::test_get" in comparison.slower_tests
        assert "test_api.py::test_post" in comparison.faster_tests

    def test_flaky_detection(self, base_session, target_session):
        """Test flaky test detection."""
        comparison = Comparison().execute([base_session, target_session])

        # Both tests changed outcomes, should be marked as flaky
        assert "test_api.py::test_get" in comparison.flaky_tests
        assert "test_api.py::test_post" in comparison.flaky_tests

    def test_comparison_validation_no_sessions_no_filters(self):
        """Test input validation."""
        # Create a comparison with no sessions list
        comparison = Comparison()

        # Remove any default filters that might be applied
        comparison._base_query = Query()
        comparison._target_query = Query()

        # This should raise an error when execute() is called with no sessions and no filters
        with pytest.raises(ComparisonError):
            comparison.execute()

    def test_filtered_comparison(self, base_session, target_session):
        """Test comparison with pattern matching and filtering.

        Key aspects:
        1. Pattern Matching:
           - Simple substring matching for specified field
           - field_name parameter is required
           - Case-sensitive matching

        2. Two-Level Filtering:
           - Test-level filter that returns full TestSession objects
           - Sessions containing ANY matching test are included
           - ALL tests in matching sessions are preserved

        3. Context Preservation:
           - Session metadata (tags, IDs) is preserved
           - Test relationships are maintained
           - Never returns isolated TestResult objects
        """
        comparison = (
            Comparison()
            .apply_to_both(lambda q: q.filter_by_test()
                .with_nodeid_containing("get")  # Match tests with 'get' in nodeid
                .with_duration_between(0.5, float("inf"))  # Lower threshold to 0.5s
                .apply())
            .execute([base_session, target_session])
        )

        # Both tests should be included because:
        # 1. They're in the same session so would be preserved
        # 2. At least one test matches the pattern
        assert len(comparison.outcome_changes) == 2
        assert "test_api.py::test_get" in comparison.outcome_changes
        assert "test_api.py::test_post" in comparison.outcome_changes

    def test_combined_filters(self, base_session, target_session):
        """Test multiple filters working together in comparison.

        Demonstrates:
        1. Test-Level Filtering:
           - Pattern matching on test fields
           - Duration thresholds for test execution
           - Returns full TestSession objects

        2. Session Context:
           - Preserves session metadata
           - Maintains test relationships
           - Keeps all tests in matching sessions
        """
        comparison = (
            Comparison()
            .apply_to_both(lambda q: q.filter_by_test()
                .with_nodeid_containing("get")  # Match tests with 'get' in nodeid
                .with_duration_between(0.5, float("inf"))  # This should pass (both sessions have durations > 0.5)
                .apply())
            .execute([base_session, target_session])
        )

        # Verify the filters worked correctly
        assert len(comparison.base_session.test_results) > 0
        assert len(comparison.target_session.test_results) > 0

    def test_filter_stacking(self, base_session, target_session):
        """Test filter stacking in comparison.

        Demonstrates:
        1. Filter Combinations:
           - Session-level filters (environment)
           - Test-level filters (pattern matching)
           - Outcome filters (failures, flaky)

        2. Two-Level Design:
           - Session filters applied first
           - Test filters preserve session context
           - Never returns isolated test results
        """
        # Test multiple outcome filters (should restrict results)
        comparison1 = (
            Comparison()
            .apply_to_both(lambda q: q.filter_by_test()
                .with_outcome(TestOutcome.FAILED)  # First filter - failed outcomes
                .apply())
            .apply_to_both(lambda q: q.with_reruns(False))  # Second filter - no reruns
            .execute([base_session, target_session])
        )
        assert comparison1.base_session is not None

        # Test environment + pattern filtering using with_environment
        comparison2 = (
            Comparison()
            .with_environment({"python": "3.9"}, {"python": "3.10"})
            .apply_to_both(lambda q: q.filter_by_test()
                .with_nodeid_containing("api")  # Match tests with 'api' in nodeid
                .apply())
            .execute([base_session, target_session])
        )
        assert comparison2.base_session is not None
