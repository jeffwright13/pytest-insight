from datetime import datetime, timedelta
import pytest
from typing import List

from pytest_insight.models import TestSession, TestResult, RerunTestGroup
from pytest_insight.query.query import Query, InvalidQueryParameterError, QueryExecutionError
from pytest_insight.storage import get_storage_instance

@pytest.fixture
def mock_session_now() -> TestSession:
    """Fixture providing a test session."""
    return TestSession(
        sut_name="test_sut",
        session_id="test-123",
        session_start_time=datetime.now(),
        session_stop_time=datetime.now(),
        test_results=[
            TestResult(
                nodeid="test_api.py::test_endpoint",
                outcome="PASSED",
                start_time=datetime.now(),
                duration=1.0
            )
        ],
        rerun_test_groups=[]
    )

@pytest.fixture
def mock_session_1_day_1_hour_ago() -> TestSession:
    """Fixture providing a test session from 1d1m ago."""
    return TestSession(
        sut_name="test_sut",
        session_id="test-123",
        session_start_time=datetime.now() - timedelta(days=1, hours=1),
        session_stop_time=datetime.now() - timedelta(days=1, hours=1),
        test_results=[
            TestResult(
                nodeid="test_api.py::test_endpoint",
                outcome="PASSED",
                start_time=datetime.now() - timedelta(days=1, hours=1),
                duration=1.0
            )
        ],
        rerun_test_groups=[]
    )

@pytest.fixture
def mock_session_1_hour_1_minute_ago() -> TestSession:
    """Fixture providing a test session from 1h1m ago."""
    return TestSession(
        sut_name="test_sut",
        session_id="test-123",
        session_start_time=datetime.now() - timedelta(hours=1, minutes=1),
        session_stop_time=datetime.now() - timedelta(hours=1, minutes=1),
        test_results=[
            TestResult(
                nodeid="test_api.py::test_endpoint",
                outcome="PASSED",
                start_time=datetime.now() - timedelta(days=1, minutes=1),
                duration=1.0
            )
        ],
        rerun_test_groups=[]
    )

@pytest.fixture
def mock_session_1_minute_1_second_ago() -> TestSession:
    """Fixture providing a test session from 1m1s ago."""
    return TestSession(
        sut_name="test_sut",
        session_id="test-123",
        session_start_time=datetime.now() - timedelta(minutes=1, seconds=1),
        session_stop_time=datetime.now() - timedelta(minutes=1, seconds=1),
        test_results=[
            TestResult(
                nodeid="test_api.py::test_endpoint",
                outcome="PASSED",
                start_time=datetime.now() - timedelta(minutes=1, seconds=1),
                duration=1.0
            )
        ],
        rerun_test_groups=[]
    )

@pytest.fixture
def mock_sessions(mock_session_now, mock_session_1_day_1_hour_ago, mock_session_1_hour_1_minute_ago, mock_session_1_minute_1_second_ago) -> List[TestSession]:
    """Fixture providing a list of test sessions."""
    return [mock_session_now, mock_session_1_day_1_hour_ago, mock_session_1_hour_1_minute_ago, mock_session_1_minute_1_second_ago]

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
def mock_session_with_reruns() -> TestSession:
    """Fixture providing a test session with reruns."""
    return TestSession(
        sut_name="test_sut",
        session_id="test-123",
        session_start_time=datetime.now(),
        session_stop_time=datetime.now(),
        test_results=[
            TestResult(
                nodeid="test_api.py::test_endpoint",
                outcome="PASSED",
                start_time=datetime.now(),
                duration=1.0
            )
        ],
        rerun_test_groups=[
            RerunTestGroup(
                nodeid="test_api.py::test_endpoint",
                tests=[
                    TestResult(
                        nodeid="test_api.py::test_endpoint",
                        outcome="FAILED",
                        start_time=datetime.now(),
                        duration=0.6
                    ),
                    TestResult(
                        nodeid="test_api.py::test_endpoint",
                        outcome="RERUN",
                        start_time=datetime.now() - timedelta(seconds=0.5),
                        duration=0.3
                    )
                ]
            )
        ]
    )

