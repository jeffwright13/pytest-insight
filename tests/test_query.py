from datetime import datetime, timedelta
import pytest
from typing import List

from pytest_insight.models import TestOutcome, TestSession, TestResult, RerunTestGroup
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

class Test_Query_TimeOperations:
    """Test suite for Query time-based operations."""

    @pytest.fixture
    def now(self) -> datetime:
        """Fixed current time for tests."""
        return datetime(2025, 3, 4, 12, 0, 0)  # Noon on March 4, 2025

    @pytest.fixture
    def sessions_at_boundaries(self, now):
        """Sessions at various time boundaries."""
        return [
            TestSession(  # Exactly 7 days ago
                sut_name="api-service",
                session_id="7d-exact",
                session_start_time=now - timedelta(days=7),
                session_duration=1.0,
                test_results=[]
            ),
            TestSession(  # Just inside 7 days
                sut_name="api-service",
                session_id="7d-minus-1min",
                session_start_time=now - timedelta(days=7, minutes=-1),
                session_duration=1.0,
                test_results=[]
            ),
            TestSession(  # Just outside 7 days
                sut_name="api-service",
                session_id="7d-plus-1min",
                session_start_time=now - timedelta(days=7, minutes=1),
                session_duration=1.0,
                test_results=[]
            )
        ]

    def test_in_last_days_boundary(self, now, sessions_at_boundaries, mocker):
        """Test exact boundary conditions for in_last_days."""
        mocker.patch('pytest_insight.query.query.datetime')
        mocker.patch('pytest_insight.query.query.datetime.now', return_value=now)

        query = Query().in_last_days(7)
        result = query.execute(sessions_at_boundaries)

        assert len(result.sessions) == 2
        assert "7d-exact" in {s.session_id for s in result.sessions}
        assert "7d-minus-1min" in {s.session_id for s in result.sessions}

    def test_date_range_edge_cases(self, now):
        """Test edge cases for date_range."""
        # Empty range (start == end)
        query = Query().date_range(now, now)

        # Start after end
        with pytest.raises(InvalidQueryParameterError):
            Query().date_range(now, now - timedelta(days=1))

        # Zero-duration range
        result = query.execute([
            TestSession(
                sut_name="api-service",
                session_id="exact-time",
                session_start_time=now,
                session_duration=0.0,
                test_results=[]
            )
        ])
        assert len(result.sessions) == 1

    def test_timezone_handling(self):
        """Test handling of timezone-aware datetimes."""
        from datetime import timezone
        utc_now = datetime.now(timezone.utc)
        est_now = datetime.now(timezone(timedelta(hours=-5)))

        # Test with timezone-aware and naive datetimes
        with pytest.raises(InvalidQueryParameterError):
            Query().date_range(utc_now, est_now)

    def test_combined_time_filters(self, now, mocker):
        """Test multiple time-based filters together."""
        mocker.patch('pytest_insight.query.query.datetime.now', return_value=now)

        query = (
            Query()
            .in_last_days(7)
            .in_last_hours(24)
        )
        # Should use most restrictive filter (24 hours)
        assert len(query._filters) == 2

    def test_time_filter_validation(self):
        """Test validation of time filter parameters."""
        with pytest.raises(InvalidQueryParameterError):
            Query().in_last_days(-1)

        with pytest.raises(InvalidQueryParameterError):
            Query().in_last_hours(-1)

        with pytest.raises(InvalidQueryParameterError):
            Query().in_last_minutes(-1)

        with pytest.raises(InvalidQueryParameterError):
            Query().date_range("not-a-date", datetime.now())






