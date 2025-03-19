from datetime import datetime, timedelta, timezone

import pytest
from pytest_insight.models import TestOutcome, TestResult, TestSession
from pytest_insight.query import (
    DurationFilter,
    InvalidQueryParameterError,
    Query,
    QueryTestFilter,
    RegexPatternFilter,
    ShellPatternFilter,
)


def get_test_time(offset_seconds: int = 0) -> datetime:
    """Returns a consistent UTC datetime for test cases."""
    base = datetime(2023, 1, 1, tzinfo=timezone.utc)
    return base + timedelta(seconds=offset_seconds)


def test_query_pattern_methods():
    """Test Query pattern matching methods.

    Key aspects:
    1. Pattern Methods:
       - with_pattern requires field_name parameter
       - Convenience methods for common fields
       - Multiple filters can be combined

    2. Field Types:
       - nodeid: Test identifier
       - caplog: Log output
       - capstdout/capstderr: Standard output/error
       - longreprtext: Test error details
    """
    query = QueryTestFilter(Query())

    # Test with_pattern requires field_name
    with pytest.raises(TypeError):
        query.with_pattern("test")  # Missing required field_name

    filter = query.with_pattern("test", field_name="nodeid").filters[0]
    assert isinstance(filter, ShellPatternFilter)
    assert filter.field_name == "nodeid"

    # Test convenience methods
    query = QueryTestFilter(Query())
    filter = query.with_nodeid_containing("test").filters[0]
    assert filter.field_name == "nodeid"

    query = QueryTestFilter(Query())
    filter = query.with_log_containing("error").filters[0]
    assert filter.field_name == "caplog"

    query = QueryTestFilter(Query())
    filter = query.with_stdout_containing("output").filters[0]
    assert filter.field_name == "capstdout"

    query = QueryTestFilter(Query())
    filter = query.with_stderr_containing("error").filters[0]
    assert filter.field_name == "capstderr"

    # Test with_output_containing creates filters for all output fields
    query = QueryTestFilter(Query())
    query.with_output_containing("error")
    assert len(query.filters) == 3
    assert all(
        f.field_name in {"capstdout", "capstderr", "caplog"} for f in query.filters
    )

    # Test with_error_containing uses longreprtext
    query = QueryTestFilter(Query())
    filter = query.with_error_containing("error").filters[0]
    assert filter.field_name == "longreprtext"


def test_query_execution():
    """Test query execution with pattern filters.

    Key aspects:
    1. Pattern Matching:
       - Simple substring matching on specified fields
       - Case-sensitive comparison
       - field_name parameter is required
       - No special handling for any fields

    2. Two-Level Filtering:
       - Session-level filters keep ALL tests in matching sessions
       - Test-level filters keep ONLY matching tests
       - Returns full TestSession objects

    3. Context Preservation:
       - Sessions containing ANY matching test are included
       - Only matching tests are kept in test-level filtering
       - Session metadata (tags, IDs) is maintained
    """
    session = TestSession(
        sut_name="api-service",
        session_id="test_session",
        session_start_time=get_test_time(),
        session_stop_time=get_test_time(3),
        test_results=[
            TestResult(
                nodeid="test_api.py::test_get",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(),
                duration=1.0,
                caplog="API request successful",
                capstdout="GET /api/v1/test",
                capstderr="",
                longreprtext="",
            ),
            TestResult(
                nodeid="test_core.py::test_error",
                outcome=TestOutcome.FAILED,
                start_time=get_test_time(1),
                duration=2.0,
                caplog="Error occurred",
                capstdout="",
                capstderr="Exception: API error",
                longreprtext="AssertionError: Expected success",
            ),
        ],
        session_tags={"type": "api", "component": "test"},
        rerun_test_groups=[],
    )

    # Test nodeid pattern matching
    query = Query().filter_by_test().with_nodeid_containing("test_api").apply()
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    # Only matching test should be included
    assert len(result.sessions[0].test_results) == 1
    assert result.sessions[0].test_results[0].nodeid == "test_api.py::test_get"
    # Session metadata is preserved
    assert result.sessions[0].session_tags == {"type": "api", "component": "test"}

    # Test output pattern matching
    query = Query().filter_by_test().with_log_containing("Error").apply()
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    # Only matching test should be included
    assert len(result.sessions[0].test_results) == 1
    assert result.sessions[0].test_results[0].nodeid == "test_core.py::test_error"

    # Test error pattern matching
    query = Query().filter_by_test().with_error_containing("AssertionError").apply()
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    # Only matching test should be included
    assert len(result.sessions[0].test_results) == 1
    assert result.sessions[0].test_results[0].nodeid == "test_core.py::test_error"
    # Session metadata is preserved
    assert result.sessions[0].session_tags == {"type": "api", "component": "test"}

    # Test complex query chain (pattern + outcome)
    query = (
        Query()
        .filter_by_test()
        .with_pattern("API", field_name="caplog")
        .with_outcome(TestOutcome.PASSED)
        .apply()
    )
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    # Only test matching both filters should be included
    assert len(result.sessions[0].test_results) == 1
    assert result.sessions[0].test_results[0].nodeid == "test_api.py::test_get"


