from datetime import datetime, timedelta
from typing import List

import pytest
from freezegun import freeze_time  # Add this import
from pytest_insight.models import RerunTestGroup, TestOutcome, TestResult, TestSession
from pytest_insight.query.query import InvalidQueryParameterError, Query, QueryExecutionError


@pytest.fixture
def mock_session_now() -> TestSession:
    """Fixture providing a test session."""
    return TestSession(
        sut_name="test_sut",
        session_id="test-123",
        session_start_time=datetime.now(),
        session_stop_time=datetime.now(),
        test_results=[
            TestResult(nodeid="test_api.py::test_endpoint", outcome="PASSED", start_time=datetime.now(), duration=1.0)
        ],
        rerun_test_groups=[],
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
                duration=1.0,
            )
        ],
        rerun_test_groups=[],
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
                duration=1.0,
            )
        ],
        rerun_test_groups=[],
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
                duration=1.0,
            )
        ],
        rerun_test_groups=[],
    )


@pytest.fixture
def mock_sessions(
    mock_session_now,
    mock_session_1_day_1_hour_ago,
    mock_session_1_hour_1_minute_ago,
    mock_session_1_minute_1_second_ago,
) -> List[TestSession]:
    """Fixture providing a list of test sessions."""
    return [
        mock_session_now,
        mock_session_1_day_1_hour_ago,
        mock_session_1_hour_1_minute_ago,
        mock_session_1_minute_1_second_ago,
    ]


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
                duration=1.0,
            ),
            TestResult(
                nodeid="test_api.py::test_post",
                outcome="FAILED",
                start_time=datetime.now() - timedelta(days=7),
                duration=2.0,
            ),
        ],
        rerun_test_groups=[],
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
                duration=2.0,  # Slower
            ),
            TestResult(
                nodeid="test_api.py::test_post",
                outcome="PASSED",  # Fixed
                start_time=datetime.now(),
                duration=1.0,  # Faster
            ),
        ],
        rerun_test_groups=[],
    )


@pytest.fixture
def empty_query():
    """Fixture for empty query."""
    return Query(sessions=[], total_count=0, execution_time=0.0, matched_nodeids=set())


@pytest.fixture
def mock_session_with_reruns() -> TestSession:
    """Fixture providing a test session with reruns."""
    return TestSession(
        sut_name="test_sut",
        session_id="test-123",
        session_start_time=datetime.now(),
        session_stop_time=datetime.now(),
        test_results=[
            TestResult(nodeid="test_api.py::test_endpoint", outcome="PASSED", start_time=datetime.now(), duration=1.0)
        ],
        rerun_test_groups=[
            RerunTestGroup(
                nodeid="test_api.py::test_endpoint",
                tests=[
                    TestResult(
                        nodeid="test_api.py::test_endpoint", outcome="FAILED", start_time=datetime.now(), duration=0.6
                    ),
                    TestResult(
                        nodeid="test_api.py::test_endpoint",
                        outcome="RERUN",
                        start_time=datetime.now() - timedelta(seconds=0.5),
                        duration=0.3,
                    ),
                ],
            )
        ],
    )


