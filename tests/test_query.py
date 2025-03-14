import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import pytest
from pytest_insight.models import TestOutcome, TestResult, TestSession
from pytest_insight.query.query import (
    BasePatternFilter,
    CustomFilter,
    DurationFilter,
    FilterType,
    GlobPatternFilter,
    InvalidQueryParameterError,
    OutcomeFilter,
    Query,
    QueryResult,
    QueryTestFilter,
    RegexPatternFilter,
)


def get_test_time(offset_seconds: int = 0) -> datetime:
    """Helper to get consistent test timestamps."""
    base = datetime(2025, 3, 14, 11, 47, tzinfo=timezone.utc)
    return base + timedelta(seconds=offset_seconds)


class Test_Query:
    """Test suite for Query."""

    def test_query_with_random_sessions_via_execute_and_with_query_deconstructed(self, random_test_sessions):
        """Test using Query with random but realistic sessions via execute().

        This demonstrates using QueryTestFilter to filter by test criteria.
        Pattern matching rules:
        1. For non-regex patterns:
           - Matches are done using fnmatch with wildcards (*pattern*)
           - Pattern is matched against both file parts and test names separately
           - File part has .py extension removed before matching
           - Any part matching the pattern counts as a match
        """
        query: Query = Query()

        # Create one step at a time to test each component
        query_test_filter: QueryTestFilter = query.filter_by_test()
        query_test_filter_applied: Query = query_test_filter.with_pattern("api").apply()
        executed_result: QueryResult = query_test_filter_applied.execute(sessions=random_test_sessions)
        sessions: List[TestSession] = executed_result.sessions

        # Verify we got results
        assert sessions, "Expected sessions containing 'api' pattern"

        # Verify pattern matching rules
        for session in sessions:
            matched = False
            for test in session.test_results:
                # Pattern should match either module part (after .py strip) or test name
                module_part = test.nodeid.split("::")[0].replace(".py", "")
                test_part = test.nodeid.split("::")[1]
                if "api" in module_part or "api" in test_part:
                    matched = True
                    break
            assert matched, f"Session {session.session_id} had no tests matching 'api' pattern"

            # Verify session metadata preserved
            assert session.session_id.startswith("session_")
            assert session.sut_name.endswith("_service")
            assert len(session.session_tags) == 3  # module, type, env tags
            assert any(tag.startswith("module_") for tag in session.session_tags)
            assert any(tag.startswith("type_") for tag in session.session_tags)
            assert any(tag.startswith("env_") for tag in session.session_tags)

            # All tests preserved in matching sessions
            assert len(session.test_results) > 0
            for test in session.test_results:
                # Verify nodeid format: test_{module}.py::test_{action}_{module}
                parts = test.nodeid.split("::")
                assert len(parts) == 2, f"Invalid nodeid format: {test.nodeid}"
                assert parts[0].startswith("test_"), f"Invalid module format: {parts[0]}"
                assert parts[0].endswith(".py"), f"Invalid module format: {parts[0]}"
                assert parts[1].startswith("test_"), f"Invalid test format: {parts[1]}"

                # Verify test attributes
                assert test.outcome.to_str() in TestOutcome.to_list()
                assert test.duration > 0
                assert isinstance(test.start_time, datetime)
                assert test.stop_time is not None

    def test_query_with_random_sessions_via_execute(self, random_test_sessions):
        """Test using Query with random but realistic sessions via execute().

        This demonstrates passing sessions directly to execute(), bypassing storage.
        Session context rules:
        1. Sessions containing ANY matching test are included
        2. ALL tests in matching sessions are preserved
        3. Session metadata (tags, IDs) is preserved
        """
        query: Query = Query()

        # Use execute() with predefined sessions - match test_file pattern
        result: QueryResult = (
            query.filter_by_test().with_pattern("test_file").apply().execute(sessions=random_test_sessions)
        )
        result_sessions: List[TestSession] = result.sessions

        # Verify we got results
        assert result_sessions

        # Verify session context is preserved
        for session in result_sessions:
            # Session metadata preserved
            assert session.session_id.isdigit()  # Should be a number from 1-1000
            assert session.sut_name.startswith("test_sut_")
            assert session.session_tags[0].startswith("tag_")

            # All tests preserved in matching sessions
            assert len(session.test_results) > 0
            for test in session.test_results:
                assert test.nodeid.startswith("test_file_")
                assert "test_case_" in test.nodeid
                assert test.outcome in [
                    TestOutcome.PASSED,
                    TestOutcome.FAILED,
                    TestOutcome.SKIPPED,
                ]
                assert test.duration > 0
                assert isinstance(test.start_time, datetime)
                assert test.duration is not None
                assert test.rerun_test_groups == []
                assert test.session_tags == session.session_tags

    def test_query_with_random_sessions_via_storage(self, random_test_sessions):
        """Test using Query with predefined sessions via InMemoryStorage.

        This demonstrates using InMemoryStorage to hold predefined sessions.
        Pattern matching rules:
        1. For non-regex patterns:
           - Matches are done using fnmatch with wildcards (*pattern*)
           - Pattern is matched against both file parts and test names separately
           - File part has .py extension removed before matching
           - Any part matching the pattern counts as a match
        """
        # Create InMemoryStorage with predefined sessions
        from pytest_insight.storage import InMemoryStorage

        storage = InMemoryStorage(sessions=random_test_sessions)

        # Create Query with custom storage
        query = Query(storage=storage)

        # Run query - match test type pattern (get, post, etc.)
        result = query.filter_by_test().with_pattern("get").apply().execute()

        # Verify we got results
        assert result.sessions, "Expected sessions containing 'get' in test name"

        # Verify pattern matching rules
        for session in result.sessions:
            matched = False
            for test in session.test_results:
                # Pattern should match either module part (after .py strip) or test name
                module_part = test.nodeid.split("::")[0].replace(".py", "")
                test_part = test.nodeid.split("::")[1]
                if "get" in module_part or "get" in test_part:
                    matched = True
                    break
            assert matched, f"Session {session.session_id} had no tests matching 'get' pattern"

            # Verify session metadata preserved
            assert session.session_id.startswith("session_")
            assert session.sut_name.endswith("_service")
            assert len(session.session_tags) == 3  # module, type, env tags
            assert any(tag.startswith("module_") for tag in session.session_tags)
            assert any(tag.startswith("type_") for tag in session.session_tags)
            assert any(tag.startswith("env_") for tag in session.session_tags)

            # All tests preserved in matching sessions
            assert len(session.test_results) > 0
            for test in session.test_results:
                # Verify nodeid format: test_{module}.py::test_{action}_{module}
                parts = test.nodeid.split("::")
                assert len(parts) == 2, f"Invalid nodeid format: {test.nodeid}"
                assert parts[0].startswith("test_"), f"Invalid module format: {parts[0]}"
                assert parts[0].endswith(".py"), f"Invalid module format: {parts[0]}"
                assert parts[1].startswith("test_"), f"Invalid test format: {parts[1]}"

                # Verify test attributes
                assert test.outcome.to_str() in TestOutcome.to_list()
                assert test.duration > 0
                assert isinstance(test.start_time, datetime)
                assert test.stop_time is not None