def test_query_order_preservation():
    """Test that query execution preserves test order and session context."""
    session = TestSession(
        sut_name="api-service",
        session_id="test_session",
        session_start_time=get_test_time(),
        session_stop_time=get_test_time(3),
        test_results=[
            TestResult(
                nodeid="test_1.py::test_first",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(),
                duration=1.0,
                caplog="First test",
                capstdout="stdout 1",
                capstderr="stderr 1",
                longreprtext="error 1",
            ),
            TestResult(
                nodeid="test_2.py::test_second",
                outcome=TestOutcome.FAILED,
                start_time=get_test_time(1),
                duration=2.0,
                caplog="Second test",
                capstdout="stdout 2",
                capstderr="stderr 2",
                longreprtext="error 2",
            ),
            TestResult(
                nodeid="test_3.py::test_third",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(2),
                duration=3.0,
                caplog="Third test",
                capstdout="stdout 3",
                capstderr="stderr 3",
                longreprtext="error 3",
            ),
        ],
        session_tags={"a": "1", "b": "2", "c": "3"},
        rerun_test_groups=[],
    )

    # Test that order is preserved when filtering by pattern
    query = Query().filter_by_test().with_pattern("Second", field_name="caplog").apply()
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    # Only matching tests should be included
    assert len(result.sessions[0].test_results) == 1
    # Original test order is maintained
    assert result.sessions[0].test_results[0].nodeid == "test_2.py::test_second"
    # Session metadata is preserved
    assert result.sessions[0].session_tags == {"a": "1", "b": "2", "c": "3"}
    assert result.sessions[0].rerun_test_groups == session.rerun_test_groups

    # Verify session context is preserved
    filtered_session = result.sessions[0]
    assert filtered_session.sut_name == session.sut_name
    assert filtered_session.session_id == session.session_id
    assert filtered_session.session_start_time == session.session_start_time
    assert filtered_session.session_tags == {"a": "1", "b": "2", "c": "3"}
    assert filtered_session.rerun_test_groups == session.rerun_test_groups

    # Test that order is preserved with multiple filters
    query = (
        Query()
        .filter_by_test()
        .with_pattern("test", field_name="caplog")
        .with_outcome(TestOutcome.PASSED)
        .apply()
    )
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    # Only matching tests should be included
    assert len(result.sessions[0].test_results) == 2
    # Original test order is maintained
    assert result.sessions[0].test_results[0].nodeid == "test_1.py::test_first"
    assert result.sessions[0].test_results[1].nodeid == "test_3.py::test_third"

    # Verify A == B is same as B == A
    query1 = (
        Query()
        .filter_by_test()
        .with_pattern("test", field_name="caplog")
        .with_outcome(TestOutcome.PASSED)
        .apply()
    )
    query2 = (
        Query()
        .filter_by_test()
        .with_outcome(TestOutcome.PASSED)
        .with_pattern("test", field_name="caplog")
        .apply()
    )
    result1 = query1.execute(sessions=[session])
    result2 = query2.execute(sessions=[session])
    assert len(result1.sessions) == len(result2.sessions)
    # Only matching tests should be included
    assert len(result1.sessions[0].test_results) == 2
    assert len(result2.sessions[0].test_results) == 2
    # Original test order is maintained in both results
    nodeids1 = [t.nodeid for t in result1.sessions[0].test_results]
    nodeids2 = [t.nodeid for t in result2.sessions[0].test_results]
    assert nodeids1 == nodeids2
    assert nodeids1 == ["test_1.py::test_first", "test_3.py::test_third"]


