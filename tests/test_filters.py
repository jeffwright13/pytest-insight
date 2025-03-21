"""Test the query filters."""

from datetime import datetime, timedelta, timezone

import pytest
from pytest_insight.models import TestOutcome, TestResult, TestSession
from pytest_insight.query import Query
from pytest_insight.storage import InMemoryStorage


@pytest.fixture
def test_query_initialization(test_session_no_reruns):
    """Test basic initialization of Query with no filters."""
    storage = InMemoryStorage()
    storage.save_session(test_session_no_reruns)
    query = Query(storage=storage)
    result = query.execute()
    assert len(result.sessions) == 1
    assert result.sessions[0] == test_session_no_reruns


def test_sut_filter(test_session_no_reruns):
    """Test filtering by SUT name.

    Session-level filter that preserves all tests in matching sessions.
    """
    storage = InMemoryStorage()
    storage.save_session(test_session_no_reruns)
    query = Query(storage=storage)
    result = query.for_sut("test_sut").execute()
    assert len(result.sessions) == 1

    # All tests preserved in matching sessions
    assert len(result.sessions[0].test_results) == len(
        test_session_no_reruns.test_results
    )


def test_days_filter(test_session_no_reruns, get_test_time, mocker):
    """Test filtering by days.

    Session-level filter that preserves all tests in matching sessions.
    """
    # Mock datetime.now to return a fixed time relative to our test timestamps
    mock_now = get_test_time(3600)  # 1 hour after base time
    mock_datetime = mocker.MagicMock()
    mock_datetime.now = mocker.MagicMock(return_value=mock_now)
    mock_zoneinfo = mocker.MagicMock()
    mock_zoneinfo.return_value = mock_now.tzinfo
    mocker.patch("pytest_insight.query.datetime", mock_datetime)
    mocker.patch("pytest_insight.query.ZoneInfo", mock_zoneinfo)

    storage = InMemoryStorage()
    storage.save_session(test_session_no_reruns)
    query = Query(storage=storage)
    result = query.in_last_days(7).execute()
    assert len(result.sessions) == 1

    # All tests preserved in matching sessions
    assert len(result.sessions[0].test_results) == len(
        test_session_no_reruns.test_results
    )

    # Test old session gets filtered out
    old_session = TestSession(
        sut_name="test_sut",
        session_id="old-session",
        session_start_time=get_test_time(-864000),  # 10 days ago
        session_stop_time=get_test_time(-777600),  # 9 days ago
        test_results=[],
    )
    storage.save_session(old_session)
    result = query.in_last_days(7).execute()
    assert len(result.sessions) == 1


def test_outcome_filter(test_result_pass, test_result_fail):
    """Test filtering by test outcome.

    Test-level filter that:
    1. Returns sessions containing ANY matching test
    2. Creates new sessions with only matching tests
    3. Maintains session context (metadata, relationships)
    """
    session = TestSession(
        sut_name="test_sut",
        session_id="test-123",
        session_start_time=test_result_pass.start_time,  # Use fixture's timezone-aware time
        session_stop_time=test_result_pass.start_time + timedelta(minutes=1),
        test_results=[test_result_pass, test_result_fail],
        rerun_test_groups=[],
    )
    storage = InMemoryStorage()
    storage.save_session(session)

    query = Query(storage=storage)
    result = query.filter_by_test().with_outcome(TestOutcome.PASSED).apply().execute()

    assert len(result.sessions) == 1
    # Only matching tests included in new session
    assert len(result.sessions[0].test_results) == 1
    # Test matches the filter
    assert all(t.outcome == TestOutcome.PASSED for t in result.sessions[0].test_results)
    # Session metadata preserved
    assert result.sessions[0].session_id == "test-123"
    assert result.sessions[0].sut_name == "test_sut"


def test_warnings_filter(test_result_warning, test_result_pass):
    """Test filtering by warning presence using custom filter.

    Test-level filter that:
    1. Returns sessions containing ANY test with warning
    2. Creates new sessions with only tests containing warnings
    3. Maintains session context (metadata, relationships)
    """
    session = TestSession(
        sut_name="test_sut",
        session_id="test-123",
        session_start_time=test_result_warning.start_time,  # Use fixture's timezone-aware time
        session_stop_time=test_result_warning.start_time + timedelta(minutes=1),
        test_results=[test_result_warning, test_result_pass],  # Add a test without warning
        rerun_test_groups=[],
    )
    storage = InMemoryStorage()
    storage.save_session(session)

    query = Query(storage=storage)
    result = query.filter_by_test().with_warning().apply().execute()

    assert len(result.sessions) == 1
    # Only tests with warnings included
    assert len(result.sessions[0].test_results) == 1
    # Test has warning
    assert result.sessions[0].test_results[0].has_warning
    # Session metadata preserved
    assert result.sessions[0].session_id == "test-123"
    assert result.sessions[0].sut_name == "test_sut"


