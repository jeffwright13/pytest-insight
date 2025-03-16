import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import pytest
from pytest_insight.models import TestOutcome, TestResult, TestSession
from pytest_insight.query import (
    GlobPatternFilter,
    InvalidQueryParameterError,
    Query,
    QueryTestFilter,
    RegexPatternFilter,
)


def get_test_time(offset_seconds: int = 0) -> datetime:
    """Get a test timestamp with optional offset.

    Returns:
        A UTC datetime starting from 2023-01-01 plus the given offset in seconds.
        This provides consistent timestamps for test cases while avoiding any
        timezone issues.
    """
    base = datetime(2023, 1, 1, tzinfo=timezone.utc)
    return base + timedelta(seconds=offset_seconds)


class Test_PatternMatching:
    """Test suite for pattern matching behavior.

    Pattern matching rules:
    1. For non-regex patterns:
       - Pattern is wrapped with wildcards: *{pattern}*
       - Pattern is matched against full field value
       - Simple glob pattern matching

    2. For regex patterns:
       - Pattern is used as-is (no wildcards)
       - Pattern is matched against full field value
       - Full regex syntax support
    """

    def test_pattern_rules_examples(self, get_test_time):
        """Test pattern matching rules with examples."""
        test_cases = [
            # Basic glob patterns
            {
                "nodeid": "test_api.py::test_get",
                "pattern": "api",
                "should_match": True,
                "message": "*api* should match anywhere in nodeid",
            },
            {
                "nodeid": "test_api.py::test_api_post",
                "pattern": "test_api.py::test",
                "should_match": True,
                "message": "Pattern should match exact prefix",
            },
            {
                "nodeid": "test_core.py::test_api_get",
                "pattern": "core.*api",
                "should_match": False,
                "message": "Glob patterns are not regex patterns",
            },
            # Test case sensitivity
            {
                "nodeid": "test_API.py::test_get",
                "pattern": "api",
                "should_match": False,
                "message": "Glob patterns are case sensitive",
            },
        ]

        for case in test_cases:
            test = TestResult(
                nodeid=case["nodeid"],
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(),
                duration=1.0,
            )
            filter = GlobPatternFilter(pattern=case["pattern"])
            assert filter.matches(test) == case["should_match"], case["message"]

    def test_regex_pattern_rules(self, get_test_time):
        """Test regex pattern matching rules."""
        test_cases = [
            # Basic regex
            {
                "nodeid": "test_api.py::test_get",
                "pattern": r"test_\w+\.py",
                "should_match": True,
                "message": "Basic regex pattern should match",
            },
            # Case sensitivity
            {
                "nodeid": "test_API.py::test_get",
                "pattern": r"test_api",
                "should_match": False,
                "message": "Regex patterns are case sensitive by default",
            },
            {
                "nodeid": "test_API.py::test_get",
                "pattern": r"(?i)test_api",
                "should_match": True,
                "message": "Case insensitive flag should work",
            },
            # Boundaries and groups
            {
                "nodeid": "test_api.py::test_get",
                "pattern": r"^test_.*::test_\w+$",
                "should_match": True,
                "message": "Regex anchors and wildcards should work",
            },
        ]

        for case in test_cases:
            test = TestResult(
                nodeid=case["nodeid"],
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(),
                duration=1.0,
            )
            filter = RegexPatternFilter(pattern=case["pattern"])
            assert filter.matches(test) == case["should_match"], case["message"]

    def test_string_field_matching(self, get_test_time):
        """Test pattern matching against other string fields."""
        test = TestResult(
            nodeid="test_api.py::test_get",
            outcome=TestOutcome.FAILED,
            start_time=get_test_time(),
            duration=1.0,
            caplog="DEBUG: API request started\nINFO: Processing data",
            capstderr="Warning: Resource usage high",
            capstdout="Response received: 200 OK",
            longreprtext="AssertionError: Expected status 201, got 400",
        )

        # Non-regex patterns (glob)
        test_cases = [
            # Match in caplog
            {
                "field_name": "caplog",
                "pattern": "API request",
                "should_match": True,
            },
            # Match in capstderr
            {
                "field_name": "capstderr",
                "pattern": "Resource",
                "should_match": True,
            },
            # Match in capstdout
            {
                "field_name": "capstdout",
                "pattern": "200 OK",
                "should_match": True,
            },
            # Match in longreprtext
            {
                "field_name": "longreprtext",
                "pattern": "status 201",
                "should_match": True,
            },
        ]

        for case in test_cases:
            filter = GlobPatternFilter(
                pattern=case["pattern"], field_name=case["field_name"]
            )
            assert filter.matches(test) == case["should_match"]

        # Regex patterns
        test_cases = [
            # Match in caplog with line boundary
            {
                "field_name": "caplog",
                "pattern": r"^DEBUG:",
                "should_match": True,
            },
            # Match in capstderr with word boundary
            {
                "field_name": "capstderr",
                "pattern": r"\bResource\b",
                "should_match": True,
            },
            # Match in capstdout with number
            {
                "field_name": "capstdout",
                "pattern": r"\d{3}",
                "should_match": True,
            },
            # Match in longreprtext with capture group
            {
                "field_name": "longreprtext",
                "pattern": r"status (\d+), got \d+",
                "should_match": True,
            },
        ]

        for case in test_cases:
            filter = RegexPatternFilter(
                pattern=case["pattern"], field_name=case["field_name"]
            )
            assert filter.matches(test) == case["should_match"]

    def test_field_validation(self):
        """Test field name validation."""
        # Valid fields
        GlobPatternFilter(pattern="test", field_name="nodeid")
        GlobPatternFilter(pattern="error", field_name="caplog")
        GlobPatternFilter(pattern="warning", field_name="capstderr")
        GlobPatternFilter(pattern="output", field_name="capstdout")
        GlobPatternFilter(pattern="error", field_name="longreprtext")

        # Invalid field
        with pytest.raises(InvalidQueryParameterError) as exc:
            GlobPatternFilter(pattern="test", field_name="invalid")
        assert "Invalid field" in str(exc.value)

    def test_pattern_hierarchy(self, get_test_time):
        """Test pattern hierarchy from broad to specific.

        Pattern hierarchy (from broad to specific):
        - Module patterns (e.g., "test_api.py")
        - Test name patterns (e.g., "test_get")
        - Full path patterns (e.g., "test_api.py::test_get")
        - Full path patterns w/ class (e.g., "test_api.py::TestApi::test_get")
        """
        # Create test session with related tests
        session = TestSession(
            sut_name="api-service",
            session_id="test-1",
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
                    outcome=TestOutcome.PASSED,
                    start_time=get_test_time(1),
                    duration=1.0,
                ),
                TestResult(
                    nodeid="test_db.py::test_connect",
                    outcome=TestOutcome.PASSED,
                    start_time=get_test_time(2),
                    duration=1.0,
                ),
                TestResult(
                    nodeid="test_api.py::TestApi::test_get",
                    outcome=TestOutcome.PASSED,
                    start_time=get_test_time(3),
                    duration=1.0,
                ),
            ],
        )

        query = Query()

        # Module pattern (broadest)
        result = (
            query.filter_by_test()
            .with_pattern("test_api.py")
            .apply()
            .execute(sessions=[session])
        )
        assert len(result.sessions) == 1
        filtered = result.sessions[0].test_results
        assert len([t for t in filtered if "test_api.py" in t.nodeid]) == 2

        # Test name pattern (more specific)
        result = (
            query.filter_by_test()
            .with_pattern("test_get")
            .apply()
            .execute(sessions=[session])
        )
        assert len(result.sessions) == 1
        filtered = result.sessions[0].test_results
        assert len([t for t in filtered if "test_get" in t.nodeid]) == 1

        # Full path pattern (most specific)
        result = (
            query.filter_by_test()
            .with_pattern("test_api.py::test_get")
            .apply()
            .execute(sessions=[session])
        )
        assert len(result.sessions) == 1
        filtered = result.sessions[0].test_results
        assert len([t for t in filtered if t.nodeid == "test_api.py::test_get"]) == 1

    def test_session_context_preservation(self, get_test_time):
        """Test that session context is preserved when filtering.

        Session context rules:
        - Sessions containing ANY matching test are included
        - ALL tests in matching sessions are preserved
        - Session metadata (tags, IDs) is preserved
        - Test relationships stay together (API/DB tests, pass/fail, fast/slow)
        """
        # Create a test session with related tests and metadata
        session = TestSession(
            sut_name="api-service",
            session_id="test-1",
            session_start_time=get_test_time(),
            session_stop_time=get_test_time(10),
            session_duration=10.0,
            session_tags=["module_api", "type_unit", "env_test"],
            test_results=[
                # API tests (fast, pass)
                TestResult(
                    nodeid="test_api.py::test_get",
                    outcome=TestOutcome.PASSED,
                    start_time=get_test_time(),
                    duration=0.5,  # Fast test
                ),
                # API tests (slow, fail)
                TestResult(
                    nodeid="test_api.py::test_post",
                    outcome=TestOutcome.FAILED,
                    start_time=get_test_time(2),
                    duration=5.0,  # Slow test
                    longreprtext="AssertionError: Expected 201, got 400",
                ),
                # DB tests
                TestResult(
                    nodeid="test_db.py::test_connect",
                    outcome=TestOutcome.PASSED,
                    start_time=get_test_time(5),
                    duration=1.0,
                ),
            ],
        )

        query = Query()
        result = (
            query.filter_by_test()
            .with_pattern("test_get")  # Only matches first test
            .apply()
            .execute(sessions=[session])
        )

        # Verify session context preservation
        assert len(result.sessions) == 1
        filtered_session = result.sessions[0]

        # 1. Session metadata preserved
        assert filtered_session.sut_name == "api-service"
        assert filtered_session.session_id == "test-1"
        assert filtered_session.session_tags == ["module_api", "type_unit", "env_test"]
        assert filtered_session.session_duration == 10.0

        # 2. All tests preserved in matching session
        assert len(filtered_session.test_results) == 3
        assert any(
            t.nodeid == "test_api.py::test_get" for t in filtered_session.test_results
        )
        assert any(
            t.nodeid == "test_api.py::test_post" for t in filtered_session.test_results
        )
        assert any(
            t.nodeid == "test_db.py::test_connect"
            for t in filtered_session.test_results
        )

        # 3. Test relationships preserved
        api_tests = [
            t for t in filtered_session.test_results if "test_api.py" in t.nodeid
        ]
        assert len(api_tests) == 2

        # Pass/fail relationships
        assert any(t.outcome == TestOutcome.PASSED for t in api_tests)
        assert any(t.outcome == TestOutcome.FAILED for t in api_tests)

        # Fast/slow relationships
        assert any(t.duration < 1.0 for t in api_tests)  # Fast tests
        assert any(t.duration > 4.0 for t in api_tests)  # Slow tests

        # API/DB test relationships
        assert (
            len([t for t in filtered_session.test_results if "test_db.py" in t.nodeid])
            == 1
        )

    def test_convenience_methods(self, get_test_time):
        """Test convenience methods for output filtering."""
        query = Query()
        test_filter = query.filter_by_test()

        # Test with_output_containing
        test = TestResult(
            nodeid="test_api.py::test_get",
            outcome=TestOutcome.PASSED,
            start_time=get_test_time(),
            duration=1.0,
            caplog="DEBUG: test message",
            capstderr="",
            capstdout="test output",
        )

        result = (
            test_filter.with_output_containing("test")
            .apply()
            .execute(
                sessions=[
                    TestSession(
                        sut_name="api",
                        session_id="1",
                        session_start_time=get_test_time(),
                        session_stop_time=get_test_time(1),  # 1 second total duration
                        test_results=[test],
                    )
                ]
            )
        )
        assert len(result.sessions) == 1

        # Test with_error_containing
        test = TestResult(
            nodeid="test_api.py::test_post",
            outcome=TestOutcome.FAILED,
            start_time=get_test_time(),
            duration=1.0,
            longreprtext="test error message",
        )

        result = (
            test_filter.with_error_containing("error message")
            .apply()
            .execute(
                sessions=[
                    TestSession(
                        sut_name="api",
                        session_id="1",
                        session_start_time=get_test_time(),
                        session_stop_time=get_test_time(1),  # 1 second total duration
                        test_results=[test],
                    )
                ]
            )
        )
        assert len(result.sessions) == 1