def test_query_filtered_sessions():
    """Test filtering multiple sessions with test-level filters.

    Key aspects:
    1. Two-Level Filtering Design:
       - Session-level filters return ALL tests in matching sessions
       - Test-level filters create NEW sessions with ONLY matching tests
       - Both return complete TestSession objects (never isolated tests)

    2. Context Preservation:
       - Session metadata (tags, warnings) is preserved
       - Test relationships maintained within matching tests
       - Original order of matching tests preserved
       - Rerun groups preserved
    """
    # Session with reruns and warnings to verify context preservation
    session1 = TestSession(
        sut_name="api",
        session_id="session1",
        session_tags={"type": "api"},
        session_start_time=get_test_time(),
        session_stop_time=get_test_time(10),
        test_results=[
            TestResult(
                nodeid="test_get.py",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(),
                duration=1.0,
            ),
            TestResult(
                nodeid="test_post.py",
                outcome=TestOutcome.FAILED,
                start_time=get_test_time(1),
                duration=2.0,
            ),
        ],
        rerun_test_groups=[["test_post.py"]],  # Failed test was rerun
    )

    session2 = TestSession(
        sut_name="db",
        session_id="session2",
        session_tags={"type": "db"},
        session_start_time=get_test_time(),
        session_stop_time=get_test_time(10),
        test_results=[
            TestResult(
                nodeid="test_query.py",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(),
                duration=1.0,
            ),
            TestResult(
                nodeid="test_update.py",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(1),
                duration=0.5,
            ),
        ],
        rerun_test_groups=[],  # No reruns needed
    )

    # Test session-level filtering - returns ALL tests in matching sessions
    query = Query().for_sut("api")
    result = query.execute(sessions=[session1, session2])
    assert len(result.sessions) == 1
    # ALL tests included (session-level filter)
    assert len(result.sessions[0].test_results) == 2
    # Original test order maintained
    assert result.sessions[0].test_results[0].nodeid == "test_get.py"
    assert result.sessions[0].test_results[1].nodeid == "test_post.py"
    # Session context preserved
    assert result.sessions[0].session_tags == {"type": "api"}
    assert result.sessions[0].rerun_test_groups == [["test_post.py"]]

    # Test test-level filtering - returns ONLY matching tests while preserving context
    query = Query().filter_by_test().with_outcome(TestOutcome.PASSED).apply()
    result = query.execute(sessions=[session1, session2])
    assert len(result.sessions) == 2
    # Only PASSED tests included in new sessions
    assert len(result.sessions[0].test_results) == 1
    assert len(result.sessions[1].test_results) == 2
    # All tests match filter
    assert all(t.outcome == TestOutcome.PASSED for t in result.sessions[0].test_results)
    assert all(t.outcome == TestOutcome.PASSED for t in result.sessions[1].test_results)
    # Original test order maintained within matching tests
    assert result.sessions[0].test_results[0].nodeid == "test_get.py"
    assert result.sessions[1].test_results[0].nodeid == "test_query.py"
    assert result.sessions[1].test_results[1].nodeid == "test_update.py"
    # Session context preserved
    assert result.sessions[0].session_tags == {"type": "api"}
    assert result.sessions[0].rerun_test_groups == [["test_post.py"]]
    assert result.sessions[1].session_tags == {"type": "db"}
    assert result.sessions[1].rerun_test_groups == []

    # Test shell pattern matching (substring)
    query = Query().filter_by_test().with_pattern("get|query", field_name="nodeid").apply()
    result = query.execute(sessions=[session1, session2])
    assert len(result.sessions) == 2
    # Only matching tests included
    assert len(result.sessions[0].test_results) == 1
    assert len(result.sessions[1].test_results) == 1
    # All tests match pattern
    assert all("get" in t.nodeid or "query" in t.nodeid for t in result.sessions[0].test_results)
    assert all("get" in t.nodeid or "query" in t.nodeid for t in result.sessions[1].test_results)
    # Session context preserved
    assert result.sessions[0].rerun_test_groups == [["test_post.py"]]
    assert result.sessions[1].rerun_test_groups == []

    # Test regex pattern matching
    query = (
        Query()
        .filter_by_test()
        .with_pattern("test_(get|query)\\.py$", field_name="nodeid", use_regex=True)
        .apply()
    )
    result = query.execute(sessions=[session1, session2])
    assert len(result.sessions) == 2
    # Only matching tests included
    assert len(result.sessions[0].test_results) == 1
    assert len(result.sessions[1].test_results) == 1
    # All tests match pattern
    assert all(t.nodeid in ["test_get.py", "test_query.py"] for t in result.sessions[0].test_results)
    assert all(t.nodeid in ["test_get.py", "test_query.py"] for t in result.sessions[1].test_results)
    # Session context preserved

    # Test combined filtering - session filtered first, then tests
    query = (
        Query()
        .for_sut("api")
        .filter_by_test()
        .with_outcome(TestOutcome.FAILED)
        .apply()
    )
    result = query.execute(sessions=[session1, session2])
    assert len(result.sessions) == 1
    # Only FAILED test in api session
    assert len(result.sessions[0].test_results) == 1
    assert result.sessions[0].test_results[0].nodeid == "test_post.py"
    # Session context preserved
    assert result.sessions[0].session_tags == {"type": "api"}
    assert result.sessions[0].rerun_test_groups == [["test_post.py"]]

    # Test no matches
    query = Query().for_sut("unknown")
    result = query.execute(sessions=[session1, session2])
    assert len(result.sessions) == 0

    # Additional test for multiple sessions with test-level filtering
    query = Query().filter_by_test().with_outcome(TestOutcome.PASSED).apply()
    result = query.execute(sessions=[session1, session2])
    assert len(result.sessions) == 2
    # Only PASSED tests included
    assert len(result.sessions[0].test_results) == 1
    assert len(result.sessions[1].test_results) == 2
    # All tests match filter
    assert all(t.outcome == TestOutcome.PASSED for t in result.sessions[0].test_results)
    assert all(t.outcome == TestOutcome.PASSED for t in result.sessions[1].test_results)
    # Original order maintained within matching tests
    assert result.sessions[0].test_results[0].nodeid == "test_get.py"
    assert result.sessions[1].test_results[0].nodeid == "test_query.py"
    assert result.sessions[1].test_results[1].nodeid == "test_update.py"

    # Test session-level filtering with multiple sessions
    query = Query().for_sut("api")
    result = query.execute(sessions=[session1, session2])
    assert len(result.sessions) == 1
    # ALL tests included in session-level filter
    assert len(result.sessions[0].test_results) == 2
    assert result.sessions[0].test_results[0].nodeid == "test_get.py"
    assert result.sessions[0].test_results[1].nodeid == "test_post.py"

    # Test test-level filtering with no matches
    query = Query().filter_by_test().with_outcome(TestOutcome.SKIPPED).apply()
    result = query.execute(sessions=[session1, session2])
    assert len(result.sessions) == 0


