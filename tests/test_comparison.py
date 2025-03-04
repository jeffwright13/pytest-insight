from datetime import datetime, timedelta
import pytest

from pytest_insight.models import TestSession, TestResult
from pytest_insight.query.query import Query, QueryResult
from pytest_insight.query.comparison import SessionComparator, ComparisonResult, ComparisonError

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
                outcome="PASSED",
                start_time=datetime.now() - timedelta(days=7),
                duration=1.0
            ),
            TestResult(
                nodeid="test_api.py::test_post",
                outcome="FAILED",
                start_time=datetime.now() - timedelta(days=7),
                duration=2.0
            )
        ],
        rerun_test_groups=[]
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
                outcome="FAILED",  # Changed outcome
                start_time=datetime.now(),
                duration=2.0  # Slower
            ),
            TestResult(
                nodeid="test_api.py::test_post",
                outcome="PASSED",  # Fixed
                start_time=datetime.now(),
                duration=1.0  # Faster
            )
        ],
        rerun_test_groups=[]
    )

@pytest.fixture
def empty_query():
    """Fixture for empty query."""
    return Query(
        sessions=[],
        total_count=0,
        execution_time=0.0,
        matched_nodeids=set()
    )

@pytest.fixture
def base_query(base_session):
    """Fixture providing base query."""
    return Query().for_sut("api-service")

@pytest.fixture
def target_query(target_session):
    """Fixture providing target query."""
    return Query().for_sut("api-service")

class TestSessionComparator:
    """Test suite for session comparison functionality."""

    def test_basic_comparison(self, base_query, target_query, base_session, target_session):
        """Test basic comparison functionality."""
        comparator = SessionComparator(base_query, target_query)
        result = comparator.compare([base_session, target_session])

        assert isinstance(result, ComparisonResult)
        assert "test_api.py::test_get" in result.new_failures
        assert "test_api.py::test_post" in result.new_passes

    def test_performance_changes(self, base_query, target_query, base_session, target_session):
        """Test performance change detection."""
        comparator = SessionComparator(base_query, target_query)
        result = comparator.compare([base_session, target_session])

        assert "test_api.py::test_get" in result.slower_tests
        assert result.slower_tests["test_api.py::test_get"] == 100.0  # 1.0 -> 2.0
        assert "test_api.py::test_post" in result.faster_tests
        assert result.faster_tests["test_api.py::test_post"] == -50.0  # 2.0 -> 1.0

    def test_empty_comparison(self):
        """Test comparison with empty queries."""
        empty_query = Query()
        comparator = SessionComparator(empty_query, empty_query)
        result = comparator.compare([])

        assert result.base_results.empty
        assert result.target_results.empty
        assert result.duration_change == 0.0
        assert not result.new_failures
        assert not result.new_passes

    def test_comparison_error_handling(self, base_query):
        """Test comparison error handling."""
        with pytest.raises(ComparisonError):
            SessionComparator(None, base_query)
        with pytest.raises(ComparisonError):
            SessionComparator(base_query, None)

        comparator = SessionComparator(base_query, base_query)
        with pytest.raises(ComparisonError):
            comparator.compare(None)