class Test_QueryQodoGen:
    def test_for_sut_filters_sessions(self, mocker):
        query = Query()
        sessions = [
            TestSession(sut_name="sut1", session_id="1", session_start_time=datetime.now(), session_duration=10),
            TestSession(sut_name="sut2", session_id="2", session_start_time=datetime.now(), session_duration=10)
        ]
        storage_mock = mocker.patch('pytest_insight.query.query.get_storage_instance')
        storage_mock.return_value.load_sessions.return_value = sessions
        result = query.for_sut("sut1").execute()
        assert len(result.sessions) == 1
        assert result.sessions[0].sut_name == "sut1"

    def test_for_sut_invalid_name(self):
        query = Query()
        with pytest.raises(InvalidQueryParameterError, match="SUT name must be a non-empty string"):
            query.for_sut("")
        with pytest.raises(InvalidQueryParameterError, match="SUT name must be a non-empty string"):
            query.for_sut("   ")

    def test_date_range_filter(self):
        now = datetime.now()
        session1 = TestSession(sut_name="SUT1", session_id="1", session_start_time=now - timedelta(days=5), session_duration=10)
        session2 = TestSession(sut_name="SUT2", session_id="2", session_start_time=now - timedelta(days=3), session_duration=10)
        session3 = TestSession(sut_name="SUT3", session_id="3", session_start_time=now - timedelta(days=1), session_duration = 10)
        sessions = [session1, session2, session3]
        query = Query().date_range(now - timedelta(days=4), now)
        result = query.execute(sessions)
        assert len(result.sessions) == 2
        assert session2 in result.sessions
        assert session3 in result.sessions

    def test_outcome_filter(self):
        """Test filtering by test outcome."""
        # Create test data with enum outcomes
        result_passed = TestResult(
            nodeid="test_1",
            outcome=TestOutcome.PASSED,
            start_time=datetime.now(),
            duration=1.0
        )
        result_failed = TestResult(
            nodeid="test_2",
            outcome=TestOutcome.FAILED,
            start_time=datetime.now(),
            duration=1.0
        )

        # Create test sessions
        session1 = TestSession(
            sut_name="SUT1",
            session_id="1",
            session_start_time=datetime.now(),
            session_duration=1.5,
            test_results=[result_passed]
        )
        session2 = TestSession(
            sut_name="SUT2",
            session_id="2",
            session_start_time=datetime.now(),
            session_duration=1.5,
            test_results=[result_failed]
        )

        # Test with both string and enum
        sessions = [session1, session2]
        query_str = Query().with_outcome("FAILED")
        query_enum = Query().with_outcome(TestOutcome.FAILED)

        result_str = query_str.execute(sessions)
        result_enum = query_enum.execute(sessions)

        assert len(result_str.sessions) == 1
        assert len(result_enum.sessions) == 1
        assert session2 in result_str.sessions
        assert session2 in result_enum.sessions

    def test_query_executes_with_provided_sessions(self):
        session = TestSession(
            sut_name="SUT1", session_id="1", session_start_time=datetime.now() - timedelta(days=1),
            session_stop_time=datetime.now(), session_duration=86400, test_results=[]
        )
        query = Query()
        result = query.execute([session])
        assert result.total_count == 1
        assert result.sessions[0].sut_name == "SUT1"

    def test_query_executes_with_storage_sessions(self, mocker):
        """Test query execution with all sessions loaded from storage (default behavior)."""
        # mock_storage = mocker.patch('pytest_insight.storage.get_storage_instance')
        # A classic example of the need to patch it where it's being used, not where it's defined!
        # "PLAY IT WHERE IT LIES!"
        mock_storage = mocker.patch('pytest_insight.query.query.get_storage_instance')
        mock_storage_instance = mock_storage.return_value
        mock_storage_instance.load_sessions.return_value = []

        query = Query()
        result = query.execute()
        assert result.total_count == 0
        mock_storage_instance.load_sessions.assert_called_once()

    def test_negative_values_for_time_filters(self):
        query = Query()
        with pytest.raises(InvalidQueryParameterError, match="Days must be a non-negative integer"):
            query.in_last_days(-1)
        with pytest.raises(InvalidQueryParameterError, match="Hours must be a non-negative integer"):
            query.in_last_hours(-1)
        with pytest.raises(InvalidQueryParameterError, match="Minutes must be a non-negative integer"):
            query.in_last_minutes(-1)

    def test_invalid_date_range(self):
        query = Query()
        with pytest.raises(InvalidQueryParameterError, match="Start date must be before end date"):
            query.date_range(datetime(2023, 10, 10), datetime(2023, 10, 9))

    def test_invalid_test_outcome_type(self):
        query = Query()
        with pytest.raises(InvalidQueryParameterError, match="Invalid outcome: UNKNOWN. Must be one of:"):
            query.with_outcome("UNKNOWN")

    def test_empty_session_list_returns_empty_query_result(self):
        query = Query()
        result = query.execute(sessions=[])
        assert result.empty is True
        assert result.total_count == 0
        assert result.execution_time >= 0

    def test_non_testsession_objects_raise_error(self):
        query = Query()
        with pytest.raises(QueryExecutionError, match="Invalid session type"):
            query.execute(sessions=[object()])

    def test_query_maintains_filter_chain_state(self, mocker):
        mock_session = mocker.Mock(spec=TestSession)
        mock_session.sut_name = "SUT1"
        mock_session.session_start_time = datetime.now()
        mock_session.duration = 10
        mock_session.test_results = []
        query = Query().for_sut("SUT1")
        result1 = query.execute(sessions=[mock_session])
        assert result1.total_count == 1
        result2 = query.execute(sessions=[mock_session])
        assert result2.total_count == 1