def test_query_invalid_sessions():
    """Test query execution validation.

    Key aspects:
    1. Pattern Validation:
       - field_name parameter is required
       - Field names must be valid test attributes
       - Pattern must be a string

    2. Session Validation:
       - Sessions list cannot be empty
       - Each session must be a TestSession
       - Test results must be properly initialized

    3. Filter Chain:
       - Invalid filter combinations are caught
       - Proper error messages are provided
       - Query state remains consistent
    """
    # Test empty sessions list
    query = Query()
    with pytest.raises(InvalidQueryParameterError, match="No sessions provided"):
        query.execute(sessions=[])

    # Test invalid session type
    with pytest.raises(InvalidQueryParameterError, match="Invalid session type"):
        query.execute(sessions=[{"invalid": "session"}])

    # Test invalid pattern type
    with pytest.raises(TypeError):
        query.filter_by_test().with_pattern(123, field_name="nodeid")

    # Test invalid field name
    with pytest.raises(InvalidQueryParameterError, match="Invalid field name"):
        query.filter_by_test().with_pattern("test", field_name="invalid_field")

    # Test applying test filter without initializing
    with pytest.raises(InvalidQueryParameterError, match="Test filter not initialized"):
        Query().apply()

    # Test double initialization of test filter
    query = Query().filter_by_test()
    with pytest.raises(InvalidQueryParameterError, match="Test filter already initialized"):
        query.filter_by_test()

    # Test invalid sessions parameter
    query = Query()
    with pytest.raises(
        InvalidQueryParameterError, match="Sessions list cannot be empty"
    ):
        query.execute(sessions=[])

    with pytest.raises(InvalidQueryParameterError, match="Invalid session type"):
        query.execute(sessions=[{"invalid": "session"}])

    # Test invalid pattern parameters
    query = Query().filter_by_test()
    with pytest.raises(TypeError, match="missing.*field_name"):
        query.with_pattern("test")

    with pytest.raises(InvalidQueryParameterError, match="Invalid field name"):
        query.with_pattern("test", field_name="invalid_field").apply()

    # Test invalid filter combinations
    query = Query().filter_by_test()
    with pytest.raises(InvalidQueryParameterError, match="Invalid pattern type"):
        query.with_pattern(None, field_name="nodeid")

    # Verify query state remains consistent after errors
    query = Query().filter_by_test()
    try:
        query.with_pattern(None, field_name="nodeid")
    except InvalidQueryParameterError:
        pass

    # Should still be able to add valid filters
    query.with_pattern("test", field_name="nodeid").apply()
    assert len(query.filters) == 1
    assert isinstance(query.filters[0], ShellPatternFilter)


