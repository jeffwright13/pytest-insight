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


@pytest.mark.parametrize(
    "pattern, field_name, should_raise",
    [
        ("test", "nodeid", False),
        ("error", "caplog", False),
        ("output", "capstdout", False),
        ("test", "invalid", True),
    ],
)
def test_field_validation(pattern, field_name, should_raise):
    """Test field name validation in pattern filters.

    Key aspects:
    1. Field names must be valid test result attributes
    2. Common fields: nodeid, caplog, capstdout, capstderr, longreprtext
    3. Invalid fields raise InvalidQueryParameterError
    """
    if should_raise:
        with pytest.raises(InvalidQueryParameterError, match="Invalid field name"):
            ShellPatternFilter(pattern=pattern, field_name=field_name)
    else:
        ShellPatternFilter(pattern=pattern, field_name=field_name)


@pytest.mark.parametrize(
    "field_value, pattern, should_match",
    [
        # Simple substring matches
        ("test_api.py::test_get", "test_api", True),
        ("test_api.py::test_get", "test_get", True),
        ("test_api.py::test_get", "api.py", True),
        ("test_core.py::test_get", "api", False),
        # Case sensitivity
        ("test_API.py::test_get", "api", False),
        ("test_api.py::TEST_get", "test_get", False),
        # Other fields
        ("Error in test_api", "Error", True),
        ("Warning: test failed", "warning", False),
    ],
)
def test_shell_pattern_matching(field_value, pattern, should_match):
    """Test shell pattern matching behavior.

    Key aspects:
    1. Pattern Matching:
       - Simple substring matching (no glob patterns)
       - Case-sensitive comparison
       - field_name parameter is required
       - No special handling for any fields

    2. Test Context:
       - Matches are performed on individual test fields
       - Each field type (nodeid, caplog, etc.) is tested separately
       - Test result objects maintain all required fields
    """
    # Create base test result with required fields
    base_test = TestResult(
        nodeid="test_example.py::test_func",
        outcome=TestOutcome.PASSED,
        start_time=get_test_time(),
        duration=1.0,
        caplog="",
        capstderr="",
        capstdout="",
        longreprtext="",
    )

    # Test each field type
    for field_name in ["nodeid", "caplog", "longreprtext"]:
        # Create test result with field value
        test_dict = base_test.__dict__.copy()
        test_dict[field_name] = field_value
        test = TestResult(**test_dict)

        # Test that field_name is required
        with pytest.raises(TypeError):
            ShellPatternFilter(pattern=pattern)

        # Test with explicit field_name
        filter = ShellPatternFilter(pattern=pattern, field_name=field_name)
        assert filter.matches(test) == should_match, f"Failed for field: {field_name}"


@pytest.mark.parametrize(
    "pattern, field_name, value, should_match",
    [
        # Basic regex
        (r"test_\d+", "nodeid", "test_123", True),
        (r"test_\d+", "nodeid", "test_abc", False),
        # Case insensitive
        (r"(?i)error", "longreprtext", "ERROR: failed", True),
        (r"(?i)warning", "caplog", "Warning: test failed", True),
        # Complex patterns
        (r"test_[a-z]+\.py::test_\w+", "nodeid", "test_api.py::test_get", True),
        (r"\[(\d{2}:){2}\d{2}\]", "caplog", "[14:35:22] Warning", True),
    ],
)
def test_regex_pattern_matching(pattern, field_name, value, should_match):
    """Test regex pattern matching behavior.

    Key aspects:
    1. Pattern Matching:
       - Full regex pattern support
       - Case sensitivity controlled by regex flags
       - field_name parameter is required
       - No special handling for any fields

    2. Test Context:
       - Matches are performed on individual test fields
       - Complex patterns can match structured data
       - Test result objects maintain all required fields
    """
    # Create base test result with required fields
    base_test = TestResult(
        nodeid="test_example.py::test_func",
        outcome=TestOutcome.PASSED,
        start_time=get_test_time(),
        duration=1.0,
        caplog="",
        capstderr="",
        capstdout="",
        longreprtext="",
    )

    # Set the field value for testing
    test_dict = base_test.__dict__.copy()
    test_dict[field_name] = value
    test = TestResult(**test_dict)

    filter = RegexPatternFilter(pattern=pattern, field_name=field_name)
    assert filter.matches(test) == should_match


