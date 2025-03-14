from typing import List

import pytest
from pytest_insight.models import TestOutcome, TestSession
from pytest_insight.query.query import (
    InvalidQueryParameterError,
    Query,
    QueryResult,
    QueryTestFilter,
)

# @pytest.fixture
# def test_sessions():
#     """Create a set of test sessions for filtering tests."""
#     now = datetime.now()

#     # Session 1: Mixed tests with different durations and outcomes
#     session1_start = now - timedelta(days=1)
#     session1 = TestSession(
#         sut_name="api-service",
#         session_id="session1",
#         session_start_time=session1_start,
#         session_stop_time=session1_start + timedelta(seconds=30),
#         session_duration=30.0,  # 30 seconds total duration
#         test_results=[
#             TestResult(
#                 nodeid="test_api.py::test_get",
#                 outcome=TestOutcome.PASSED,
#                 start_time=session1_start,  # First test starts at session start
#                 duration=1.5,  # Medium duration
#             ),
#             TestResult(
#                 nodeid="test_api.py::test_post",
#                 outcome=TestOutcome.FAILED,
#                 start_time=session1_start + timedelta(seconds=1.5),  # Starts after first test
#                 duration=0.5,  # Fast
#             ),
#             TestResult(
#                 nodeid="test_db.py::test_connection",
#                 outcome=TestOutcome.PASSED,
#                 start_time=session1_start + timedelta(seconds=2.0),  # Starts after second test
#                 duration=5.0,  # Slow
#             ),
#         ],
#         rerun_test_groups=[],
#         session_tags={"env": "dev", "python": "3.9"},
#     )

#     # Session 2: All tests passed but different patterns
#     session2_start = now - timedelta(hours=12)
#     session2 = TestSession(
#         sut_name="web-service",
#         session_id="session2",
#         session_start_time=session2_start,
#         session_stop_time=session2_start + timedelta(seconds=20),
#         session_duration=20.0,  # 20 seconds total duration
#         test_results=[
#             TestResult(
#                 nodeid="test_web.py::test_login",
#                 outcome=TestOutcome.PASSED,
#                 start_time=session2_start,  # First test starts at session start
#                 duration=1.0,
#             ),
#             TestResult(
#                 nodeid="test_web.py::test_logout",
#                 outcome=TestOutcome.PASSED,
#                 start_time=session2_start + timedelta(seconds=1.0),  # Starts after first test
#                 duration=0.8,
#             ),
#             TestResult(
#                 nodeid="test_auth.py::test_session",
#                 outcome=TestOutcome.SKIPPED,
#                 start_time=session2_start + timedelta(seconds=1.8),  # Starts after second test
#                 duration=0.1,
#             ),
#         ],
#         rerun_test_groups=[],
#         session_tags={"env": "prod", "python": "3.8"},
#     )

#     return [session1, session2]
# #