def test_test_level_filtering():
    """Test that test-level filtering properly filters individual tests while preserving session context."""
    session = TestSession(
        sut_name="test-service",
        session_id="test_session",
        session_tags={"env": "prod"},
        session_start_time=get_test_time(),
        session_stop_time=get_test_time(10),
        test_results=[
            TestResult(
                nodeid="test_1",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(),
                duration=1.0,
            ),
            TestResult(
                nodeid="test_2",
                outcome=TestOutcome.FAILED,
                start_time=get_test_time(1),
                duration=5.0,
            ),
            TestResult(
                nodeid="test_3",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(2),
                duration=10.0,
            ),
        ],
    )

    # Single filter - by duration
    query = Query().filter_by_test().with_duration_between(4.0, float("inf")).apply()
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    assert len(result.sessions[0].test_results) == 2
    assert {t.nodeid for t in result.sessions[0].test_results} == {"test_2", "test_3"}
    assert result.sessions[0].session_tags == {"env": "prod"}  # Session context preserved

    # Multiple filters - AND logic
    query = (
        Query()
        .filter_by_test()
        .with_duration_between(4.0, float("inf"))
        .with_outcome(TestOutcome.FAILED)
        .apply()
    )
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    assert len(result.sessions[0].test_results) == 1
    assert result.sessions[0].test_results[0].nodeid == "test_2"
    assert result.sessions[0].session_tags == {"env": "prod"}  # Session context preserved

    # No matches - session should be excluded
    query = Query().filter_by_test().with_duration_between(20.0, float("inf")).apply()
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 0


def test_test_level_filtering_multiple_sessions():
    """Test that test-level filtering works correctly across multiple sessions."""
    session1 = TestSession(
        sut_name="service-1",
        session_id="session1",
        session_tags={"env": "prod"},
        session_start_time=get_test_time(),
        session_stop_time=get_test_time(10),
        test_results=[
            TestResult(
                nodeid="test_1",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(),
                duration=1.0,
            ),
            TestResult(
                nodeid="test_2",
                outcome=TestOutcome.FAILED,
                start_time=get_test_time(1),
                duration=5.0,
            ),
        ],
    )
    session2 = TestSession(
        sut_name="service-2",
        session_id="session2",
        session_tags={"env": "stage"},
        session_start_time=get_test_time(10),
        session_stop_time=get_test_time(20),
        test_results=[
            TestResult(
                nodeid="test_1",
                outcome=TestOutcome.FAILED,
                start_time=get_test_time(10),
                duration=2.0,
            ),
            TestResult(
                nodeid="test_2",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(11),
                duration=3.0,
            ),
        ],
    )

    # Filter should work independently on each session
    query = Query().filter_by_test().with_outcome(TestOutcome.FAILED).apply()
    result = query.execute(sessions=[session1, session2])
    assert len(result.sessions) == 2

    # Session 1 should have only test_2
    assert len(result.sessions[0].test_results) == 1
    assert result.sessions[0].test_results[0].nodeid == "test_2"
    assert result.sessions[0].session_tags == {"env": "prod"}

    # Session 2 should have only test_1
    assert len(result.sessions[1].test_results) == 1
    assert result.sessions[1].test_results[0].nodeid == "test_1"
    assert result.sessions[1].session_tags == {"env": "stage"}


