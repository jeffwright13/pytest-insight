"""Test the query filters."""

import datetime as dt_module
from datetime import timedelta

import pytest
from pytest_insight.core.models import TestOutcome, TestResult, TestSession
from pytest_insight.core.query import Query
from pytest_insight.core.storage import InMemoryStorage


@pytest.fixture
def test_query_initialization(test_session_no_reruns):
    """Test basic initialization of Query with no filters."""
    # Create a unique profile name for this test
    profile_name = "test_query_initialization_profile"

    # Initialize storage and add the profile name attribute
    storage = InMemoryStorage()
    storage.profile_name = profile_name

    storage.save_session(test_session_no_reruns)

    # Create query with profile name
    query = Query(profile_name=profile_name)

    # Mock the execute method to use our storage directly
    original_execute = query.execute
    query.execute = lambda sessions=None: original_execute(
        sessions=storage.load_sessions() if sessions is None else sessions
    )

    result = query.execute()
    assert len(result.sessions) == 1
    assert result.sessions[0] == test_session_no_reruns


def test_sut_filter(test_session_no_reruns):
    """Test filtering by SUT name.

    Session-level filter that preserves all tests in matching sessions.
    """
    # Create a unique profile name for this test
    profile_name = "test_sut_filter_profile"

    # Initialize storage and add the profile name attribute
    storage = InMemoryStorage()
    storage.profile_name = profile_name

    storage.save_session(test_session_no_reruns)

    # Create query with profile name
    query = Query(profile_name=profile_name)

    # Mock the execute method to use our storage directly
    original_execute = query.execute
    query.execute = lambda sessions=None: original_execute(
        sessions=storage.load_sessions() if sessions is None else sessions
    )

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
    # Get a fixed time for testing
    mock_now = get_test_time(3600)  # 1 hour after base time

    # Create a mock datetime object with a now method that returns our fixed time
    mock_datetime = mocker.MagicMock()
    mock_datetime.now.return_value = mock_now
    # Preserve the original timedelta for calculations
    mock_datetime.timedelta = mocker.patch(
        "pytest_insight.core.query.dt_module.timedelta", wraps=dt_module.timedelta
    )
    # Preserve the original timezone for UTC
    mock_datetime.timezone = mocker.patch(
        "pytest_insight.core.query.dt_module.timezone", wraps=dt_module.timezone
    )

    # Patch dt_module.datetime, not dt_module.datetime.now
    mocker.patch("pytest_insight.core.query.dt_module.datetime", mock_datetime)

    # Create a unique profile name for this test
    profile_name = "test_days_filter_profile"

    # Initialize storage and add the profile name attribute
    storage = InMemoryStorage()
    storage.profile_name = profile_name

    storage.save_session(test_session_no_reruns)

    # Create query with profile name
    query = Query(profile_name=profile_name)

    # Mock the execute method to use our storage directly
    original_execute = query.execute
    query.execute = lambda sessions=None: original_execute(
        sessions=storage.load_sessions() if sessions is None else sessions
    )

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

    # Create a new query with the same profile
    query = Query(profile_name=profile_name)

    # Mock the execute method to use our storage directly
    original_execute = query.execute
    query.execute = lambda sessions=None: original_execute(
        sessions=storage.load_sessions() if sessions is None else sessions
    )

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

    # Create a unique profile name for this test
    profile_name = "test_outcome_filter_profile"

    # Initialize storage and add the profile name attribute
    storage = InMemoryStorage()
    storage.profile_name = profile_name

    storage.save_session(session)

    # Create query with profile name
    query = Query(profile_name=profile_name)

    # Mock the execute method to use our storage directly
    original_execute = query.execute
    query.execute = lambda sessions=None: original_execute(
        sessions=storage.load_sessions() if sessions is None else sessions
    )

    result = query.with_outcome(TestOutcome.PASSED).execute()

    assert len(result.sessions) == 1
    # Only matching tests included in new session
    assert len(result.sessions[0].test_results) == 1
    # Test matches the filter
    assert all(t.outcome == TestOutcome.PASSED for t in result.sessions[0].test_results)
    # Session metadata preserved
    assert result.sessions[0].session_id == "test-123"


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
        session_start_time=test_result_pass.start_time,  # Use fixture's timezone-aware time
        session_stop_time=test_result_pass.start_time + timedelta(minutes=1),
        test_results=[test_result_warning, test_result_pass],
        rerun_test_groups=[],
    )

    # Create a unique profile name for this test
    profile_name = "test_warnings_filter_profile"

    # Initialize storage and add the profile name attribute
    storage = InMemoryStorage()
    storage.profile_name = profile_name

    storage.save_session(session)

    # Create query with profile name
    query = Query(profile_name=profile_name)

    # Mock the execute method to use our storage directly
    original_execute = query.execute
    query.execute = lambda sessions=None: original_execute(
        sessions=storage.load_sessions() if sessions is None else sessions
    )

    result = query.filter_by_test().with_warning().apply().execute()

    assert len(result.sessions) == 1
    # Only tests with warnings included
    assert len(result.sessions[0].test_results) == 1
    # Test matches the filter
    assert all(t.has_warning for t in result.sessions[0].test_results)
    # Session metadata preserved
    assert result.sessions[0].session_id == "test-123"