class Test_Query:
    """Test suite for Query."""

    def test_query_with_random_sessions_via_execute_and_with_query_deconstructed(
        self, random_test_sessions
    ):
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
        executed_result: QueryResult = query_test_filter_applied.execute(
            sessions=random_test_sessions
        )
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
                assert test.start_time is not None
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
                assert test.start_time is not None
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
                assert test.start_time is not None
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

        # Test old method still works but warns
        with pytest.warns(DeprecationWarning):
            query.filter_by_test().with_duration(1.0, 2.0).apply()

    # def test_filter_by_pattern_matches_test_name(self, test_sessions, mocker):
    #     """Test pattern matching against test name while preserving session context."""
    #     query = Query()
    #     storage_mock = mocker.patch("pytest_insight.query.query.get_storage_instance")
    #     storage_mock.return_value.load_sessions.return_value = test_sessions

    #     # Test module-only pattern matching (broadest)
    #     module_result = query.filter_by_test().with_pattern("api").apply().execute()
    #     assert len(module_result.sessions) > 0
    #     # Verify substring match against module name after stripping .py
    #     matching_tests = [test for test in module_result.sessions[0].test_results
    #                      if "api" in test.nodeid.split("::")[0].replace(".py", "")]
    #     assert matching_tests

    #     # Test test-name-only pattern matching (medium)
    #     name_result = query.filter_by_test().with_pattern("get").apply().execute()
    #     assert len(name_result.sessions) > 0
    #     # Verify substring match against test name
    #     matching_tests = [test for test in name_result.sessions[0].test_results
    #                      if "get" in test.nodeid.split("::")[1]]
    #     assert matching_tests

    #     # Test full path pattern matching (most specific)
    #     path_result = query.filter_by_test().with_pattern("test_api::test_get").apply().execute()
    #     assert len(path_result.sessions) > 0
    #     # Verify both parts match after splitting on ::
    #     matching_tests = [test for test in path_result.sessions[0].test_results
    #                      if test.nodeid.split("::")[0].replace(".py", "") == "test_api" and
    #                      "test_get" in test.nodeid.split("::")[1]]
    #     assert matching_tests

    #     # Verify pattern hierarchy (more specific = fewer matches)
    #     assert len(path_result.sessions) <= len(name_result.sessions)
    #     assert len(name_result.sessions) <= len(module_result.sessions)

    # def test_filter_by_pattern_preserves_session_context(self, test_sessions, mocker):
    #     """Test that pattern matching preserves session context.

    #     Pattern matching rules:
    #     1. Non-regex patterns:
    #        - Pattern wrapped with wildcards: *{pattern}*
    #        - Test nodeid split on :: into parts
    #        - Module part: .py extension stripped before matching
    #        - Test name part: pattern matched directly
    #        - Test matches if ANY part matches pattern

    #     Session context rules:
    #     1. Sessions containing ANY matching test are included
    #     2. ALL tests in matching sessions are preserved
    #     3. Session metadata (tags, IDs) is preserved
    #     4. Test relationships stay together
    #     """
    #     # Create storage mock that returns our test sessions
    #     storage_mock = mocker.Mock()
    #     storage_mock.load_sessions.return_value = test_sessions
    #     query = Query(storage=storage_mock)

    #     # Filter by API tests - should match test_api.py module name after stripping .py
    #     result = query.filter_by_test().with_pattern("api").apply().execute()

    #     # Verify we got exactly one session (session1 with API tests)
    #     assert len(result.sessions) == 1

    #     # Verify session1 was selected and metadata preserved
    #     session = result.sessions[0]
    #     assert session.session_id == "session1"  # ID preserved
    #     assert session.sut_name == "api-service"  # SUT name preserved
    #     assert session.session_tags == {"env": "dev", "python": "3.9"}  # Tags preserved

    #     # Verify ALL tests preserved in matching session
    #     assert len(session.test_results) == 3  # All 3 tests from session1

    #     # Verify test relationships preserved (API tests + DB test)
    #     api_tests = [t for t in session.test_results if "test_api.py" in t.nodeid]
    #     db_tests = [t for t in session.test_results if "test_db.py" in t.nodeid]
    #     assert len(api_tests) == 2  # Both API tests present
    #     assert len(db_tests) == 1   # DB test preserved (relationship maintained)

    #     # Verify test details preserved
    #     for test in api_tests:
    #         # Verify module part matches after stripping .py
    #         assert test.nodeid.split("::")[0].replace(".py", "") == "test_api"

    #     # Verify specific test outcomes preserved
    #     assert any(t.nodeid == "test_api.py::test_get" and t.outcome == TestOutcome.PASSED for t in api_tests)
    #     assert any(t.nodeid == "test_api.py::test_post" and t.outcome == TestOutcome.FAILED for t in api_tests)
    #     assert any(t.nodeid == "test_db.py::test_connection" and t.outcome == TestOutcome.PASSED for t in db_tests)

    #     # Verify session2 excluded (no matching tests)
    #     assert all(s.session_id != "session2" for s in result.sessions)

    #     # Verify original test sessions unmodified
    #     assert len(test_sessions) == 2
    #     assert test_sessions[0].session_id == "session1"
    #     assert test_sessions[1].session_id == "session2"
    #     assert test_sessions[0].session_tags == {"env": "dev", "python": "3.9"}
    #     assert test_sessions[1].session_tags == {"env": "prod", "python": "3.8"}

    # def test_filter_by_pattern_matches_partial_names(self, test_sessions, mocker):
    #     """Test pattern matching behavior for partial names.

    #     For non-regex patterns:
    #     - Module part: Pattern is matched with wildcards (*pattern*) after stripping .py
    #     - Test name part: Pattern is also matched with wildcards (*pattern*)

    #     The test data contains only API-related tests, so:
    #     - 'api' should match module names containing 'api'
    #     - 'get' should match test names containing 'get'
    #     - 'test_api' should match the full module name
    #     """
    #     storage_mock = mocker.patch("pytest_insight.query.query.get_storage_instance")
    #     storage_mock.return_value.load_sessions.return_value = test_sessions

    #     query = Query()

    #     # Match by partial module name (api matches *api* in test_api)
    #     result1 = query.filter_by_test().with_pattern("api").apply().execute()
    #     assert len(result1.sessions) > 0
    #     # Verify *api* matches test_api after .py strip
    #     matching_tests = [test for test in result1.sessions[0].test_results
    #                      if "api" in test.nodeid.split("::")[0].replace(".py", "")]
    #     assert matching_tests

    #     # Match by partial test name (get) - should match test_get
    #     # result2 = query.filter_by_test().with_pattern("get").apply().execute()
    #     # assert len(result2.sessions) > 0  # Test contains 'get'
    #     filtered: QueryTestFilter = query.filter_by_test()
    #     print(f"DEBUG: 'filtered' = {filtered}")
    #     pattern: QueryTestFilter = filtered.with_pattern("get")
    #     print(f"DEBUG: 'pattern' = {pattern}")
    #     applied: Query = pattern.apply()
    #     print(f"DEBUG: 'applied' = {applied}")
    #     executed: QueryResult = applied.execute()
    #     print(f"DEBUG: 'executed' = {executed}")
    #     assert len(executed.sessions) > 0

    #     # Match by partial path (test_api matches *test_api* in module name)
    #     result3 = query.filter_by_test().with_pattern("test_api").apply().execute()
    #     assert len(result3.sessions) > 0
    #     # Verify module name matches after stripping .py
    #     matching_tests = [test for test in result3.sessions[0].test_results
    #                      if test.nodeid.split("::")[0].replace(".py", "") == "test_api"]
    #     assert matching_tests

    # def test_filter_by_pattern_matches_partial_names_random_sessions(self, random_test_sessions):
    #     """Test pattern matching behavior for partial names.

    #     For non-regex patterns:
    #     - Module part: Pattern is matched with wildcards (*pattern*) after stripping .py
    #     - Test name part: Pattern is also matched with wildcards (*pattern*)

    #     The test data contains only API-related tests, so:
    #     - 'api' should match module names containing 'api'
    #     - 'get' should match test names containing 'get'
    #     - 'test_api' should match the full module name
    #     """
    #     query = Query()

    #     result1 = query.filter_by_test().with_pattern("api").apply().execute()
    #     assert len(result1.sessions) > 0
    #     matching_tests = [test for test in result1.sessions[0].test_results
    #                      if "api" in test.nodeid.split("::")[0].replace(".py", "")]
    #     assert matching_tests

    #     # Match by partial test name (get) - should find test_get
    #     # result2 = query.filter_by_test().with_pattern("get").apply().execute()
    #     # assert len(result2.sessions) > 0  # Test contains 'get'
    #     filtered: QueryTestFilter = query.filter_by_test()
    #     pattern: QueryTestFilter = filtered.with_pattern("get")
    #     applied: Query = pattern.apply()
    #     executed: QueryResult = applied.execute()
    #     assert len(executed.sessions) > 0

    #     # Match by partial path (test_api matches *test_api* in module name)
    #     result3 = query.filter_by_test().with_pattern("test_api").apply().execute()
    #     assert len(result3.sessions) > 0
    #     # Verify module name matches after stripping .py
    #     matching_tests = [test for test in result3.sessions[0].test_results
    #                      if test.nodeid.split("::")[0].replace(".py", "") == "test_api"]
    #     assert matching_tests