@pytest.mark.parametrize(
    "min_seconds, max_seconds, duration, should_match",
    [
        (1.0, 5.0, 3.0, True),  # Within range
        (1.0, 5.0, 0.5, False),  # Below range
        (1.0, 5.0, 5.0, True),  # At upper bound
        (1.0, 5.0, 6.0, False),  # Above range
    ],
)
def test_duration_filter(min_seconds, max_seconds, duration, should_match):
    """Test filtering tests by duration range."""
    test = TestResult(
        nodeid="test_case",
        outcome=TestOutcome.PASSED,
        start_time=get_test_time(),
        duration=duration,
    )
    filter = DurationFilter(min_seconds=min_seconds, max_seconds=max_seconds)
    assert filter.matches(test) == should_match


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
       - Session-level filters (SUT, time range)
       - Test-level filters (pattern, outcome)
       - Returns full TestSession objects

    3. Context Preservation:
       - Sessions containing ANY matching test are included
       - ALL tests in matching sessions are preserved
       - Session metadata (tags, IDs) is maintained
       - Test relationships are preserved
    """
    session = TestSession(
        sut_name="api-service",
        session_id="test_session",
        session_start_time=get_test_time(),
        session_duration=10.0,
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
                start_time=get_test_time(),
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
    # Both tests should be included (session context preserved)
    assert len(result.sessions[0].test_results) == 2
    # Original test order is maintained
    assert result.sessions[0].test_results[0].nodeid == "test_api.py::test_get"
    assert result.sessions[0].test_results[1].nodeid == "test_core.py::test_error"
    # Session metadata is preserved
    assert result.sessions[0].session_tags == {"type": "api", "component": "test"}

    # Test output pattern matching
    query = Query().filter_by_test().with_log_containing("Error").apply()
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    # Both tests should be included (session context preserved)
    assert len(result.sessions[0].test_results) == 2
    # Original test order is maintained
    assert result.sessions[0].test_results[0].nodeid == "test_api.py::test_get"
    assert result.sessions[0].test_results[1].nodeid == "test_core.py::test_error"

    # Test error pattern matching
    query = Query().filter_by_test().with_error_containing("AssertionError").apply()
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    # Both tests should be included (session context preserved)
    assert len(result.sessions[0].test_results) == 2
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
    # Both tests should be included (session context preserved)
    assert len(result.sessions[0].test_results) == 2
    # Original test order is maintained
    assert result.sessions[0].test_results[0].nodeid == "test_api.py::test_get"
    assert result.sessions[0].test_results[1].nodeid == "test_core.py::test_error"


def test_query_order_preservation():
    """Test that query execution preserves test order and session context."""
    session = TestSession(
        sut_name="api-service",
        session_id="test_session",
        session_start_time=get_test_time(),
        session_duration=10.0,
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
    assert len(result.sessions[0].test_results) == 1
    assert result.sessions[0].test_results[0].nodeid == "test_2.py::test_second"
    assert result.sessions[0].session_tags == {"a": "1", "b": "2", "c": "3"}
    assert result.sessions[0].rerun_test_groups == session.rerun_test_groups

    # Verify session context is preserved
    filtered_session = result.sessions[0]
    assert filtered_session.sut_name == session.sut_name
    assert filtered_session.session_id == session.session_id
    assert filtered_session.session_start_time == session.session_start_time
    assert filtered_session.session_tags == {"a": "1", "b": "2", "c": "3"}
    assert filtered_session.rerun_test_groups == session.rerun_test_groups

    # Verify test order matches original for matching tests
    assert filtered_session.test_results[0].nodeid == "test_2.py::test_second"

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
    nodeids = [t.nodeid for t in result.sessions[0].test_results]
    assert nodeids == ["test_1.py::test_first", "test_3.py::test_third"]

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
    nodeids1 = [t.nodeid for t in result1.sessions[0].test_results]
    nodeids2 = [t.nodeid for t in result2.sessions[0].test_results]
    assert nodeids1 == nodeids2


def test_query_filtered_sessions():
    """Test query execution with filtered sessions.

    Key aspects:
    1. Two-Level Filtering:
       - Session-level filters (SUT, time range)
       - Test-level filters (pattern, outcome)
       - Returns full TestSession objects

    2. Context Preservation:
       - Sessions containing ANY matching test are included
       - ALL tests in matching sessions are preserved
       - Session metadata (tags, IDs) is maintained
       - Test relationships are preserved

    3. Pattern Matching:
       - Simple substring matching on specified fields
       - Case-sensitive comparison
       - field_name parameter is required
       - No special handling for any fields
    """
    session1 = TestSession(
        sut_name="api-service",
        session_id="session1",
        session_start_time=get_test_time(),
        session_duration=10.0,
        test_results=[
            TestResult(
                nodeid="test_api.py::test_get",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(),
                duration=1.0,
                caplog="API test",
                capstdout="API stdout",
                capstderr="",
                longreprtext="",
            ),
            TestResult(
                nodeid="test_api.py::test_post",
                outcome=TestOutcome.FAILED,
                start_time=get_test_time(1),
                duration=2.0,
                caplog="API error",
                capstdout="",
                capstderr="API failure",
                longreprtext="AssertionError",
            ),
        ],
        session_tags={"type": "api", "version": "v1"},
        rerun_test_groups=[],
    )

    session2 = TestSession(
        sut_name="db-service",
        session_id="session2",
        session_start_time=get_test_time(),
        session_duration=5.0,
        test_results=[
            TestResult(
                nodeid="test_db.py::test_query",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(),
                duration=1.0,
                caplog="DB test",
                capstdout="DB stdout",
                capstderr="",
                longreprtext="",
            ),
        ],
        session_tags={"type": "db", "version": "v1"},
        rerun_test_groups=[],
    )

    # Test pattern matching with filtered sessions
    query = Query().filter_by_test().with_pattern("API", field_name="caplog").apply()
    result = query.execute(sessions=[session1, session2])
    assert len(result.sessions) == 1
    # Both tests in session1 should be included (session context preserved)
    assert len(result.sessions[0].test_results) == 2
    # Original test order is maintained
    assert result.sessions[0].test_results[0].nodeid == "test_api.py::test_get"
    assert result.sessions[0].test_results[1].nodeid == "test_api.py::test_post"
    # Session metadata is preserved
    assert result.sessions[0].session_tags == {"type": "api", "version": "v1"}

    # Test pattern matching with multiple sessions
    query = Query().filter_by_test().with_pattern("test", field_name="caplog").apply()
    result = query.execute(sessions=[session1, session2])
    assert len(result.sessions) == 2
    # All tests in both sessions should be included (session context preserved)
    assert len(result.sessions[0].test_results) == 2
    assert len(result.sessions[1].test_results) == 1
    # Original test order is maintained in each session
    assert result.sessions[0].test_results[0].nodeid == "test_api.py::test_get"
    assert result.sessions[0].test_results[1].nodeid == "test_api.py::test_post"
    assert result.sessions[1].test_results[0].nodeid == "test_db.py::test_query"
    # Session metadata is preserved for both sessions
    assert result.sessions[0].session_tags == {"type": "api", "version": "v1"}
    assert result.sessions[1].session_tags == {"type": "db", "version": "v1"}

    # Test pattern matching with multiple fields
    query = (
        Query()
        .filter_by_test()
        .with_pattern("DB", field_name="caplog")
        .with_pattern("stdout", field_name="capstdout")
        .apply()
    )
    result = query.execute(sessions=[session1, session2])
    assert len(result.sessions) == 1
    # All tests in session2 should be included (session context preserved)
    assert len(result.sessions[0].test_results) == 1
    # Original test order is maintained
    assert result.sessions[0].test_results[0].nodeid == "test_db.py::test_query"
    # Session metadata is preserved
    assert result.sessions[0].session_tags == {"type": "db", "version": "v1"}

    # Test session tag filtering
    query = Query().with_tag("type", "api")
    result = query.execute(sessions=[session1, session2])
    assert len(result.sessions) == 1
    assert result.sessions[0].session_id == session1.session_id

    # Test session tag filtering with multiple sessions
    query = Query().with_tag("version", "v1")
    result = query.execute(sessions=[session1, session2])
    assert len(result.sessions) == 2
    assert result.sessions[0].session_id == session1.session_id
    assert result.sessions[1].session_id == session2.session_id

    # Test session tag filtering with no matches
    query = Query().with_tag("type", "unknown")
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
        session_tags={"env": "prod"},
        test_results=[
            TestResult(nodeid="test_1", outcome=TestOutcome.PASSED, duration=1.0),
            TestResult(nodeid="test_2", outcome=TestOutcome.FAILED, duration=5.0),
            TestResult(nodeid="test_3", outcome=TestOutcome.PASSED, duration=10.0),
        ]
    )

    # Single filter - by duration
    query = Query().filter_by_test().with_duration(4.0, float("inf")).apply()
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    assert len(result.sessions[0].test_results) == 2
    assert {t.nodeid for t in result.sessions[0].test_results} == {"test_2", "test_3"}
    assert result.sessions[0].session_tags == {"env": "prod"}  # Session context preserved

    # Multiple filters - AND logic
    query = Query().filter_by_test().with_duration(4.0, float("inf")).with_outcome(TestOutcome.FAILED).apply()
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    assert len(result.sessions[0].test_results) == 1
    assert result.sessions[0].test_results[0].nodeid == "test_2"
    assert result.sessions[0].session_tags == {"env": "prod"}  # Session context preserved

    # No matches - session should be excluded
    query = Query().filter_by_test().with_duration(20.0, float("inf")).apply()
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 0


def test_test_level_filtering_multiple_sessions():
    """Test that test-level filtering works correctly across multiple sessions."""
    session1 = TestSession(
        sut_name="service-1",
        session_tags={"env": "prod"},
        test_results=[
            TestResult(nodeid="test_1", outcome=TestOutcome.PASSED, duration=1.0),
            TestResult(nodeid="test_2", outcome=TestOutcome.FAILED, duration=5.0),
        ]
    )
    session2 = TestSession(
        sut_name="service-2",
        session_tags={"env": "stage"},
        test_results=[
            TestResult(nodeid="test_1", outcome=TestOutcome.FAILED, duration=2.0),
            TestResult(nodeid="test_2", outcome=TestOutcome.PASSED, duration=3.0),
        ]
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
        session_tags={"env": "prod", "version": "1.2.3"},
        test_results=[
            TestResult(nodeid="test_1", outcome=TestOutcome.PASSED, duration=1.0),
            TestResult(nodeid="test_2", outcome=TestOutcome.FAILED, duration=2.0),
            TestResult(nodeid="test_3", outcome=TestOutcome.PASSED, duration=3.0),
        ]
    )

    # Session-level filter - should keep ALL tests in matching sessions
    query = Query().with_tag("env", "prod")
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    assert len(result.sessions[0].test_results) == 3  # All tests kept
    assert result.sessions[0].session_tags == {"env": "prod", "version": "1.2.3"}

    # Test-level filter - should keep ONLY matching tests
    query = Query().filter_by_test().with_outcome(TestOutcome.PASSED).apply()
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    assert len(result.sessions[0].test_results) == 2  # Only PASSED tests
    assert {t.nodeid for t in result.sessions[0].test_results} == {"test_1", "test_3"}
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
    assert len(result.sessions[0].test_results) == 1  # Only FAILED tests
    assert result.sessions[0].test_results[0].nodeid == "test_2"
    assert result.sessions[0].session_tags == {"env": "prod", "version": "1.2.3"}