def test_session_vs_test_level_filtering():
    """Test the difference between session-level and test-level filtering.

    Key aspects of the query system's two-level design:
    1. Session-Level: Filter entire test sessions (keeps all tests)
    2. Test-Level: Filter by test properties (keeps matching tests only)
    Both preserve full session context.
    """
    session = TestSession(
        sut_name="api-service",
        session_id="test_session",
        session_tags={"env": "prod", "version": "1.2.3"},
        session_start_time=get_test_time(),
        session_stop_time=get_test_time(3),
        test_results=[
            TestResult(
                nodeid="test_1",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(),
                duration=1.0,
            ),
            TestResult(
                nodeid="test_2",
                outcome=TestOutcome.FAILED,
                start_time=get_test_time(1),
                duration=2.0,
            ),
            TestResult(
                nodeid="test_3",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(2),
                duration=3.0,
            ),
        ],
        rerun_test_groups=[],
    )

    # Session-level filter - should keep ALL tests in matching sessions
    query = Query().with_tag("env", "prod")
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    # ALL tests should be included (session-level filter)
    assert len(result.sessions[0].test_results) == 3
    # Original test order is maintained
    assert result.sessions[0].test_results[0].nodeid == "test_1"
    assert result.sessions[0].test_results[1].nodeid == "test_2"
    assert result.sessions[0].test_results[2].nodeid == "test_3"
    # Session metadata is preserved
    assert result.sessions[0].session_tags == {"env": "prod", "version": "1.2.3"}

    # Test-level filter - should keep ONLY matching tests
    query = Query().filter_by_test().with_outcome(TestOutcome.PASSED).apply()
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    # Only matching tests should be included
    assert len(result.sessions[0].test_results) == 2
    # Original test order is maintained
    assert result.sessions[0].test_results[0].nodeid == "test_1"
    assert result.sessions[0].test_results[1].nodeid == "test_3"
    # Session metadata is preserved
    assert result.sessions[0].session_tags == {"env": "prod", "version": "1.2.3"}

    # Combined filtering - session filtered first, then tests
    query = (
        Query()
        .with_tag("env", "prod")  # Session-level: keeps whole session
        .filter_by_test()
        .with_outcome(TestOutcome.FAILED)  # Test-level: keeps only FAILED tests
        .apply()
    )
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    # Only matching tests should be included
    assert len(result.sessions[0].test_results) == 1
    # Original test order is maintained
    assert result.sessions[0].test_results[0].nodeid == "test_2"
    # Session metadata is preserved
    assert result.sessions[0].session_tags == {"env": "prod", "version": "1.2.3"}

    # Test-level filter with no matches - session should be excluded
    query = Query().filter_by_test().with_outcome(TestOutcome.SKIPPED).apply()
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 0  # No sessions with matching tests


def test_query_duration_filter():
    """Test filtering by test duration.

    Key aspects:
    1. Duration Filtering:
       - Test-level filter using duration bounds
       - Creates new sessions with only matching tests
       - Maintains original order of matching tests

    2. Context Preservation:
       - Session metadata preserved
       - Test relationships maintained within matching tests
       - Never returns isolated TestResult objects
    """
    session = TestSession(
        sut_name="api-service",
        session_id="test_session",
        session_start_time=get_test_time(),
        session_stop_time=get_test_time(10),
        test_results=[
            TestResult(
                nodeid="test_1",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(),
                duration=1.0,
                caplog="Test 1",
                capstdout="",
                capstderr="",
                longreprtext="",
            ),
            TestResult(
                nodeid="test_2",
                outcome=TestOutcome.FAILED,
                start_time=get_test_time(1),
                duration=5.0,
                caplog="Test 2",
                capstdout="",
                capstderr="",
                longreprtext="",
            ),
            TestResult(
                nodeid="test_3",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(2),
                duration=10.0,
                caplog="Test 3",
                capstdout="",
                capstderr="",
                longreprtext="",
            ),
        ],
        session_tags={"env": "prod"},
        rerun_test_groups=[],
    )

    # Test duration range filtering
    query = Query().filter_by_test().with_duration_between(4.0, float("inf")).apply()
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    # Only matching tests included in new session
    assert len(result.sessions[0].test_results) == 2
    # All included tests match the duration filter
    assert all(t.duration >= 4.0 for t in result.sessions[0].test_results)
    # Original order maintained within matching tests
    assert result.sessions[0].test_results[0].nodeid == "test_2"
    assert result.sessions[0].test_results[1].nodeid == "test_3"
    # Session metadata preserved
    assert result.sessions[0].session_tags == {"env": "prod"}

    # Multiple filters - AND logic
    query = (
        Query()
        .filter_by_test()
        .with_duration_between(4.0, float("inf"))
        .with_outcome(TestOutcome.FAILED)
        .apply()
    )
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    # Only tests matching BOTH filters included
    assert len(result.sessions[0].test_results) == 1
    # Test matches both duration and outcome filters
    assert result.sessions[0].test_results[0].duration >= 4.0
    assert result.sessions[0].test_results[0].outcome == TestOutcome.FAILED
    # Original test order maintained
    assert result.sessions[0].test_results[0].nodeid == "test_2"
    # Session metadata preserved
    assert result.sessions[0].session_tags == {"env": "prod"}

    # No matches - session should be excluded
    query = Query().filter_by_test().with_duration_between(20.0, float("inf")).apply()
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 0