class Test_QueryTestFilter:
    """Test suite for test-level filtering in Query."""

    def test_query_with_duration_filter(self, random_test_sessions, mocker):
        """Test filtering by duration range."""
        query = Query()
        storage_mock = mocker.patch("pytest_insight.query.query.get_storage_instance")
        storage_mock.return_value.load_sessions.return_value = random_test_sessions

        # Test duration range filtering
        result = query.filter_by_test().with_duration_between(1.0, 2.0).apply().execute()

        # Verify we got results
        assert len(result.sessions) > 0

        # Verify all tests in range
        for session in result.sessions:
            matching_tests = [t for t in session.test_results if 1.0 <= t.duration <= 2.0]
            assert matching_tests

        # Test invalid duration ranges
        with pytest.raises(InvalidQueryParameterError):
            query.filter_by_test().with_duration_between(-1.0, 1.0).apply()
        with pytest.raises(InvalidQueryParameterError):
            query.filter_by_test().with_duration_between(2.0, 1.0).apply()


class Test_PatternFilters:
    """Test suite for pattern filtering implementations."""

    def test_module_name_stripping(self):
        """Test .py extension stripping for module part."""
        glob_filter = GlobPatternFilter("api")

        # Create test results with different module names
        tests = [
            TestResult(
                nodeid="test_api.py::test_get",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(),
                duration=1.0,
            ),
            TestResult(
                nodeid="api_test.py::test_post",
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
        ]

        # Verify module name stripping
        for test in tests:
            if "api" in test.nodeid.split("::")[0].replace(".py", ""):
                assert glob_filter.matches(test), f"Should match {test.nodeid}"
            else:
                assert not glob_filter.matches(test), f"Should not match {test.nodeid}"

    def test_pattern_part_matching(self):
        """Test pattern matching against module and test parts."""
        glob_filter = GlobPatternFilter("get")

        # Create test results with pattern in different parts
        tests = [
            TestResult(
                nodeid="test_get.py::test_post",  # Pattern in module
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(),
                duration=1.0,
            ),
            TestResult(
                nodeid="test_api.py::test_get",  # Pattern in test name
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(1),
                duration=1.0,
            ),
            TestResult(
                nodeid="test_api.py::test_post",  # Pattern in neither
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(2),
                duration=1.0,
            ),
        ]

        # Verify pattern matching in both parts
        for test in tests:
            module_part, test_part = test.nodeid.split("::")
            if "get" in module_part.replace(".py", "") or "get" in test_part:
                assert glob_filter.matches(test), f"Should match {test.nodeid}"
            else:
                assert not glob_filter.matches(test), f"Should not match {test.nodeid}"

    def test_regex_vs_glob_patterns(self):
        """Test regex pattern matching vs glob pattern matching."""
        tests = [
            TestResult(
                nodeid="test_api.py::TestAPI::test_get",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(),
                duration=1.0,
            ),
            TestResult(
                nodeid="test_api.py::test_api_post",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(1),
                duration=1.0,
            ),
            TestResult(
                nodeid="test_db.py::TestDB::test_api_connect",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(2),
                duration=1.0,
            ),
        ]

        # Test glob pattern
        glob_filter = GlobPatternFilter("api")
        for test in tests:
            assert glob_filter.matches(test), f"Glob should match {test.nodeid}"

        # Test regex pattern
        regex_filter = RegexPatternFilter(r"test_api\.py::")
        for test in tests:
            if test.nodeid.startswith("test_api.py::"):
                assert regex_filter.matches(test), f"Regex should match {test.nodeid}"
            else:
                assert not regex_filter.matches(test), f"Regex should not match {test.nodeid}"

    def test_glob_pattern_wildcards(self):
        """Test glob pattern wildcard behavior."""
        tests = [
            TestResult(
                nodeid="test_api.py::test_get",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(),
                duration=1.0,
            ),
            TestResult(
                nodeid="test_API.py::test_post",  # Capital API
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(1),
                duration=1.0,
            ),
        ]

        # Test case-sensitive pattern
        filter = GlobPatternFilter("API")
        assert not filter.matches(tests[0]), "Should not match lowercase api"
        assert filter.matches(tests[1]), "Should match uppercase API"

    def test_invalid_nodeid_format(self):
        """Test handling of invalid nodeid formats."""
        glob_filter = GlobPatternFilter("api")
        regex_filter = RegexPatternFilter(r"test_\w+")

        # No :: separator
        test = TestResult(nodeid="test_api", outcome=TestOutcome.PASSED, start_time=get_test_time(), duration=1.0)
        assert not glob_filter.matches(test), "Should not match without :: separator"
        assert not regex_filter.matches(test), "Should not match without :: separator"

        # Empty parts
        test = TestResult(nodeid="::test_api", outcome=TestOutcome.PASSED, start_time=get_test_time(), duration=1.0)
        assert not glob_filter.matches(test), "Should not match with empty module part"
        test = TestResult(nodeid="test_api.py::", outcome=TestOutcome.PASSED, start_time=get_test_time(), duration=1.0)
        assert not glob_filter.matches(test), "Should not match with empty test part"

    def test_empty_pattern_error(self):
        """Test that empty patterns raise error."""
        with pytest.raises(InvalidQueryParameterError):
            GlobPatternFilter("")
        with pytest.raises(InvalidQueryParameterError):
            RegexPatternFilter("")

    def test_pattern_filter_serialization(self):
        """Test serialization of pattern filters."""
        # Complex regex pattern
        filter = RegexPatternFilter(r"test_(\w+)\.py::test_\1")
        assert filter.to_dict()["pattern"] == r"test_(\w+)\.py::test_\1"

        # Pattern with special characters
        filter = GlobPatternFilter("test_*_api")
        assert filter.to_dict()["pattern"] == "test_*_api"

    def test_multiple_filters_interaction(self):
        """Test interaction between multiple pattern filters."""
        session = TestSession(
            sut_name="api-service",
            session_id="test-1",
            session_start_time=get_test_time(0),
            session_stop_time=get_test_time(3),
            session_duration=3.0,
            test_results=[
                TestResult(
                    nodeid="test_api.py::test_get",
                    outcome=TestOutcome.PASSED,
                    start_time=get_test_time(0),
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
            ],
        )

        query = Query()

        # Test combining patterns
        result = (
            query.filter_by_test()
            .with_pattern("api")  # Matches test_api.py
            .with_pattern("post", use_regex=True)  # Matches test_post
            .apply()
            .execute(sessions=[session])
        )

        # Verify results
        assert len(result.sessions) == 1
        session = result.sessions[0]
        assert len(session.test_results) == 3  # All tests preserved
        assert any(t.nodeid == "test_api.py::test_post" for t in session.test_results)


class Test_PatternMatching:
    """Test suite for pattern matching behavior.

    Pattern matching rules from MEMORY[bdabab6d] and MEMORY[9240e042]:
    1. Non-regex patterns:
       - Pattern wrapped with wildcards: *{pattern}*
       - Test nodeid split on :: into parts
       - Module part: .py extension stripped
       - Test parts: Direct pattern matching
       - ANY part matching counts as match

    2. Regex patterns:
       - Pattern used as-is (no wildcards)
       - Matched against full nodeid
       - re.search() used for matching
    """

    def test_pattern_rules_examples(self):
        """Test pattern matching rules with examples.

        For non-regex patterns:
        - Pattern is wrapped with wildcards: *{pattern}*
        - Test nodeid is split on :: into parts
        - Module part has .py extension stripped before matching
        - Any part matching the pattern counts as a match
        """
        test_cases = [
            ("api", "test_api.py::test_get", True, "Should match in module name"),
            ("get", "test_api.py::test_get", True, "Should match in test name"),
            ("test", "test_api.py::test_get", True, "Should match in both parts"),
            ("xyz", "test_api.py::test_get", False, "Should not match anywhere"),
        ]

        for pattern, nodeid, should_match, message in test_cases:
            filter = GlobPatternFilter(pattern)
            test = TestResult(nodeid=nodeid, outcome=TestOutcome.PASSED, start_time=get_test_time(), duration=1.0)
            assert filter.matches(test) == should_match, message

    def test_regex_pattern_rules(self):
        """Test regex pattern matching rules.

        For regex patterns:
        - Pattern is used as-is (no wildcards added)
        - Pattern is matched against full nodeid using re.search()
        - Test matches if pattern matches anywhere in nodeid
        """
        test_cases = [
            (r"test_\w+\.py", "test_api.py::test_get", True, "Should match module pattern"),
            (r"test_[a-z]+$", "test_api.py::test_get", True, "Should match test name"),
            (r"api.*get", "test_api.py::test_get", True, "Should match across parts"),
            (r"xyz", "test_api.py::test_get", False, "Should not match anywhere"),
        ]

        for pattern, nodeid, should_match, message in test_cases:
            filter = RegexPatternFilter(pattern)
            test = TestResult(
                nodeid=nodeid,
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(),
                duration=1.0,
            )
            assert filter.matches(test) == should_match, message

    def test_mixed_pattern_strategies(self, random_test_sessions):
        """Test mixing different pattern matching strategies.

        Demonstrates combining:
        1. Glob patterns (with implicit wildcards)
        2. Regex patterns (for precise matching)
        3. Session context preservation
        """
        # Create test session with mixed patterns
        session = TestSession(
            sut_name="api-service",
            session_id="test-1",
            session_start_time=get_test_time(0),
            session_duration=3.0,  # Last test starts at t=2 and runs for 1s = 3s total
            test_results=[
                TestResult(
                    nodeid="test_api.py::test_get",
                    outcome=TestOutcome.PASSED,
                    start_time=get_test_time(0),
                    duration=1.0,
                ),
                TestResult(
                    nodeid="test_api.py::test_post",
                    outcome=TestOutcome.PASSED,
                    start_time=get_test_time(1),
                    duration=1.0,
                ),
                TestResult(
                    nodeid="test_web.py::test_api_get",
                    outcome=TestOutcome.PASSED,
                    start_time=get_test_time(2),
                    duration=1.0,
                ),
            ],
        )

        query = Query()

        # Glob for module, regex for test name
        result = (
            query.filter_by_test()
            .with_pattern("api")  # Matches test_api.py
            .with_pattern(r"test_\w{3}$", use_regex=True)  # Matches 3-char test names
            .apply()
            .execute(sessions=[session])
        )

        # Verify correct matching
        for session in result.sessions:
            matched = False
            for test in session.test_results:
                if "api" in test.nodeid and re.search(r"test_\w{3}$", test.nodeid.split("::")[-1]):
                    matched = True
                    break
            assert matched, "Should match both glob and regex patterns"

    def test_glob_pattern_hierarchy(self):
        """Test pattern hierarchy from broad to specific.

        Pattern hierarchy (from broad to specific):
        - Module patterns (e.g., "test_api.py")
        - Test name patterns (e.g., "test_get")
        - Full path patterns (e.g., "test_api.py::test_get")
        """
        # Create test sessions with different pattern matches
        sessions = [
            TestSession(
                sut_name="api-service",
                session_id="test-1",
                session_start_time=get_test_time(0),
                session_stop_time=get_test_time(2),
                session_duration=2.0,  # Last test starts at t=1 and runs for 1s = 2s total
                test_results=[
                    TestResult(
                        nodeid="test_api.py::test_get",
                        outcome=TestOutcome.PASSED,
                        start_time=get_test_time(0),
                        duration=1.0,
                    ),
                    TestResult(
                        nodeid="test_api.py::test_post",
                        outcome=TestOutcome.PASSED,
                        start_time=get_test_time(1),
                        duration=1.0,
                    ),
                ],
            ),
            TestSession(
                sut_name="web-service",
                session_id="test-2",
                session_start_time=get_test_time(0),
                session_stop_time=get_test_time(3),
                session_duration=3.0,  # Test starts at t=2 and runs for 1s = 3s total
                test_results=[
                    TestResult(
                        nodeid="test_web.py::test_get",
                        outcome=TestOutcome.PASSED,
                        start_time=get_test_time(2),
                        duration=1.0,
                    )
                ],
            ),
        ]

        query = Query()

        # Module pattern (broadest)
        module_result = (
            query.filter_by_test()
            .with_pattern("api")  # Matches test_api.py
            .apply()
            .execute(sessions=sessions)
        )

        # Test name pattern (medium)
        name_result = (
            query.filter_by_test()
            .with_pattern("get")  # Matches test_get
            .apply()
            .execute(sessions=sessions)
        )

        # Full path pattern (most specific)
        path_result = (
            query.filter_by_test()
            .with_pattern("test_api::test_get")  # Exact path match
            .apply()
            .execute(sessions=sessions)
        )

        # Verify hierarchy (more specific = fewer matches)
        assert len(path_result.sessions) <= len(name_result.sessions)
        assert len(name_result.sessions) <= len(module_result.sessions)

    def test_pattern_examples(self):
        """Test pattern matching with example test cases."""
        test_cases = [
            ("api", "test_api.py::test_get", True),
            ("api", "test_web.py::test_get", False),
            ("test_", "test_api.py::test_get", True),
            ("get", "test_api.py::test_get", True),
            ("get", "test_api.py::test_post", False),
        ]

        for pattern, nodeid, should_match in test_cases:
            filter = GlobPatternFilter(pattern)
            test = TestResult(nodeid=nodeid, outcome=TestOutcome.PASSED, start_time=get_test_time(), duration=1.0)
            assert filter.matches(test) == should_match, f"Pattern '{pattern}' matching failed for '{test.nodeid}'"

    def test_empty_pattern_error(self):
        """Test that empty patterns raise error."""
        with pytest.raises(InvalidQueryParameterError):
            GlobPatternFilter("")

        with pytest.raises(InvalidQueryParameterError):
            RegexPatternFilter("")

    def test_pattern_filter_serialization(self):
        """Test serialization of pattern filters."""
        # Complex regex pattern
        filter = RegexPatternFilter(r"test_(\w+)\.py::test_\1")
        assert filter.to_dict()["pattern"] == r"test_(\w+)\.py::test_\1"

        # Pattern with special characters
        filter = GlobPatternFilter("test_*_api")
        assert filter.to_dict()["pattern"] == "test_*_api"


class Test_BasePatternFilter:
    """Test suite for BasePatternFilter."""

    def test_pattern_validation(self):
        """Test pattern validation in base filter."""

        # Create concrete subclass for testing
        class TestFilter(BasePatternFilter):
            def matches(self, test: TestResult) -> bool:
                return True

            def to_dict(self) -> Dict:
                return {}

        # Valid patterns
        TestFilter("valid")
        TestFilter("test_pattern")
        TestFilter("123")

        # Invalid patterns
        with pytest.raises(InvalidQueryParameterError):
            TestFilter("")
        with pytest.raises(InvalidQueryParameterError):
            TestFilter("   ")
        with pytest.raises(InvalidQueryParameterError):
            TestFilter(None)


class Test_DurationFilter:
    """Test suite for DurationFilter."""

    def test_duration_validation(self):
        """Test duration bounds validation."""
        # Valid ranges
        DurationFilter(0, 1)
        DurationFilter(1, 1)  # Equal bounds
        DurationFilter(0, float("inf"))  # Unbounded max

        # Invalid ranges
        with pytest.raises(InvalidQueryParameterError):
            DurationFilter(-1, 1)  # Negative min
        with pytest.raises(InvalidQueryParameterError):
            DurationFilter(2, 1)  # Min > max

    def test_duration_matching(self):
        """Test duration range matching."""
        filter = DurationFilter(1.0, 3.0)

        # Create test results with different durations
        tests = [
            TestResult(
                nodeid="test_1",
                duration=0.5,
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(),
            ),
            TestResult(
                nodeid="test_2",
                duration=1.0,
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(1),
            ),
            TestResult(
                nodeid="test_3",
                duration=2.0,
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(2),
            ),
            TestResult(
                nodeid="test_4",
                duration=3.0,
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(3),
            ),
            TestResult(
                nodeid="test_5",
                duration=3.5,
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(4),
            ),
        ]

        # Verify matching
        assert not filter.matches(tests[0])  # Too fast
        assert filter.matches(tests[1])  # At min bound
        assert filter.matches(tests[2])  # In range
        assert filter.matches(tests[3])  # At max bound
        assert not filter.matches(tests[4])  # Too slow

    def test_duration_serialization(self):
        """Test duration filter serialization."""
        filter = DurationFilter(1.5, 2.5)
        data = filter.to_dict()

        # Verify serialization
        assert data["type"] == FilterType.DURATION.name
        assert data["min_seconds"] == 1.5
        assert data["max_seconds"] == 2.5

        # Verify deserialization
        restored = DurationFilter.from_dict(data)
        assert restored.min_seconds == 1.5
        assert restored.max_seconds == 2.5


class Test_OutcomeFilter:
    """Test suite for OutcomeFilter."""

    def test_outcome_validation(self):
        """Test outcome validation."""
        # Valid outcomes
        OutcomeFilter(TestOutcome.PASSED)
        OutcomeFilter("passed")  # String form
        OutcomeFilter(TestOutcome.FAILED)
        OutcomeFilter("failed")

        # Invalid outcomes
        with pytest.raises(InvalidQueryParameterError):
            OutcomeFilter("invalid")
        with pytest.raises(InvalidQueryParameterError):
            OutcomeFilter(None)

    def test_outcome_matching(self):
        """Test outcome matching."""
        filter = OutcomeFilter(TestOutcome.PASSED)

        # Create test results with different outcomes
        tests = [
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
                duration=1.0,
            ),
            TestResult(
                nodeid="test_3",
                outcome=TestOutcome.SKIPPED,
                start_time=get_test_time(2),
                duration=1.0,
            ),
        ]

        # Verify matching
        assert filter.matches(tests[0])  # Passed
        assert not filter.matches(tests[1])  # Failed
        assert not filter.matches(tests[2])  # Skipped

    def test_outcome_serialization(self):
        """Test outcome filter serialization."""
        filter = OutcomeFilter(TestOutcome.PASSED)
        data = filter.to_dict()

        # Verify serialization
        assert data["type"] == FilterType.OUTCOME.name
        assert data["outcome"] == TestOutcome.PASSED.name

        # Verify deserialization
        restored = OutcomeFilter.from_dict(data)
        assert restored.outcome == TestOutcome.PASSED


class Test_CustomFilter:
    """Test suite for CustomFilter."""

    def test_custom_predicate(self):
        """Test custom predicate filtering."""

        # Define custom predicates
        def is_long_test(test: TestResult) -> bool:
            return test.duration > 5.0

        def has_warning(test: TestResult) -> bool:
            return bool(test.has_warning)

        # Create filters
        duration_filter = CustomFilter(is_long_test, "long_tests")
        warning_filter = CustomFilter(has_warning, "warning_tests")

        # Create test results
        tests = [
            TestResult(
                nodeid="test_1",
                duration=6.0,
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(),
                has_warning=False,
            ),
            TestResult(
                nodeid="test_2",
                duration=2.0,
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(1),
                has_warning=True,
            ),
            TestResult(
                nodeid="test_3",
                duration=7.0,
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(2),
                has_warning=True,
            ),
        ]

        # Test duration filter
        assert duration_filter.matches(tests[0])  # Long test
        assert not duration_filter.matches(tests[1])  # Short test
        assert duration_filter.matches(tests[2])  # Long test with warning

        # Test warning filter
        assert not warning_filter.matches(tests[0])  # No warning
        assert warning_filter.matches(tests[1])  # Has warning
        assert warning_filter.matches(tests[2])  # Has warning

    def test_custom_filter_serialization(self):
        """Test custom filter serialization."""

        def always_true(test: TestResult) -> bool:
            return True

        filter = CustomFilter(always_true, "test_filter")
        data = filter.to_dict()

        # Verify serialization
        assert data["type"] == FilterType.CUSTOM.name
        assert data["name"] == "test_filter"

        # Note: Custom filters can't be fully deserialized since predicates
        # can't be serialized. The from_dict method raises NotImplementedError
        with pytest.raises(NotImplementedError):
            CustomFilter.from_dict(data)
