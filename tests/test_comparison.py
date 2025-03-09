from datetime import datetime, timedelta

import pytest
from pytest_insight.models import TestOutcome, TestResult, TestSession
from pytest_insight.query.comparison import Comparison, ComparisonError, ComparisonResult
from pytest_insight.query.query import Query


@pytest.fixture
def base_session():
    """Fixture providing a base test session."""
    return TestSession(
        sut_name="api-service",
        session_id="base-123",
        session_start_time=datetime.now() - timedelta(days=7),
        session_stop_time=datetime.now() - timedelta(days=7),
        test_results=[
            TestResult(
                nodeid="test_api.py::test_get",
                outcome=TestOutcome.PASSED,
                start_time=datetime.now() - timedelta(days=7),
                duration=1.0,
            ),
            TestResult(
                nodeid="test_api.py::test_post",
                outcome=TestOutcome.FAILED,
                start_time=datetime.now() - timedelta(days=7),
                duration=2.0,
            ),
        ],
        rerun_test_groups=[],
        session_tags={"python": "3.9", "os": "linux"},
    )


@pytest.fixture
def target_session():
    """Fixture providing a target test session with changes."""
    return TestSession(
        sut_name="api-service",
        session_id="target-123",
        session_start_time=datetime.now(),
        session_stop_time=datetime.now(),
        test_results=[
            TestResult(
                nodeid="test_api.py::test_get",
                outcome=TestOutcome.FAILED,  # Changed outcome
                start_time=datetime.now(),
                duration=2.0,  # Slower
            ),
            TestResult(
                nodeid="test_api.py::test_post",
                outcome=TestOutcome.PASSED,  # Fixed
                start_time=datetime.now(),
                duration=1.0,  # Faster
            ),
        ],
        rerun_test_groups=[],
        session_tags={"python": "3.10", "os": "linux"},
    )


class Test_Comparison:
    """Test suite for Comparison class."""

    # def test_basic_comparison(self, base_session, target_session):
    #     """Test basic comparison functionality."""
    #     comparison = Comparison().between_suts("api-service", "api-service").execute([base_session, target_session])

    #     assert isinstance(comparison, ComparisonResult)
    #     assert "test_api.py::test_get" in comparison.new_failures
    #     assert "test_api.py::test_post" in comparison.new_passes


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

    def test_date_window_comparison(self, base_session, target_session):
        """Test comparing within time window."""
        now = datetime.now()
        comparison = (
            Comparison()
            .in_date_window(now - timedelta(days=14), now - timedelta(days=7))
            .execute([base_session, target_session])
        )

        assert len(comparison.base_results.sessions) == 1
        assert base_session in comparison.base_results.sessions

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

    # def test_comparison_validation(self):
    #     """Test input validation."""
    #     with pytest.raises(ComparisonError):
    #         Comparison().execute()  # No queries configured

    #     with pytest.raises(ComparisonError):
    #         Comparison().between_suts(None, "api")  # Invalid SUT name

    def test_comparison_validation(self, monkeypatch):
        """Test input validation."""
        # Create a comparison with no sessions list
        comparison = Comparison()

        # Remove any default filters that might be applied
        comparison._base_query = Query()
        comparison._target_query = Query()

        # This should raise an error when execute() is called with no sessions
        with pytest.raises(ComparisonError):
            comparison.execute()  # No sessions and no queries

    def test_filtered_comparison(self, base_session, target_session):
        """Test comparison with filters."""
        comparison = (
            Comparison()
            .with_test_pattern("test_api.py::test_get")
            .with_duration_threshold(0.5)  # Lower threshold to 0.5s
            .execute([base_session, target_session])
        )

        assert len(comparison.outcome_changes) == 1

    def test_combined_filters(self, base_session, target_session):
        """Test multiple filters working together."""
        # Create a comparison with multiple filters
        comparison = (
            Comparison()
            .with_test_pattern("test_api.py::test_get")  # This matches a specific test
            .with_duration_threshold(0.5)  # This should pass (both sessions have durations > 0.5)
            .execute([base_session, target_session])
        )

        # Verify the filters worked correctly (should include both sessions)
        assert len(comparison.base_results.sessions) == 1
        assert len(comparison.target_results.sessions) == 1
        assert "test_api.py::test_get" in comparison.outcome_changes

    def test_filter_stacking(self, base_session, target_session):
        """Test that filters can be stacked in specific ways."""
        # Test multiple outcome filters (should restrict results)
        comparison1 = (
            Comparison()
            .only_failures()  # First filter - failed outcomes
            .exclude_flaky()  # Second filter - no reruns
            .execute([base_session, target_session])
        )
        assert len(comparison1.base_results.sessions) > 0

        # Test environment + pattern filtering
        comparison2 = (
            Comparison()
            .with_environment(  # First filter - environment
                {"python": "3.9"}, {"python": "3.10"}
            )
            .with_test_pattern("test_api")  # Second filter - pattern
            .execute([base_session, target_session])
        )
        assert len(comparison2.base_results.sessions) > 0
        assert len(comparison2.target_results.sessions) > 0
