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
        session_tags={"api", "test"},
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
    assert result.sessions[0].session_tags == {"api", "test"}

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
    assert result.sessions[0].session_tags == {"api", "test"}

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
        session_tags={"tag1", "tag2"},
        rerun_test_groups=[],
    )

    # Test that order is preserved when filtering by pattern
    query = Query().filter_by_test().with_pattern("Second", field_name="caplog").apply()
    result = query.execute(sessions=[session])
    assert len(result.sessions) == 1
    assert len(result.sessions[0].test_results) == 1

    # Verify session context is preserved
    filtered_session = result.sessions[0]
    assert filtered_session.sut_name == session.sut_name
    assert filtered_session.session_id == session.session_id
    assert filtered_session.session_start_time == session.session_start_time
    assert filtered_session.session_tags == session.session_tags
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
        session_tags={"api", "v1"},
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
        session_tags={"db", "v1"},
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
    assert result.sessions[0].session_tags == {"api", "v1"}

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
    assert result.sessions[0].session_tags == {"api", "v1"}
    assert result.sessions[1].session_tags == {"db", "v1"}

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
    assert result.sessions[0].session_tags == {"db", "v1"}


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