def test_query_outcome_filter():
    """Test filtering by test outcome."""
    session1 = TestSession(
        sut_name="api-service",
        session_id="session1",
        session_start_time=get_test_time(),
        session_stop_time=get_test_time(2),
        test_results=[
            TestResult(
                nodeid="test_1",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(),
                duration=1.0,
                caplog="Test 1",
                capstdout="",
                capstderr="",
                longreprtext="",
            ),
            TestResult(
                nodeid="test_2",
                outcome=TestOutcome.FAILED,
                start_time=get_test_time(1),
                duration=1.0,
                caplog="Test 2",
                capstdout="",
                capstderr="",
                longreprtext="",
            ),
        ],
        session_tags={"env": "prod"},
        rerun_test_groups=[],
    )

    session2 = TestSession(
        sut_name="db-service",
        session_id="session2",
        session_start_time=get_test_time(),
        session_stop_time=get_test_time(2),
        test_results=[
            TestResult(
                nodeid="test_1",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(),
                duration=1.0,
                caplog="Test 1",
                capstdout="",
                capstderr="",
                longreprtext="",
            ),
            TestResult(
                nodeid="test_2",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(1),
                duration=1.0,
                caplog="Test 2",
                capstdout="",
                capstderr="",
                longreprtext="",
            ),
        ],
        session_tags={"env": "stage"},
        rerun_test_groups=[],
    )

    # Test outcome filtering - single session
    query = Query().filter_by_test().with_outcome(TestOutcome.FAILED).apply()
    result = query.execute(sessions=[session1])
    assert len(result.sessions) == 1
    # Only matching tests should be included
    assert len(result.sessions[0].test_results) == 1
    # Original test order is maintained
    assert result.sessions[0].test_results[0].nodeid == "test_2"
    # Session metadata is preserved
    assert result.sessions[0].session_tags == {"env": "prod"}

    # Test outcome filtering - multiple sessions
    query = Query().filter_by_test().with_outcome(TestOutcome.PASSED).apply()
    result = query.execute(sessions=[session1, session2])
    assert len(result.sessions) == 2
    # Only matching tests should be included in each session
    assert len(result.sessions[0].test_results) == 1
    assert len(result.sessions[1].test_results) == 2
    # Original test order is maintained in each session
    assert result.sessions[0].test_results[0].nodeid == "test_1"
    assert result.sessions[1].test_results[0].nodeid == "test_1"
    assert result.sessions[1].test_results[1].nodeid == "test_2"
    # Session metadata is preserved
    assert result.sessions[0].session_tags == {"env": "prod"}
    assert result.sessions[1].session_tags == {"env": "stage"}

    # Test outcome filtering - no matches
    query = Query().filter_by_test().with_outcome(TestOutcome.SKIPPED).apply()
    result = query.execute(sessions=[session1, session2])
    assert len(result.sessions) == 0


def test_query_combined_filters():
    """Test combining session-level and test-level filters.

    Key aspects:
    1. Session-Level Filters:
       - Filter entire sessions (SUT, time range, warnings)
       - Keep ALL tests in matching sessions
       - No test-level criteria applied

    2. Test-Level Filters:
       - Filter by test properties (duration, outcome, pattern)
       - Keep ONLY matching tests in matching sessions
       - Preserve session metadata

    3. Combined Filtering:
       - Session filters applied first
       - Test filters applied to remaining sessions
       - Session context always preserved
    """
    session = TestSession(
        sut_name="api-service",
        session_id="test_session",
        session_start_time=get_test_time(),
        session_stop_time=get_test_time(3),
        test_results=[
            TestResult(
                nodeid="test_1",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(),
                duration=1.0,
                caplog="Test 1",
                capstdout="",
                capstderr="",
                longreprtext="",
            ),
            TestResult(
                nodeid="test_2",
                outcome=TestOutcome.FAILED,
                start_time=get_test_time(1),
                duration=2.0,
                caplog="Test 2",
                capstdout="",
                capstderr="",
                longreprtext="",
            ),
            TestResult(
                nodeid="test_3",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(2),
                duration=3.0,
                caplog="Test 3",
                capstdout="",
                capstderr="",
                longreprtext="",
            ),
        ],
        session_tags={"env": "prod", "version": "1.2.3"},
        rerun_test_groups=[],
    )

    # Session-level filter only - keep ALL tests
    query = Query().with_tag("env", "prod")
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    # ALL tests should be included (session-level filter)
    assert len(result.sessions[0].test_results) == 3
    # Original test order is maintained
    assert result.sessions[0].test_results[0].nodeid == "test_1"
    assert result.sessions[0].test_results[1].nodeid == "test_2"
    assert result.sessions[0].test_results[2].nodeid == "test_3"
    # Session metadata is preserved
    assert result.sessions[0].session_tags == {"env": "prod", "version": "1.2.3"}

    # Test-level filter only - keep ONLY matching tests
    query = Query().filter_by_test().with_outcome(TestOutcome.PASSED).apply()
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    # Only matching tests should be included
    assert len(result.sessions[0].test_results) == 2
    # Original test order is maintained
    assert result.sessions[0].test_results[0].nodeid == "test_1"
    assert result.sessions[0].test_results[1].nodeid == "test_3"
    # Session metadata is preserved
    assert result.sessions[0].session_tags == {"env": "prod", "version": "1.2.3"}

    # Combined filtering - session filtered first, then tests
    query = (
        Query()
        .with_tag("env", "prod")
        .filter_by_test()
        .with_outcome(TestOutcome.FAILED)
        .apply()
    )
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    # Only matching tests should be included
    assert len(result.sessions[0].test_results) == 1
    # Original test order is maintained
    assert result.sessions[0].test_results[0].nodeid == "test_2"
    # Session metadata is preserved
    assert result.sessions[0].session_tags == {"env": "prod", "version": "1.2.3"}

    # Test-level filter with no matches - session should be excluded
    query = Query().filter_by_test().with_outcome(TestOutcome.SKIPPED).apply()
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 0