class Test_Query:
    """Test suite for Query functionality."""

    def test_query_initialization(self):
        """Test basic Query initialization."""
        query = Query()
        assert hasattr(query, '_filters')
        assert len(query._filters) == 0

    def test_for_sut_filter(self, mock_sessions):
        """Test SUT name filtering."""
        query = Query().for_sut("test_sut")
        result = query.execute(mock_sessions)
        assert not result.empty
        assert result.total_count == 4
        assert all(s.sut_name == "test_sut" for s in result.sessions)

    def test_for_sut_validation(self):
        """Test SUT name validation."""
        with pytest.raises(InvalidQueryParameterError):
            Query().for_sut("")
        with pytest.raises(InvalidQueryParameterError):
            Query().for_sut(None)

    def test_in_last_days(self, mock_sessions):
        """Test date range filtering."""
        query = Query().in_last_days(1)
        result = query.execute(mock_sessions)
        assert not result.empty
        assert result.total_count == 3

        # Test old session gets filtered out
        old_session = TestSession(
            sut_name="test_sut",
            session_id="old-123",
            session_start_time=datetime.now() - timedelta(days=2),
            session_stop_time=datetime.now() - timedelta(days=2),
            test_results=[],
            rerun_test_groups=[]
        )
        result = query.execute([old_session])
        assert result.empty

    def test_in_last_hours(self, mock_sessions):
        """Test hours range filtering."""
        query = Query().in_last_hours(1)
        result = query.execute(mock_sessions)
        assert not result.empty
        assert result.total_count == 2

        # Test old session gets filtered out
        old_session = TestSession(
            sut_name="test_sut",
            session_id="old-123",
            session_start_time=datetime.now() - timedelta(hours=2),
            session_stop_time=datetime.now() - timedelta(hours=2),
            test_results=[],
            rerun_test_groups=[]
        )
        result = query.execute([old_session])
        assert result.empty

    def test_in_last_minutes(self, mock_sessions):
        """Test minutes range filtering."""
        query = Query().in_last_minutes(1)
        result = query.execute(mock_sessions)

        assert not result.empty
        assert result.total_count == 1

        # Test old session gets filtered out
        old_session = TestSession(
            sut_name="test_sut",
            session_id="old-123",
            session_start_time=datetime.now() - timedelta(minutes=30),
            session_stop_time=datetime.now() - timedelta(minutes=30),
            test_results=[],
            rerun_test_groups=[]
        )
        result = query.execute([old_session])
        assert result.empty

    def test_with_outcome(self, mock_sessions):
        """Test outcome filtering."""
        query = Query().with_outcome("PASSED")
        result = query.execute(mock_sessions)

        assert not result.empty
        assert all(any(t.outcome == "PASSED" for t in s.test_results)
                  for s in result.sessions)

    def test_having_warnings(self, mock_session_now):
        """Test warning presence filtering."""
        warning_result = TestResult(
            nodeid="test_warn.py::test_warning",
            outcome="PASSED",
            start_time=datetime.now(),
            duration=1.0,
            has_warning=True
        )
        mock_session_now.test_results.append(warning_result)
        query = Query().having_warnings(True)
        result = query.execute([mock_session_now])
        assert not result.empty
        assert any(t.has_warning for s in result.sessions
                  for t in s.test_results)

    def test_query_result_properties(self, base_session, target_session):
        """Test QueryResult properties."""
        result = Query().execute([base_session, target_session])

        assert not result.empty
        assert result.total_count == 2
        assert len(result.matched_nodeids) == 2
        assert isinstance(result.execution_time, float)

    def test_execution_error_handling(self):
        """Test error handling during query execution."""
        with pytest.raises(QueryExecutionError):
            Query().execute("not a list")
        with pytest.raises(QueryExecutionError):
            Query().execute([{"not": "a session"}])

    def test_query_validation(self):
        """Test query parameter validation."""
        with pytest.raises(InvalidQueryParameterError):
            Query().for_sut("")
        with pytest.raises(InvalidQueryParameterError):
            Query().in_last_days(-1)

    def test_query_result_properties(self, base_session, target_session):
        """Test QueryResult properties and methods."""
        result = Query().execute([base_session, target_session])
        assert not result.empty
        assert result.total_count == 2
        assert len(result.matched_nodeids) == 2
        assert isinstance(result.execution_time, float)

    def test_query_chaining_no_matches(self, mock_sessions):
        """Test query method chaining and execution with no matching sessions."""
        query = (
            Query()
            .for_sut("api-service")
            .in_last_days(7)
            .with_outcome("PASSED")
        )
        result = query.execute(mock_sessions)
        assert result.empty
        assert result.total_count == 0
        assert result.matched_nodeids == set()

    def test_query_chaining_with_matches(self, base_session, target_session):
        """Test query method chaining and execution with matching sessions."""
        query = (
            Query()
            .for_sut("api-service")
            .in_last_days(7)
            .with_outcome("PASSED")
        )
        result = query.execute([base_session, target_session])

        assert not result.empty
        assert result.total_count == 1
        assert any(
            any(t.outcome == "PASSED" for t in s.test_results)
            for s in result.sessions
        )

    def test_query_with_reruns(self, mock_session_with_reruns):
        """Test filtering sessions with reruns."""
        query = Query().with_reruns(True)
        result = query.execute([mock_session_with_reruns])
        assert not result.empty
        assert result.total_count == 1