def test_pattern_matching(get_test_time):
    """Test pattern matching behavior in test-level filtering.

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
    # Create test with module and test name parts
    test_in_module = TestResult(
        nodeid="test_api.py::test_get_user",
        outcome=TestOutcome.PASSED,
        start_time=get_test_time(),  # Base time
        duration=1.0,
        caplog="API module test",
        capstderr="",
        capstdout="",
    )
    test_in_name = TestResult(
        nodeid="test_other.py::test_api_endpoint",
        outcome=TestOutcome.PASSED,
        start_time=get_test_time(5),  # 5 seconds later
        duration=1.0,
        caplog="API name test",
        capstderr="",
        capstdout="",
    )
    session = TestSession(
        sut_name="test_sut",
        session_id="test-123",
        session_start_time=get_test_time(),  # Same as first test
        session_stop_time=get_test_time(10),  # 10 seconds total duration
        test_results=[test_in_module, test_in_name],
        rerun_test_groups=[],
    )

    storage = InMemoryStorage()
    storage.save_session(session)

    # Test pattern matching in nodeid field
    query = Query(storage=storage)
    result = (
        query.filter_by_test()
        .with_pattern("api", field_name="nodeid")
        .apply()
        .execute()
    )
    assert len(result.sessions) == 1
    # Session context preserved - both tests still present
    assert len(result.sessions[0].test_results) == 2
    # Both tests match pattern in nodeid
    assert all("api" in r.nodeid.lower() for r in result.sessions[0].test_results)
    # Session metadata preserved
    assert result.sessions[0].session_id == "test-123"
    assert result.sessions[0].sut_name == "test_sut"

    # Test pattern matching in caplog field
    query = Query(storage=storage)
    result = (
        query.filter_by_test()
        .with_pattern("API", field_name="caplog")
        .apply()
        .execute()
    )
    assert len(result.sessions) == 1
    # Both tests match pattern in caplog
    assert all("API" in r.caplog for r in result.sessions[0].test_results)

    # Test case-sensitive pattern matching
    query = Query(storage=storage)
    result = (
        query.filter_by_test()
        .with_pattern("api", field_name="caplog")
        .apply()
        .execute()
    )
    assert len(result.sessions) == 0  # No matches due to case sensitivity


def test_multiple_filters(test_session_no_reruns, get_test_time, mocker):
    """Test combining multiple filters.

    Demonstrates the two-level filtering design:
    1. Session-Level Filters:
       - Filter entire test sessions (SUT, time range)
       - No modification of test results in matching sessions

    2. Test-Level Filters:
       - Creates new sessions with only matching tests
       - Preserves session metadata (tags, IDs)
       - Returns sessions that have at least one matching test

    3. Context Preservation:
       - Session metadata (tags, IDs) preserved
       - Test relationships maintained within matching tests
       - Original order of matching tests preserved
    """
    # Mock datetime.now to return a fixed time relative to our test timestamps
    mock_now = get_test_time(3600)  # 1 hour after base time
    mock_datetime = mocker.MagicMock()
    mock_datetime.now = mocker.MagicMock(return_value=mock_now)
    mock_zoneinfo = mocker.MagicMock()
    mock_zoneinfo.return_value = mock_now.tzinfo
    mocker.patch("pytest_insight.query.datetime", mock_datetime)
    mocker.patch("pytest_insight.query.ZoneInfo", mock_zoneinfo)

    # Create test session with mixed outcomes
    test_pass = TestResult(
        nodeid="test_api.py::test_get",
        outcome=TestOutcome.PASSED,
        start_time=get_test_time(),  # Base time
        duration=1.0,
        caplog="",
        capstderr="",
        capstdout="",
    )
    test_fail = TestResult(
        nodeid="test_api.py::test_post",
        outcome=TestOutcome.FAILED,
        start_time=get_test_time(5),  # 5 seconds later
        duration=1.0,
        caplog="",
        capstderr="",
        capstdout="",
    )
    session = TestSession(
        sut_name="test_sut",
        session_id="test-123",
        session_start_time=get_test_time(),  # Same as first test
        session_stop_time=get_test_time(10),  # 10 seconds total duration
        test_results=[test_pass, test_fail],
        rerun_test_groups=[],
    )

    storage = InMemoryStorage()
    storage.save_session(session)

    # Apply both session-level and test-level filters
    query = Query(storage=storage)
    result = (
        query.for_sut("test_sut")  # Session-level filter
        .in_last_days(7)  # Session-level filter
        .filter_by_test()  # Switch to test-level filtering
        .with_outcome(TestOutcome.PASSED)  # Test-level filter
        .apply()  # Back to session context
        .execute()
    )

    assert not result.empty
    assert len(result.sessions) == 1  # Session is included because it has a matching test
    filtered_session = result.sessions[0]

    # Verify session-level filters worked
    assert filtered_session.sut_name == "test_sut"
    assert (mock_now - filtered_session.session_start_time).days < 7

    # Verify test-level filter worked - only matching tests included
    assert len(filtered_session.test_results) == 1  # Only the passing test
    assert all(t.outcome == TestOutcome.PASSED for t in filtered_session.test_results)

    # Verify session metadata preserved
    assert filtered_session.session_id == "test-123"
    assert filtered_session.sut_name == "test_sut"
