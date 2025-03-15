import pytest
from datetime import datetime, timedelta, timezone
from pytest_insight.models import TestResult, TestSession, TestOutcome
from pytest_insight.query import Query, CustomFilter
from pytest_insight.storage import InMemoryStorage


def get_test_time(offset_seconds: int = 0) -> datetime:
    """Get a test timestamp with optional offset.

    Returns:
        A UTC datetime starting from 2023-01-01 plus the given offset in seconds.
        This provides consistent timestamps for test cases while avoiding any
        timezone issues.
    """
    base = datetime(2023, 1, 1, tzinfo=timezone.utc)
    return base + timedelta(seconds=offset_seconds)


def test_query_initialization(mock_session_no_reruns):
    """Test basic initialization of Query with no filters."""
    storage = InMemoryStorage()
    storage.save_session(mock_session_no_reruns)
    query = Query(storage=storage)
    result = query.execute()
    assert len(result.sessions) == 1
    assert result.sessions[0] == mock_session_no_reruns


def test_sut_filter(mock_session_no_reruns):
    """Test filtering by SUT name.

    Session-level filter that preserves all tests in matching sessions.
    """
    storage = InMemoryStorage()
    storage.save_session(mock_session_no_reruns)
    query = Query(storage=storage)
    result = query.for_sut("test_sut").execute()
    assert len(result.sessions) == 1
    assert result.sessions[0].sut_name == "test_sut"
    # All tests preserved in matching sessions
    assert len(result.sessions[0].test_results) == len(
        mock_session_no_reruns.test_results
    )


def test_days_filter(mock_session_no_reruns):
    """Test filtering by days.

    Session-level filter that preserves all tests in matching sessions.
    """
    storage = InMemoryStorage()
    storage.save_session(mock_session_no_reruns)
    query = Query(storage=storage)
    result = query.in_last_days(7).execute()
    assert len(result.sessions) == 1
    # All tests preserved in matching sessions
    assert len(result.sessions[0].test_results) == len(
        mock_session_no_reruns.test_results
    )

    # Test old session gets filtered out
    old_session = TestSession(
        sut_name="test_sut",
        session_id="old-123",
        session_start_time=get_test_time(-10 * 24 * 60 * 60),  # 10 days ago
        session_stop_time=get_test_time(
            -10 * 24 * 60 * 60 + 60
        ),  # 10 days ago + 1 minute
        test_results=[],
        rerun_test_groups=[],
    )
    storage = InMemoryStorage()
    storage.save_session(old_session)
    result = Query(storage=storage).in_last_days(7).execute()
    assert len(result.sessions) == 0


def test_outcome_filter(mock_test_result_pass, mock_test_result_fail):
    """Test filtering by test outcome.

    Test-level filter that:
    1. Returns sessions containing ANY matching test
    2. Preserves ALL tests in matching sessions
    3. Maintains session context (metadata, relationships)
    """
    session = TestSession(
        sut_name="test_sut",
        session_id="test-123",
        session_start_time=get_test_time(),
        session_stop_time=get_test_time(2),  # 2 seconds total duration
        test_results=[mock_test_result_pass, mock_test_result_fail],
        rerun_test_groups=[],
    )
    storage = InMemoryStorage()
    storage.save_session(session)
    query = Query(storage=storage)
    result = query.filter_by_test().with_outcome(TestOutcome.PASSED).apply().execute()
    assert len(result.sessions) == 1
    # Session context preserved - both tests still present
    assert len(result.sessions[0].test_results) == 2
    # At least one test matches the filter
    assert any(t.outcome == TestOutcome.PASSED for t in result.sessions[0].test_results)
    # Session metadata preserved
    assert result.sessions[0].session_id == "test-123"
    assert result.sessions[0].sut_name == "test_sut"


def has_warning(test: TestResult) -> bool:
    """Custom predicate for filtering tests with warnings."""
    return test.has_warning


def test_warnings_filter(mock_test_result_pass):
    """Test filtering by warning presence using custom filter.

    Test-level filter that:
    1. Returns sessions containing ANY test with warning
    2. Preserves ALL tests in matching sessions
    3. Maintains session context (metadata, relationships)
    """
    warning_result = TestResult(
        nodeid="test_warn.py::test_warning",
        outcome=TestOutcome.PASSED,
        start_time=get_test_time(1),  # Start 1 second after first test
        duration=1.0,
        has_warning=True,
    )
    session = TestSession(
        sut_name="test_sut",
        session_id="test-123",
        session_start_time=get_test_time(),
        session_stop_time=get_test_time(2),  # 2 seconds total duration
        test_results=[mock_test_result_pass, warning_result],
        rerun_test_groups=[],
    )
    storage = InMemoryStorage()
    storage.save_session(session)
    query = Query(storage=storage)

    result = (
        query.filter_by_test()
        .with_custom_filter(has_warning, "has_warning")
        .apply()
        .execute()
    )
    assert len(result.sessions) == 1
    # Session context preserved - both tests still present
    assert len(result.sessions[0].test_results) == 2
    # At least one test has a warning
    assert any(r.has_warning for r in result.sessions[0].test_results)
    # Session metadata preserved
    assert result.sessions[0].session_id == "test-123"
    assert result.sessions[0].sut_name == "test_sut"