class Test_Query:
    """Test suite for Query functionality."""

    def test_query_initialization(self):
        """Test basic Query initialization."""
        query = Query()
        assert isinstance(query, Query)
        assert len(query._session_filters) == 0
        assert len(query._test_filters) == 0

    def test_for_sut_filter(self, mock_sessions):
        """Test SUT name filtering."""
        query = Query()
        result = query.for_sut("api-service").execute(mock_sessions)
        assert len(result.sessions) == 1
        assert result.sessions[0].sut_name == "api-service"

    def test_for_sut_validation(self):
        """Test SUT name validation."""
        query = Query()
        with pytest.raises(InvalidQueryParameterError):
            query.for_sut("")

    def test_session_tag_filter(self, mock_sessions):
        """Test session tag filtering."""
        query = Query()
        result = query.with_session_tag("env", "dev").execute(mock_sessions)
        assert len(result.sessions) == 1
        assert result.sessions[0].session_tags["env"] == "dev"

    def test_session_tag_validation(self):
        """Test session tag validation."""
        query = Query()
        with pytest.raises(InvalidQueryParameterError):
            query.with_session_tag("", "value")
        with pytest.raises(InvalidQueryParameterError):
            query.with_session_tag("key", "")
        with pytest.raises(InvalidQueryParameterError):
            query.with_session_tag(None, "value")
        with pytest.raises(InvalidQueryParameterError):
            query.with_session_tag("key", None)

    def test_combined_filters(self, mock_sessions):
        """Test combining multiple session-level filters."""
        query = Query()
        result = (query
            .for_sut("api-service")
            .with_session_tag("env", "dev")
            .execute(mock_sessions))
        assert len(result.sessions) == 1
        assert result.sessions[0].sut_name == "api-service"
        assert result.sessions[0].session_tags["env"] == "dev"

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
            rerun_test_groups=[],
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
            rerun_test_groups=[],
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
            rerun_test_groups=[],
        )
        result = query.execute([old_session])
        assert result.empty

    def test_with_outcome(self, mock_sessions):
        """Test outcome filtering."""
        query = Query().with_outcome("PASSED")
        result = query.execute(mock_sessions)

        assert not result.empty
        assert all(any(t.outcome == "PASSED" for t in s.test_results) for s in result.sessions)

    def test_having_warnings(self, mock_session_now):
        """Test warning presence filtering."""
        warning_result = TestResult(
            nodeid="test_warn.py::test_warning",
            outcome="PASSED",
            start_time=datetime.now(),
            duration=1.0,
            has_warning=True,
        )
        mock_session_now.test_results.append(warning_result)
        query = Query().having_warnings(True)
        result = query.execute([mock_session_now])
        assert not result.empty
        assert any(t.has_warning for s in result.sessions for t in s.test_results)

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
        query = Query().for_sut("api-service").in_last_days(7).with_outcome("PASSED")
        result = query.execute(mock_sessions)
        assert result.empty
        assert result.total_count == 0
        assert result.matched_nodeids == set()

    def test_query_chaining_with_matches(self, base_session, target_session):
        """Test query method chaining and execution with matching sessions."""
        query = Query().for_sut("api-service").in_last_days(7).with_outcome("PASSED")
        result = query.execute([base_session, target_session])

        assert not result.empty
        assert result.total_count == 1
        assert any(any(t.outcome == "PASSED" for t in s.test_results) for s in result.sessions)

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
                test_results=[],
            ),
            TestSession(  # Just inside 7 days
                sut_name="api-service",
                session_id="7d-minus-1min",
                session_start_time=now - timedelta(days=7, minutes=-1),
                session_duration=1.0,
                test_results=[],
            ),
            TestSession(  # Just outside 7 days
                sut_name="api-service",
                session_id="7d-plus-1min",
                session_start_time=now - timedelta(days=7, minutes=1),
                session_duration=1.0,
                test_results=[],
            ),
        ]

    def test_in_last_days_boundary(self, now, sessions_at_boundaries, mocker):
        """Test exact boundary conditions for in_last_days."""
        mocker.patch("pytest_insight.query.query.datetime")
        mocker.patch("pytest_insight.query.query.datetime.now", return_value=now)

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
        result = query.execute(
            [
                TestSession(
                    sut_name="api-service",
                    session_id="exact-time",
                    session_start_time=now,
                    session_duration=0.0,
                    test_results=[],
                )
            ]
        )
        assert len(result.sessions) == 1

    def test_timezone_handling(self):
        """Test handling of timezone-aware datetimes."""
        from datetime import timezone

        utc_now = datetime.now(timezone.utc)
        est_now = datetime.now(timezone(timedelta(hours=-5)))

        # Test with timezone-aware and naive datetimes
        with pytest.raises(InvalidQueryParameterError):
            Query().date_range(utc_now, est_now)

    @freeze_time("2025-03-04 12:00:00")
    def test_combined_time_filters(self, now):
        """Test multiple time-based filters together."""
        query = Query().in_last_days(7).in_last_hours(24)

        # Should use most restrictive filter (24 hours)
        cutoff_days = now - timedelta(days=7)
        cutoff_hours = now - timedelta(hours=24)

        session_old = TestSession(
            sut_name="test-sut", session_id="old", session_start_time=cutoff_days, session_duration=2.0, test_results=[]
        )
        session_recent = TestSession(
            sut_name="test-sut",
            session_id="recent",
            session_start_time=cutoff_hours + timedelta(minutes=1),
            session_duration=2.0,
            test_results=[],
        )

        result = query.execute([session_old, session_recent])
        assert len(result.sessions) == 1
        assert result.sessions[0].session_id == "recent"

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
            TestSession(sut_name="sut2", session_id="2", session_start_time=datetime.now(), session_duration=10),
        ]
        storage_mock = mocker.patch("pytest_insight.query.query.get_storage_instance")
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
        session1 = TestSession(
            sut_name="SUT1", session_id="1", session_start_time=now - timedelta(days=5), session_duration=10
        )
        session2 = TestSession(
            sut_name="SUT2", session_id="2", session_start_time=now - timedelta(days=3), session_duration=10
        )
        session3 = TestSession(
            sut_name="SUT3", session_id="3", session_start_time=now - timedelta(days=1), session_duration=10
        )
        sessions = [session1, session2, session3]
        query = Query().date_range(now - timedelta(days=4), now)
        result = query.execute(sessions)
        assert len(result.sessions) == 2
        assert session2 in result.sessions
        assert session3 in result.sessions

    def test_outcome_filter(self):
        """Test filtering by test outcome."""
        # Create test data with enum outcomes
        result_passed = TestResult(nodeid="test_1", outcome=TestOutcome.PASSED, start_time=datetime.now(), duration=1.0)
        result_failed = TestResult(nodeid="test_2", outcome=TestOutcome.FAILED, start_time=datetime.now(), duration=1.0)

        # Create test sessions
        session1 = TestSession(
            sut_name="SUT1",
            session_id="1",
            session_start_time=datetime.now(),
            session_duration=1.5,
            test_results=[result_passed],
        )
        session2 = TestSession(
            sut_name="SUT2",
            session_id="2",
            session_start_time=datetime.now(),
            session_duration=1.5,
            test_results=[result_failed],
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
            sut_name="SUT1",
            session_id="1",
            session_start_time=datetime.now() - timedelta(days=1),
            session_stop_time=datetime.now(),
            session_duration=86400,
            test_results=[],
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
        mock_storage = mocker.patch("pytest_insight.query.query.get_storage_instance")
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
        from datetime import datetime, timedelta

        from pytest_insight.models import TestSession
        from pytest_insight.query.query import Query

        # Setup
        query = Query()
        timestamp = datetime(2023, 1, 1, 12, 0)

        # Create test sessions before and after timestamp
        sut_name = "larry"
        session_id = "session-12345"
        session_before = TestSession(
            sut_name=sut_name,
            session_id=session_id,
            session_start_time=timestamp - timedelta(hours=1),
            session_duration=10,
        )
        session_after = TestSession(
            sut_name=sut_name,
            session_id=session_id,
            session_start_time=timestamp + timedelta(hours=1),
            session_duration=10,
        )

        # Apply filter
        query.before(timestamp)

        # Verify filter is added and returns self
        assert len(query._session_filters) == 1

        # Test filter function
        filter_func = query._session_filters[0]
        assert filter_func(session_before) is True
        assert filter_func(session_after) is False

    # Passing None as timestamp parameter raises InvalidQueryParameterError
    def test_before_raises_on_invalid_timestamp(self):
        import pytest
        from pytest_insight.query.query import InvalidQueryParameterError, Query

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

    # Filter function correctly added to _session_filters list
    def test_filter_function_added_to_filters_list(self):
        from datetime import datetime

        from pytest_insight.query.query import Query

        query_instance = Query()
        initial_filter_count = len(query_instance._session_filters)
        query_instance.before(datetime.now())

        assert len(query_instance._session_filters) == initial_filter_count + 1

    # Filter lambda correctly compares session_start_time with timestamp
    def test_filter_lambda_compares_session_start_time(self, mocker):
        from datetime import datetime

        from pytest_insight.models import TestSession
        from pytest_insight.query.query import Query

        query_instance = Query()
        timestamp = datetime(2023, 10, 1)
        query_instance.before(timestamp)

        mock_session = mocker.Mock(spec=TestSession)
        mock_session.session_start_time = datetime(2023, 9, 30)

        assert query_instance._session_filters[0](mock_session) is True

        mock_session.session_start_time = datetime(2023, 10, 2)

        assert query_instance._session_filters[0](mock_session) is False

    # Filter sessions with timestamp after given datetime returns filtered Query instance
    def test_after_filters_sessions_by_timestamp(self):
        from datetime import datetime, timedelta

        from pytest_insight.models import TestSession
        from pytest_insight.query.query import Query

        # Setup
        query = Query()
        timestamp = datetime(2023, 1, 1)

        # Create test sessions before and after timestamp
        sut_name = "larry"
        session_id = "session-12345"
        session1 = TestSession(
            sut_name=sut_name,
            session_id=session_id,
            session_start_time=timestamp - timedelta(days=1),
            session_duration=10,
        )
        session2 = TestSession(
            sut_name=sut_name,
            session_id=session_id,
            session_start_time=timestamp + timedelta(days=1),
            session_duration=10,
        )

        filtered_query = query.after(timestamp)

        # Verify filter is added and returns self
        assert filtered_query is query
        assert len(query._session_filters) == 1

        # Verify filter works correctly
        filter_func = query._session_filters[0]
        assert not filter_func(session1)
        assert filter_func(session2)

    # Raise InvalidQueryParameterError when timestamp is not datetime object
    def test_after_raises_error_for_invalid_timestamp(self):
        import pytest
        from pytest_insight.query.query import InvalidQueryParameterError, Query

        query = Query()
        invalid_timestamp = "2023-01-01"

        with pytest.raises(InvalidQueryParameterError) as exc_info:
            query.after(invalid_timestamp)

        assert str(exc_info.value) == "Timestamp must be a datetime object"

    # Method adds lambda filter function to _session_filters list
    def test_adds_lambda_filter_to_filters_list(self):
        from datetime import datetime

        from pytest_insight.query.query import Query

        query_instance = Query()
        initial_filter_count = len(query_instance._session_filters)
        query_instance.after(datetime.now())
        assert len(query_instance._session_filters) == initial_filter_count + 1

    # Filter correctly compares session_start_time with provided timestamp
    def test_filter_compares_session_start_time_correctly(self, mocker):
        from datetime import datetime, timedelta

        from pytest_insight.models import TestSession
        from pytest_insight.query.query import Query

        query_instance = Query()
        timestamp = datetime.now()
        query_instance.after(timestamp)

        mock_session = mocker.Mock(spec=TestSession)
        mock_session.session_start_time = timestamp + timedelta(seconds=1)

        assert query_instance._session_filters[0](mock_session) is True

        mock_session.session_start_time = timestamp - timedelta(seconds=1)
        assert query_instance._session_filters[0](mock_session) is False

    # Method supports method chaining by returning self
    def test_method_chaining_support(self):
        from datetime import datetime

        from pytest_insight.query.query import Query

        query_instance = Query()
        result = query_instance.after(datetime.now())
        assert result is query_instance

    def test_before_after_filter_chain(self):
        """Test that before() and after() can be chained and both filters work correctly."""
        from datetime import datetime, timedelta

        from pytest_insight.models import TestSession
        from pytest_insight.query.query import Query

        # Setup test data
        now = datetime(2023, 1, 1, 12, 0)
        before_time = now + timedelta(hours=2)  # 2pm
        after_time = now - timedelta(hours=2)   # 10am

        # Create sessions at different times
        sessions = [
            TestSession(  # 11am - should match
                sut_name="test",
                session_id="1",
                session_start_time=now - timedelta(hours=1),
                session_duration=10,
            ),
            TestSession(  # 3pm - should not match (too late)
                sut_name="test",
                session_id="2",
                session_start_time=now + timedelta(hours=3),
                session_duration=10,
            ),
            TestSession(  # 9am - should not match (too early)
                sut_name="test",
                session_id="3",
                session_start_time=now - timedelta(hours=3),
                session_duration=10,
            ),
        ]

        # Create query and chain filters
        query = Query()
        result = query.before(before_time).after(after_time)

        # Verify chain returns query instance
        assert result is query
        assert len(query._session_filters) == 2

        # Test filters work correctly
        assert all(f(sessions[0]) for f in query._session_filters)  # 11am session matches
        assert not all(f(sessions[1]) for f in query._session_filters)  # 3pm session doesn't match
        assert not all(f(sessions[2]) for f in query._session_filters)  # 9am session doesn't match

        # Test execute() returns correct sessions
        result = query.execute(sessions)
        assert len(result.sessions) == 1
        assert result.sessions[0].session_id == "1"


class Test_QueryTestFilter:
    """Test suite for test-level filtering in Query."""

    def test_filter_by_pattern(self, test_sessions, mocker):
        """Test filtering tests by pattern."""
        query = Query()
        storage_mock = mocker.patch("pytest_insight.query.query.get_storage_instance")
        storage_mock.return_value.load_sessions.return_value = test_sessions
        result = query.filter_by_test().with_pattern("test_api").apply().execute()

        assert len(result.sessions) == 1
        assert result.sessions[0].session_id == "session1"

    def test_filter_by_duration(self, test_sessions, mocker):
        """Test filtering tests by duration."""
        query = Query()
        storage_mock = mocker.patch("pytest_insight.query.query.get_storage_instance")
        storage_mock.return_value.load_sessions.return_value = test_sessions
        # Find sessions with tests taking >= 3 seconds
        result = query.filter_by_test().with_duration(3.0, 10.0).apply().execute()

        assert len(result.sessions) == 1
        assert result.sessions[0].session_id == "session1"

    def test_filter_by_outcome(self, test_sessions, mocker):
        """Test filtering tests by outcome."""
        query = Query()
        storage_mock = mocker.patch("pytest_insight.query.query.get_storage_instance")
        storage_mock.return_value.load_sessions.return_value = test_sessions
        # Find sessions with failed tests
        result = query.filter_by_test().with_outcome(TestOutcome.FAILED).apply().execute()

        assert len(result.sessions) == 1
        assert result.sessions[0].session_id == "session1"

    def test_filter_by_skipped(self, test_sessions, mocker):
        """Test filtering tests by skipped outcome."""
        query = Query()
        storage_mock = mocker.patch("pytest_insight.query.query.get_storage_instance")
        storage_mock.return_value.load_sessions.return_value = test_sessions
        result = query.filter_by_test().with_outcome(TestOutcome.SKIPPED).apply().execute()

        assert len(result.sessions) == 1
        assert result.sessions[0].session_id == "session2"

    def test_combined_test_filters(self, test_sessions, mocker):
        """Test combining multiple test-level filters (AND logic within a single test)."""
        query = Query()
        storage_mock = mocker.patch("pytest_insight.query.query.get_storage_instance")
        storage_mock.return_value.load_sessions.return_value = test_sessions
        result = (
            query.filter_by_test()
            .with_pattern("test_api")
            .with_duration(3.0, 10.0)
            .with_outcome(TestOutcome.FAILED)
            .apply()
            .execute()
        )

        assert len(result.sessions) == 1
        assert result.sessions[0].session_id == "session1"

    def test_combined_test_and_session_filters(self, test_sessions, mocker):
        """Test combining test-level and session-level filters."""
        query = Query()
        storage_mock = mocker.patch("pytest_insight.query.query.get_storage_instance")
        storage_mock.return_value.load_sessions.return_value = test_sessions
        result = (
            query.for_sut("api-service")  # Match fixture sut_name
            .filter_by_test()
            .with_pattern("test_api")
            .apply()
            .execute()
        )

        assert len(result.sessions) == 1
        assert result.sessions[0].session_id == "session1"

    def test_no_matches(self, test_sessions, mocker):
        """Test when no sessions match the filters."""
        query = Query()
        storage_mock = mocker.patch("pytest_insight.query.query.get_storage_instance")
        storage_mock.return_value.load_sessions.return_value = test_sessions
        result = (
            query.filter_by_test()
            .with_pattern("nonexistent_test")
            .apply()
            .execute()
        )

        assert len(result.sessions) == 0
        assert result.empty

    def test_validation_errors(self):
        """Test validation errors in test filters."""
        query = Query()
        with pytest.raises(InvalidQueryParameterError):
            query.filter_by_test().with_pattern("").apply()
        with pytest.raises(InvalidQueryParameterError):
            query.filter_by_test().with_duration(-1, 10).apply()
        with pytest.raises(InvalidQueryParameterError):
            query.filter_by_test().with_duration(10, 5).apply()

    def test_empty_conditions(self, test_sessions, mocker):
        """Test applying an empty test filter."""
        query = Query()
        storage_mock = mocker.patch("pytest_insight.query.query.get_storage_instance")
        storage_mock.return_value.load_sessions.return_value = test_sessions
        result = query.filter_by_test().apply().execute()

        # Should return all sessions since no conditions were applied
        assert len(result.sessions) == len(test_sessions)

    def test_multiple_apply_calls(self, test_sessions, mocker):
        """Test applying multiple test filter groups."""
        query = Query()
        storage_mock = mocker.patch("pytest_insight.query.query.get_storage_instance")
        storage_mock.return_value.load_sessions.return_value = test_sessions
        result = (
            query.filter_by_test()
            .with_pattern("test_api")
            .apply()
            .filter_by_test()
            .with_duration(3.0, 10.0)
            .apply()
            .execute()
        )

        assert len(result.sessions) == 1
        assert result.sessions[0].session_id == "session1"

    def test_only_matching_one_test_keeps_session(self, test_sessions, mocker):
        """Test that a session is kept if at least one test matches all conditions."""
        query = Query()
        storage_mock = mocker.patch("pytest_insight.query.query.get_storage_instance")
        storage_mock.return_value.load_sessions.return_value = test_sessions
        result = (
            query.filter_by_test()
            .with_pattern("test_api")
            .with_duration(1.0, 2.0)  # Changed to match test_get's duration of 1.5s
            .apply()
            .execute()
        )

        assert len(result.sessions) == 1
        session = result.sessions[0]
        assert session.session_id == "session1"

from datetime import datetime

import pytest
from pytest_insight.models import TestSession


@pytest.fixture
def test_sessions():
    """Create a set of test sessions for filtering tests."""
    now = datetime.now()

    # Session 1: Mixed tests with different durations and outcomes
    session1 = TestSession(
        sut_name="api-service",
        session_id="session1",
        session_start_time=now - timedelta(days=1),
        session_stop_time=now - timedelta(days=1) + timedelta(seconds=30),
        test_results=[
            TestResult(
                nodeid="test_api.py::test_get",
                outcome=TestOutcome.PASSED,
                start_time=now - timedelta(days=1),
                duration=1.5,  # Medium duration
            ),
            TestResult(
                nodeid="test_api.py::test_post",
                outcome=TestOutcome.FAILED,
                start_time=now - timedelta(days=1),
                duration=0.5,  # Fast
            ),
            TestResult(
                nodeid="test_db.py::test_connection",
                outcome=TestOutcome.PASSED,
                start_time=now - timedelta(days=1),
                duration=5.0,  # Slow
            ),
        ],
        rerun_test_groups=[],
        session_tags={"env": "dev", "python": "3.9"},
    )

    # Session 2: All tests passed but different patterns
    session2 = TestSession(
        sut_name="web-service",
        session_id="session2",
        session_start_time=now - timedelta(hours=12),
        session_stop_time=now - timedelta(hours=12) + timedelta(seconds=20),
        test_results=[
            TestResult(
                nodeid="test_web.py::test_login",
                outcome=TestOutcome.PASSED,
                start_time=now - timedelta(hours=12),
                duration=1.0,
            ),
            TestResult(
                nodeid="test_web.py::test_logout",
                outcome=TestOutcome.PASSED,
                start_time=now - timedelta(hours=12),
                duration=0.8,
            ),
            TestResult(
                nodeid="test_auth.py::test_session",
                outcome=TestOutcome.SKIPPED,
                start_time=now - timedelta(hours=12),
                duration=0.1,
            ),
        ],
        rerun_test_groups=[],
        session_tags={"env": "prod", "python": "3.8"},
    )

    return [session1, session2]