def test_pattern_matching(get_test_time):
    """Test pattern matching behavior in test-level filtering.

    Key aspects:
    1. Pattern Matching:
       - Simple substring matching for specified field
       - field_name parameter is required
       - Case-sensitive matching

    2. Test-Level Filtering:
       - Returns sessions containing ANY matching test
       - Creates new sessions with ONLY matching tests
       - Original order maintained within matching tests

    3. Context Preservation:
       - Session metadata (tags, IDs) is preserved
       - Test relationships are maintained
       - Never returns isolated TestResult objects
    """
    # Create test session with tests having different fields to match against
    test1 = TestResult(
        nodeid="test_api.py::test_get",
        outcome=TestOutcome.PASSED,
        start_time=get_test_time(),  # Base time
        duration=1.0,
        caplog="API request succeeded",
        capstderr="",
        capstdout="",
    )
    test2 = TestResult(
        nodeid="test_api.py::test_post",
        outcome=TestOutcome.FAILED,
        start_time=get_test_time(5),  # 5 seconds later
        duration=1.0,
        caplog="API request failed with 500",
        capstderr="",
        capstdout="",
    )
    session = TestSession(
        sut_name="test_sut",
        session_id="test-123",
        session_start_time=get_test_time(),  # Same as first test
        session_stop_time=get_test_time(10),  # 10 seconds total duration
        test_results=[test1, test2],
        rerun_test_groups=[],
    )

    # Create a unique profile name for this test
    profile_name = "test_pattern_matching_profile"

    # Initialize storage and add the profile name attribute
    storage = InMemoryStorage()
    storage.profile_name = profile_name

    storage.save_session(session)

    # Test pattern matching in nodeid field
    query = Query(profile_name=profile_name)

    # Mock the execute method to use our storage directly
    original_execute = query.execute
    query.execute = lambda sessions=None: original_execute(
        sessions=storage.load_sessions() if sessions is None else sessions
    )

    result = (
        query.filter_by_test()
        .with_pattern("test_get", field_name="nodeid")
        .apply()
        .execute()
    )
    assert len(result.sessions) == 1
    # Only matching test included
    assert len(result.sessions[0].test_results) == 1
    assert "test_get" in result.sessions[0].test_results[0].nodeid

    # Test pattern matching in caplog field
    query = Query(profile_name=profile_name)

    # Mock the execute method to use our storage directly
    original_execute = query.execute
    query.execute = lambda sessions=None: original_execute(
        sessions=storage.load_sessions() if sessions is None else sessions
    )

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
    query = Query(profile_name=profile_name)

    # Mock the execute method to use our storage directly
    original_execute = query.execute
    query.execute = lambda sessions=None: original_execute(
        sessions=storage.load_sessions() if sessions is None else sessions
    )

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
    # Mock dt_module.datetime.now to return a fixed time relative to our test timestamps
    mock_now = get_test_time(3600)  # 1 hour after base time

    # Create a mock datetime object with a now method that returns our fixed time
    mock_datetime = mocker.MagicMock()
    mock_datetime.now.return_value = mock_now
    # Preserve the original timedelta for calculations
    mock_datetime.timedelta = mocker.patch(
        "pytest_insight.core.query.dt_module.timedelta", wraps=dt_module.timedelta
    )
    # Preserve the original timezone for UTC
    mock_datetime.timezone = mocker.patch(
        "pytest_insight.core.query.dt_module.timezone", wraps=dt_module.timezone
    )

    # Patch dt_module.datetime, not dt_module.datetime.now
    mocker.patch("pytest_insight.core.query.dt_module.datetime", mock_datetime)

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

    # Create a unique profile name for this test
    profile_name = "test_multiple_filters_profile"

    # Initialize storage and add the profile name attribute
    storage = InMemoryStorage()
    storage.profile_name = profile_name

    storage.save_session(session)

    # Apply both session-level and test-level filters
    query = Query(profile_name=profile_name)

    # Mock the execute method to use our storage directly
    original_execute = query.execute
    query.execute = lambda sessions=None: original_execute(
        sessions=storage.load_sessions() if sessions is None else sessions
    )

    result = (
        query.for_sut("test_sut")  # Session-level filter
        .in_last_days(7)  # Session-level filter
        .with_outcome(TestOutcome.PASSED)  # Test-level filter
        .execute()
    )

    assert not result.empty
    assert (
        len(result.sessions) == 1
    )  # Session is included because it has a matching test
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