def test_pattern_matching():
    """Test pattern matching rules.

    Pattern matching rules:
    1. Non-regex patterns:
       - Matches are done using fnmatch with wildcards (*pattern*)
       - Pattern is matched against both file parts and test names separately
       - File part has .py extension removed before matching
       - Any part matching the pattern counts as a match
    2. Session context preservation:
       - Sessions containing ANY matching test are included
       - ALL tests in matching sessions are preserved
       - Session metadata (tags, IDs) is preserved
    """
    # Create test with module and test name parts
    test_in_module = TestResult(
        nodeid="test_api.py::test_get_user",
        outcome=TestOutcome.PASSED,
        start_time=get_test_time(),
        duration=1.0,
    )
    test_in_name = TestResult(
        nodeid="test_other.py::test_api_endpoint",
        outcome=TestOutcome.PASSED,
        start_time=get_test_time(1),
        duration=1.0,
    )
    session = TestSession(
        sut_name="test_sut",
        session_id="test-123",
        session_start_time=get_test_time(),
        session_stop_time=get_test_time(2),  # 2 seconds total duration
        test_results=[test_in_module, test_in_name],
        rerun_test_groups=[],
    )

    storage = InMemoryStorage()
    storage.save_session(session)

    # Pattern matches module part (after .py strip)
    query = Query(storage=storage)
    result = query.filter_by_test().with_pattern("api").apply().execute()
    assert len(result.sessions) == 1
    # Session context preserved - both tests still present
    assert len(result.sessions[0].test_results) == 2
    # At least one test matches pattern in module part
    assert any("test_api" in r.nodeid for r in result.sessions[0].test_results)
    # Session metadata preserved
    assert result.sessions[0].session_id == "test-123"
    assert result.sessions[0].sut_name == "test_sut"

    # Pattern matches test name part
    result = query.filter_by_test().with_pattern("endpoint").apply().execute()
    assert len(result.sessions) == 1
    # Session context preserved - both tests still present
    assert len(result.sessions[0].test_results) == 2
    # At least one test matches pattern in test name
    assert any("api_endpoint" in r.nodeid for r in result.sessions[0].test_results)
    # Session metadata preserved
    assert result.sessions[0].session_id == "test-123"
    assert result.sessions[0].sut_name == "test_sut"


def test_multiple_filters(mock_session_no_reruns):
    """Test combining multiple filters.

    Demonstrates:
    1. Session-level filters (SUT, time range)
    2. Test-level filters (outcome)
    3. Session context preservation
       - Sessions containing ANY matching test are included
       - ALL tests in matching sessions are preserved
       - Session metadata (tags, IDs) is preserved
    """
    # Create test session with mixed outcomes
    session = TestSession(
        sut_name="test_sut",
        session_id="test-123",
        session_start_time=get_test_time(),
        session_stop_time=get_test_time(3),  # 3 seconds total duration
        test_results=[
            TestResult(
                nodeid="test_api.py::test_get",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(),
                duration=1.0,
            ),
            TestResult(
                nodeid="test_api.py::test_post",
                outcome=TestOutcome.FAILED,
                start_time=get_test_time(1),
                duration=1.0,
            ),
        ],
        rerun_test_groups=[],
    )

    storage = InMemoryStorage()
    storage.save_session(session)

    # Apply multiple filters
    query = Query(storage=storage)
    result = (
        query.for_sut("test_sut")  # Session-level filter
        .in_last_days(7)  # Session-level filter
        .filter_by_test()
        .with_outcome(TestOutcome.PASSED)  # Test-level filter
        .apply()
        .execute()
    )

    assert len(result.sessions) == 1
    filtered_session = result.sessions[0]

    # Verify session-level filters worked
    assert filtered_session.sut_name == "test_sut"
    assert (get_test_time() - filtered_session.session_start_time).days < 7

    # Verify test-level filter worked but preserved context
    assert len(filtered_session.test_results) == 2  # Both tests preserved
    assert any(t.outcome == TestOutcome.PASSED for t in filtered_session.test_results)

    # Verify session metadata preserved
    assert filtered_session.session_id == "test-123"
    assert filtered_session.sut_name == "test_sut"