class Test_QuerySystem:
    """Test suite for complete query system functionality.

    Tests the two-level filtering design and session context preservation.
    """

    def test_session_context_preservation(self, get_test_time):
        """Test that session context is preserved after filtering.

        Verifies:
        1. All tests in matching sessions are preserved
        2. Session metadata remains intact
        3. Test relationships are maintained
        """
        # Create a session with multiple tests
        test1 = TestResult(
            nodeid="test_api.py::test_get",
            outcome=TestOutcome.PASSED,
            start_time=get_test_time(),
            duration=1.0,
            caplog="DEBUG: test message",
            capstderr="",
            capstdout="test output",
        )

        test2 = TestResult(
            nodeid="test_api.py::test_post",
            outcome=TestOutcome.FAILED,
            start_time=get_test_time(10),  # 10 seconds later
            duration=2.0,
            caplog="ERROR: failed",
            capstderr="stack trace",
            capstdout="",
        )

        session = TestSession(
            sut_name="api",
            session_id="test-session",
            session_start_time=get_test_time(),
            session_stop_time=get_test_time(20),
            test_results=[test1, test2],
            tags={"environment": "staging"}
        )

        # Apply test-level filter
        query = Query()
        result = (
            query.filter_by_test()
            .with_pattern("test_get")
            .apply()
            .execute(sessions=[session])
        )

        # Verify session context preservation
        assert len(result.sessions) == 1
        filtered_session = result.sessions[0]
        assert len(filtered_session.test_results) == 2  # Both tests preserved
        assert filtered_session.tags == session.tags  # Metadata preserved
        assert filtered_session.session_id == session.session_id

    def test_timezone_aware_filtering(self, get_test_time):
        """Test timezone-aware datetime filtering.

        Verifies:
        1. Time-based filters work with timezone-aware datetimes
        2. Consistent behavior across different timezones
        """
        # Create sessions at different times
        now = get_test_time()
        old_session = TestSession(
            sut_name="api",
            session_id="old",
            session_start_time=now - timedelta(days=10),
            session_stop_time=now - timedelta(days=9),
            test_results=[],
        )

        recent_session = TestSession(
            sut_name="api",
            session_id="recent",
            session_start_time=now - timedelta(days=1),
            session_stop_time=now,
            test_results=[],
        )

        # Test time-based filtering
        query = Query()
        result = query.in_last_days(7).execute(sessions=[old_session, recent_session])

        assert len(result.sessions) == 1
        assert result.sessions[0].session_id == "recent"

    def test_combined_filtering(self, get_test_time):
        """Test combining session-level and test-level filters.

        Verifies:
        1. Session-level filters (SUT, time range) work with test-level filters
        2. Filters are applied in correct order
        3. Context is preserved at both levels
        """
        # Create test sessions
        test1 = TestResult(
            nodeid="test_api.py::test_get",
            outcome=TestOutcome.PASSED,
            start_time=get_test_time(),
            duration=1.0,
            caplog="",
            capstderr="",
            capstdout="",
        )

        session1 = TestSession(
            sut_name="api",
            session_id="recent-api",
            session_start_time=get_test_time(),
            session_stop_time=get_test_time(3600),
            test_results=[test1],
        )

        session2 = TestSession(
            sut_name="db",
            session_id="recent-db",
            session_start_time=get_test_time(),
            session_stop_time=get_test_time(3600),
            test_results=[test1],  # Same test, different service
        )

        # Apply both session and test filters
        query = Query()
        result = (
            query.for_sut("api")  # Session-level
            .filter_by_test()
            .with_pattern("test_get")  # Test-level
            .apply()
            .execute(sessions=[session1, session2])
        )

        assert len(result.sessions) == 1
        assert result.sessions[0].sut_name == "api"
        assert any("test_get" in t.nodeid for t in result.sessions[0].test_results)