def test_query_pattern_filter():
    """Test pattern matching filters.

    Key aspects:
    1. Pattern Types:
       - Shell pattern (simple substring)
       - Regex pattern (complex matching)
       - Field-specific patterns (nodeid, caplog, etc.)

    2. Test-Level Filtering:
       - Keep ONLY matching tests in matching sessions
       - Preserve session metadata and order
       - Multiple patterns use AND logic
    """
    session = TestSession(
        sut_name="api-service",
        session_id="test_session",
        session_start_time=get_test_time(),
        session_stop_time=get_test_time(2),
        test_results=[
            TestResult(
                nodeid="test_api.py::test_get",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(),
                duration=1.0,
                caplog="API request successful",
                capstdout="GET /api/v1/test",
                capstderr="",
                longreprtext="",
            ),
            TestResult(
                nodeid="test_core.py::test_error",
                outcome=TestOutcome.FAILED,
                start_time=get_test_time(1),
                duration=1.0,
                caplog="Error in core module",
                capstdout="",
                capstderr="AssertionError",
                longreprtext="AssertionError",
            ),
        ],
        session_tags={"type": "api", "component": "test"},
        rerun_test_groups=[],
    )

    # Test nodeid pattern matching
    query = Query().filter_by_test().with_nodeid_containing("test_api").apply()
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    # Only matching tests should be included
    assert len(result.sessions[0].test_results) == 1
    # Original test order is maintained
    assert result.sessions[0].test_results[0].nodeid == "test_api.py::test_get"
    # Session metadata is preserved
    assert result.sessions[0].session_tags == {"type": "api", "component": "test"}

    # Test log pattern matching
    query = Query().filter_by_test().with_log_containing("Error").apply()
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    # Only matching tests should be included
    assert len(result.sessions[0].test_results) == 1
    # Original test order is maintained
    assert result.sessions[0].test_results[0].nodeid == "test_core.py::test_error"
    # Session metadata is preserved
    assert result.sessions[0].session_tags == {"type": "api", "component": "test"}

    # Test error pattern matching
    query = Query().filter_by_test().with_error_containing("AssertionError").apply()
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    # Only matching tests should be included
    assert len(result.sessions[0].test_results) == 1
    # Original test order is maintained
    assert result.sessions[0].test_results[0].nodeid == "test_core.py::test_error"
    # Session metadata is preserved
    assert result.sessions[0].session_tags == {"type": "api", "component": "test"}

    # Test multiple pattern matching (AND logic)
    query = (
        Query()
        .filter_by_test()
        .with_pattern("API", field_name="caplog")
        .with_pattern("GET", field_name="capstdout")
        .apply()
    )
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    # Only matching tests should be included
    assert len(result.sessions[0].test_results) == 1
    # Original test order is maintained
    assert result.sessions[0].test_results[0].nodeid == "test_api.py::test_get"
    # Session metadata is preserved
    assert result.sessions[0].session_tags == {"type": "api", "component": "test"}
