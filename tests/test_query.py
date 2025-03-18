import pytest
from datetime import datetime, timedelta, timezone
from pytest_insight.models import TestOutcome, TestResult, TestSession
from pytest_insight.query import (
    GlobPatternFilter,
    RegexPatternFilter,
    ShellPatternFilter,
    InvalidQueryParameterError,
    Query,
    DurationFilter,  # Import DurationFilter
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
    if should_raise:
        with pytest.raises(InvalidQueryParameterError, match="Invalid field name"):
            ShellPatternFilter(pattern=pattern, field_name=field_name)
    else:
        ShellPatternFilter(pattern=pattern, field_name=field_name)


@pytest.mark.parametrize(
    "nodeid, pattern, should_match",
    [
        ("test_api.py::test_get", "api", True),
        ("test_api.py::test_api_post", "test_api.py::test", True),
        ("test_core.py::test_api_get", "core.*api", False),
        ("test_API.py::test_get", "api", False),
    ],
)
def test_shell_pattern_matching(nodeid, pattern, should_match):
    test = TestResult(nodeid=nodeid, outcome=TestOutcome.PASSED, start_time=get_test_time(), duration=1.0)
    filter = ShellPatternFilter(pattern=pattern)
    assert filter.matches(test) == should_match


@pytest.mark.parametrize(
    "pattern, field_name, nodeid, should_match",
    [
        (r"test_\d+", "nodeid", "test_123", True),
        (r"test_\d+", "nodeid", "test_abc", False),
        (r"test_[a-z]+", "nodeid", "test_abc", True),
        (r"test_[a-z]+", "nodeid", "test_123", False),
    ],
)
def test_regex_pattern_matching(pattern, field_name, nodeid, should_match):
    test = TestResult(nodeid=nodeid, outcome=TestOutcome.PASSED, start_time=get_test_time(), duration=1.0)
    filter = RegexPatternFilter(pattern=pattern, field_name=field_name)
    assert filter.matches(test) == should_match


@pytest.mark.parametrize(
    "pattern, should_match",
    [
        ("test_get", True),
        ("test_api", True),
        ("core.*api", False),
        ("TEST_API", False),
    ],
)
def test_glob_pattern_matching(pattern, should_match):
    test = TestResult(nodeid="test_api.py::test_get", outcome=TestOutcome.PASSED, start_time=get_test_time(), duration=1.0)
    filter = GlobPatternFilter(pattern=pattern)
    assert filter.matches(test) == should_match


@pytest.mark.parametrize(
    "min_seconds, max_seconds, duration, should_match",
    [
        (1.0, 5.0, 3.0, True),   # Within range
        (1.0, 5.0, 0.5, False),  # Below range
        (1.0, 5.0, 5.0, True),   # At upper bound
        (1.0, 5.0, 6.0, False),  # Above range
    ],
)
def test_duration_filter(min_seconds, max_seconds, duration, should_match):
    """Test filtering tests by duration range."""
    test = TestResult(
        nodeid="test_case",
        outcome=TestOutcome.PASSED,
        start_time=get_test_time(),
        duration=duration
    )
    filter = DurationFilter(min_seconds=min_seconds, max_seconds=max_seconds)
    assert filter.matches(test) == should_match


def test_query_execution():
    session = TestSession(
        sut_name="api-service",
        session_id="test-1",
        session_start_time=get_test_time(),
        session_stop_time=get_test_time(3),
        test_results=[
            TestResult(nodeid="test_api.py::test_get", outcome=TestOutcome.PASSED, start_time=get_test_time(), duration=1.0),
            TestResult(nodeid="test_api.py::test_post", outcome=TestOutcome.PASSED, start_time=get_test_time(1), duration=1.0),
            TestResult(nodeid="test_db.py::test_connect", outcome=TestOutcome.PASSED, start_time=get_test_time(2), duration=1.0),
        ],
    )

    query = Query().filter_by_test().with_pattern("test_api").apply()
    result = query.execute(sessions=[session])

    assert len(result.sessions) == 1
    assert len(result.sessions[0].test_results) == 2
    assert any("test_get" in t.nodeid for t in result.sessions[0].test_results)