class Test_BeforeAfter:

    # Valid datetime parameter filters sessions before given timestamp
    def test_before_filters_sessions_by_timestamp(self):
        from pytest_insight.query.query import Query
        from pytest_insight.models import TestSession
        from datetime import datetime, timedelta

        # Setup
        query = Query()
        timestamp = datetime(2023, 1, 1, 12, 0)

        # Create test sessions before and after timestamp
        sut_name = "larry"
        session_id = "session-12345"
        session_before = TestSession(sut_name=sut_name, session_id=session_id, session_start_time=timestamp - timedelta(hours=1), session_duration=10)
        session_after = TestSession(sut_name=sut_name, session_id=session_id, session_start_time=timestamp + timedelta(hours=1), session_duration=10)

        # Apply filter
        query.before(timestamp)

        # Test filter function
        filter_func = query._filters[0]
        assert filter_func(session_before) is True
        assert filter_func(session_after) is False

    # Passing None as timestamp parameter raises InvalidQueryParameterError
    def test_before_raises_on_invalid_timestamp(self):
        from pytest_insight.query.query import Query, InvalidQueryParameterError
        import pytest

        query = Query()

        with pytest.raises(InvalidQueryParameterError) as exc_info:
            query.before(None)

        assert str(exc_info.value) == "Timestamp must be a datetime object"

    # Method returns Query instance for method chaining
    def test_method_returns_query_instance(self):
        from datetime import datetime
        from pytest_insight.query.query import Query

        query_instance = Query()
        result = query_instance.before(datetime.now())

        assert isinstance(result, Query)

    # Filter function correctly added to _filters list
    def test_filter_function_added_to_filters_list(self):
        from datetime import datetime
        from pytest_insight.query.query import Query

        query_instance = Query()
        initial_filter_count = len(query_instance._filters)
        query_instance.before(datetime.now())

        assert len(query_instance._filters) == initial_filter_count + 1

    # Filter lambda correctly compares session_start_time with timestamp
    def test_filter_lambda_compares_session_start_time(self, mocker):
        from datetime import datetime
        from pytest_insight.query.query import Query
        from pytest_insight.models import TestSession

        query_instance = Query()
        timestamp = datetime(2023, 10, 1)
        query_instance.before(timestamp)

        mock_session = mocker.Mock(spec=TestSession)
        mock_session.session_start_time = datetime(2023, 9, 30)

        assert query_instance._filters[0](mock_session) is True

        mock_session.session_start_time = datetime(2023, 10, 2)

        assert query_instance._filters[0](mock_session) is False

    # Filter sessions with timestamp after given datetime returns filtered Query instance
    def test_after_filters_sessions_by_timestamp(self):
        from pytest_insight.query.query import Query
        from pytest_insight.models import TestSession
        from datetime import datetime, timedelta

        query = Query()
        timestamp = datetime(2023, 1, 1)

        # Create test sessions before and after timestamp
        sut_name = "larry"
        session_id = "session-12345"
        session1 = TestSession(sut_name=sut_name, session_id=session_id, session_start_time=timestamp - timedelta(days=1), session_duration=10)
        session2 = TestSession(sut_name=sut_name, session_id=session_id, session_start_time=timestamp + timedelta(days=1), session_duration=10)

        filtered_query = query.after(timestamp)

        # Verify filter is added and returns self
        assert filtered_query is query
        assert len(query._filters) == 1

        # Verify filter works correctly
        assert not query._filters[0](session1)
        assert query._filters[0](session2)

    # Raise InvalidQueryParameterError when timestamp is not datetime object
    def test_after_raises_error_for_invalid_timestamp(self):
        from pytest_insight.query.query import Query, InvalidQueryParameterError
        import pytest

        query = Query()
        invalid_timestamp = "2023-01-01"

        with pytest.raises(InvalidQueryParameterError) as exc_info:
            query.after(invalid_timestamp)

        assert str(exc_info.value) == "Timestamp must be a datetime object"

    # Method adds lambda filter function to _filters list
    def test_adds_lambda_filter_to_filters_list(self):
        from datetime import datetime
        from pytest_insight.query.query import Query

        query_instance = Query()
        initial_filter_count = len(query_instance._filters)
        query_instance.after(datetime.now())
        assert len(query_instance._filters) == initial_filter_count + 1

    # Filter correctly compares session_start_time with provided timestamp
    def test_filter_compares_session_start_time_correctly(self, mocker):
        from datetime import datetime, timedelta
        from pytest_insight.query.query import Query
        from pytest_insight.models import TestSession

        query_instance = Query()
        timestamp = datetime.now()
        query_instance.after(timestamp)

        mock_session = mocker.Mock(spec=TestSession)
        mock_session.session_start_time = timestamp + timedelta(seconds=1)

        assert query_instance._filters[0](mock_session) is True

        mock_session.session_start_time = timestamp - timedelta(seconds=1)
        assert query_instance._filters[0](mock_session) is False

    # Method supports method chaining by returning self
    def test_method_chaining_support(self):
        from datetime import datetime
        from pytest_insight.query.query import Query

        query_instance = Query()
        result = query_instance.after(datetime.now())
        assert result is query_instance
