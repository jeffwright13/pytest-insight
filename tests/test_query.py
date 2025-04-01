import pytest
from pytest_insight.core.models import TestOutcome, TestResult, TestSession
from pytest_insight.core.query import InvalidQueryParameterError, Query
from pytest_insight.core.storage import InMemoryStorage


def test_session_with_tags(get_test_time):
    """Test tag-based filtering methods.

    This test verifies that:
        - with_session_tag() correctly filters sessions by tag
        - with_session_id_pattern() correctly filters sessions by ID pattern
        - All tests within matching sessions are preserved
        - Session metadata is maintained
    """
    # Create sessions with different tags and IDs
    # Session with prod environment tag
    prod_session = TestSession(
        sut_name="api",
        session_id="prod-run-123",
        session_tags={"env": "prod", "region": "us-west"},
        session_start_time=get_test_time(-3600),  # 1 hour ago
        session_stop_time=get_test_time(-3600 + 300),  # 5 minutes later
        test_results=[
            TestResult(
                nodeid="test_api.py::test_endpoint",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-3600 + 10),
                duration=1.0,
            ),
        ],
    )

    # Session with staging environment tag
    staging_session = TestSession(
        sut_name="api",
        session_id="staging-run-456",
        session_tags={"env": "staging", "region": "us-east"},
        session_start_time=get_test_time(-7200),  # 2 hours ago
        session_stop_time=get_test_time(-7200 + 300),  # 5 minutes later
        test_results=[
            TestResult(
                nodeid="test_api.py::test_endpoint",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-7200 + 10),
                duration=1.0,
            ),
        ],
    )

    # Session with dev environment tag
    dev_session = TestSession(
        sut_name="api",
        session_id="dev-run-789",
        session_tags={"env": "dev", "region": "eu-west"},
        session_start_time=get_test_time(-10800),  # 3 hours ago
        session_stop_time=get_test_time(-10800 + 300),  # 5 minutes later
        test_results=[
            TestResult(
                nodeid="test_api.py::test_endpoint",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-10800 + 10),
                duration=1.0,
            ),
        ],
    )

    # Create a Query instance with InMemoryStorage
    from pytest_insight.core.query import Query
    from pytest_insight.core.storage import InMemoryStorage

    # Initialize InMemoryStorage with our test sessions
    storage = InMemoryStorage(sessions=[prod_session, staging_session, dev_session])

    # Test with_session_tag
    query = Query(storage=storage)
    result = query.with_session_tag("env", "prod").execute()
    assert len(result) == 1
    assert result.sessions[0].session_id == "prod-run-123"

    query = Query(storage=storage)
    result = query.with_session_tag("region", "us-east").execute()
    assert len(result) == 1
    assert result.sessions[0].session_id == "staging-run-456"

    # Test with_session_id_pattern
    query = Query(storage=storage)
    result = query.with_session_id_pattern("prod-*").execute()
    assert len(result) == 1
    assert result.sessions[0].session_id == "prod-run-123"

    query = Query(storage=storage)
    result = query.with_session_id_pattern("*-run-*").execute()
    assert len(result) == 3
    assert {s.session_id for s in result.sessions} == {
        "prod-run-123",
        "staging-run-456",
        "dev-run-789",
    }

    # Test invalid parameters
    query = Query(storage=storage)
    with pytest.raises(InvalidQueryParameterError):
        query.with_session_tag("", "value").execute()

    with pytest.raises(InvalidQueryParameterError):
        query.with_session_id_pattern("").execute()


def test_time_based_filtering(get_test_time):
    """Test time-based filtering methods.

    This test verifies that:
        - in_last_days() correctly filters sessions from the last N days
        - in_last_hours() correctly filters sessions from the last N hours
        - after() correctly filters sessions after a given timestamp
        - before() correctly filters sessions before a given timestamp
        - Original order of matching sessions is maintained
        - Session metadata is preserved in both cases
    """
    # Create test sessions with different timestamps
    # Session 1: 10 days ago
    session1 = TestSession(
        sut_name="api",
        session_id="old-session",
        session_tags={"type": "regression"},
        session_start_time=get_test_time(-10 * 24 * 3600),  # 10 days ago
        session_stop_time=get_test_time(-10 * 24 * 3600 + 300),  # 5 minutes later
        test_results=[
            TestResult(
                nodeid="test_api.py::test_old",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-10 * 24 * 3600 + 10),
                duration=1.0,
            )
        ],
    )

    # Session 2: 1 day ago
    session2 = TestSession(
        sut_name="api",
        session_id="recent-session",
        session_tags={"type": "smoke"},
        session_start_time=get_test_time(-1 * 24 * 3600),  # 1 day ago
        session_stop_time=get_test_time(-1 * 24 * 3600 + 300),  # 5 minutes later
        test_results=[
            TestResult(
                nodeid="test_api.py::test_recent",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-1 * 24 * 3600 + 10),
                duration=1.0,
            )
        ],
    )

    # Session 3: 2 hours ago
    session3 = TestSession(
        sut_name="api",
        session_id="very-recent-session",
        session_tags={"type": "unit"},
        session_start_time=get_test_time(-2 * 3600),  # 2 hours ago
        session_stop_time=get_test_time(-2 * 3600 + 300),  # 5 minutes later
        test_results=[
            TestResult(
                nodeid="test_api.py::test_very_recent",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-2 * 3600 + 10),
                duration=1.0,
            )
        ],
    )

    # Session 4: 1 day in the future (to test the behavior of including future sessions)
    session4 = TestSession(
        sut_name="api",
        session_id="future-session",
        session_tags={"type": "future"},
        session_start_time=get_test_time(1 * 24 * 3600),  # 1 day in future
        session_stop_time=get_test_time(1 * 24 * 3600 + 300),  # 5 minutes later
        test_results=[
            TestResult(
                nodeid="test_api.py::test_future",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(1 * 24 * 3600 + 10),
                duration=1.0,
            )
        ],
    )

    # Create a Query instance with InMemoryStorage
    from pytest_insight.core.query import Query
    from pytest_insight.core.storage import InMemoryStorage

    # Initialize InMemoryStorage with our test sessions
    storage = InMemoryStorage(sessions=[session1, session2, session3, session4])
    query = Query(storage=storage)

    # Test after() with a specific timestamp
    five_days_ago = get_test_time(-5 * 24 * 3600)  # 5 days ago
    result = query.after(five_days_ago).execute()
    assert len(result) == 3
    assert result.sessions[0].session_id == "recent-session"
    assert result.sessions[1].session_id == "very-recent-session"
    assert result.sessions[2].session_id == "future-session"
    del result
    del query

    # Test before() with a specific timestamp
    query = Query(storage=storage)
    twelve_hours_future = get_test_time(12 * 3600)  # 12 hours in future
    result = query.before(twelve_hours_future).execute()
    assert len(result) == 3
    assert result.sessions[0].session_id == "old-session"
    assert result.sessions[1].session_id == "recent-session"
    assert result.sessions[2].session_id == "very-recent-session"
    del result
    del query

    # Test date_range() for a specific time range
    query = Query(storage=storage)
    start_time = get_test_time(-6 * 24 * 3600)  # 6 days ago
    end_time = get_test_time(12 * 3600)  # 12 hours in future
    result = query.date_range(start_time, end_time).execute()
    assert len(result) == 2
    assert result.sessions[0].session_id == "recent-session"
    assert result.sessions[1].session_id == "very-recent-session"


def test_pattern_based_filtering(get_test_time):
    """Test pattern-based filtering methods.

    Key aspects:
    1. Pattern-Based Filtering:
       - test_nodeid_contains() filters sessions with tests matching a pattern
       - with_pattern() filters tests by pattern in specified field
       - Both glob and regex pattern matching are supported

    2. Two-Level Filtering Design:
       - Session-level filters return complete sessions
       - Test-level filters return sessions with only matching tests
       - Session metadata is preserved in both cases
    """
    # Create test sessions with various test patterns
    api_session = TestSession(
        sut_name="api",
        session_id="api-run",
        session_tags={"component": "api"},
        session_start_time=get_test_time(-3600),  # 1 hour ago
        session_stop_time=get_test_time(-3600 + 300),  # 5 minutes later
        test_results=[
            TestResult(
                nodeid="test_api.py::test_get_endpoint",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-3600 + 10),
                duration=1.0,
                caplog="GET endpoint test",
            ),
            TestResult(
                nodeid="test_api.py::test_post_endpoint",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-3600 + 20),
                duration=1.5,
                caplog="POST endpoint test",
            ),
        ],
    )

    ui_session = TestSession(
        sut_name="ui",
        session_id="ui-run",
        session_tags={"component": "ui"},
        session_start_time=get_test_time(-7200),  # 2 hours ago
        session_stop_time=get_test_time(-7200 + 300),  # 5 minutes later
        test_results=[
            TestResult(
                nodeid="test_ui.py::test_login_page",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-7200 + 10),
                duration=2.0,
                caplog="Login page test",
            ),
            TestResult(
                nodeid="test_ui.py::test_dashboard",
                outcome=TestOutcome.FAILED,
                start_time=get_test_time(-7200 + 20),
                duration=2.5,
                caplog="Dashboard test with API integration",
            ),
        ],
    )

    # Create a Query instance with InMemoryStorage
    from pytest_insight.core.query import Query
    from pytest_insight.core.storage import InMemoryStorage

    # Initialize InMemoryStorage with our test sessions
    storage = InMemoryStorage(sessions=[api_session, ui_session])
    query = Query(storage=storage)

    # Test session-level pattern filtering with test_nodeid_contains
    result = query.test_nodeid_contains("test_api").execute()
    assert len(result) == 1
    assert result.sessions[0].session_id == "api-run"
    # All tests in the session are preserved
    assert len(result.sessions[0].test_results) == 2
    del result
    del query

    # Test substring matching at session level
    query = Query(storage=storage)
    result = query.test_nodeid_contains("get").execute()
    assert len(result) == 1
    assert result.sessions[0].session_id == "api-run"
    # All tests in the session are preserved
    assert len(result.sessions[0].test_results) == 2
    del result
    del query

    # Test test-level pattern filtering with with_pattern (field_name="nodeid")
    query = Query(storage=storage)
    result = query.filter_by_test().with_pattern("dashboard", field_name="nodeid").apply().execute()
    assert len(result) == 1
    assert result.sessions[0].session_id == "ui-run"
    # Only matching tests are included
    assert len(result.sessions[0].test_results) == 1
    assert "dashboard" in result.sessions[0].test_results[0].nodeid
    del result
    del query

    # Test pattern matching in different fields
    query = Query(storage=storage)
    result = query.filter_by_test().with_pattern("API integration", field_name="caplog").apply().execute()
    assert len(result) == 1
    assert result.sessions[0].session_id == "ui-run"
    # Only matching tests are included
    assert len(result.sessions[0].test_results) == 1
    assert "API integration" in result.sessions[0].test_results[0].caplog
    del result
    del query

    # Test regex pattern matching
    query = Query(storage=storage)
    result = (
        query.filter_by_test()
        .with_pattern("test_[a-z]+_endpoint", use_regex=True, field_name="nodeid")
        .apply()
        .execute()
    )
    assert len(result) == 1
    assert result.sessions[0].session_id == "api-run"
    # Both tests match the regex pattern
    assert len(result.sessions[0].test_results) == 2
    del result
    del query

    # Test combining multiple pattern filters
    query = Query(storage=storage)
    result = (
        query.filter_by_test()
        .with_pattern("test_", field_name="nodeid")  # All tests have this in nodeid
        .with_pattern("API", field_name="caplog")  # Only tests with "API" in caplog
        .apply()
        .execute()
    )
    assert len(result) == 1  # Only api_session has matching tests
    # Count total matching tests
    total_tests = sum(len(s.test_results) for s in result.sessions)
    assert total_tests == 1  # 2 from api_session
    del result
    del query

    # Test invalid parameters
    query = Query(storage=storage)
    with pytest.raises(InvalidQueryParameterError):
        query.test_nodeid_contains("").execute()

    query = Query(storage=storage)
    with pytest.raises(InvalidQueryParameterError):
        query.filter_by_test().with_pattern("", field_name="nodeid").apply().execute()

    query = Query(storage=storage)
    with pytest.raises(InvalidQueryParameterError):
        query.filter_by_test().with_pattern("[invalid regex", use_regex=True, field_name="nodeid").apply().execute()

    del query


def test_duration_based_filtering(get_test_time):
    """Test duration-based filtering methods.

    This test verifies that:
        - with_duration_between() correctly filters tests by duration
        - Original order of matching tests is maintained
        - Session metadata is preserved in both cases
    """
    # Create test sessions with tests of varying durations
    session1 = TestSession(
        sut_name="api",
        session_id="api-session",
        session_tags={"type": "regression"},
        session_start_time=get_test_time(-3600),  # 1 hour ago
        session_stop_time=get_test_time(-3600 + 300),  # 5 minutes later
        test_results=[
            TestResult(
                nodeid="test_api.py::test_get",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-3600 + 10),
                duration=0.5,  # Fast test
            ),
            TestResult(
                nodeid="test_api.py::test_post",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-3600 + 20),
                duration=5.0,  # Medium test
            ),
            TestResult(
                nodeid="test_api.py::test_put",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-3600 + 30),
                duration=15.0,  # Slow test
            ),
        ],
    )

    session2 = TestSession(
        sut_name="ui",
        session_id="ui-session",
        session_tags={"type": "smoke"},
        session_start_time=get_test_time(-7200),  # 2 hours ago
        session_stop_time=get_test_time(-7200 + 300),  # 5 minutes later
        test_results=[
            TestResult(
                nodeid="test_ui.py::test_login",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-7200 + 10),
                duration=1.0,  # Fast test
            ),
            TestResult(
                nodeid="test_ui.py::test_dashboard",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-7200 + 20),
                duration=10.0,  # Medium test
            ),
        ],
    )

    # Create a Query instance with InMemoryStorage
    from pytest_insight.core.query import Query
    from pytest_insight.core.storage import InMemoryStorage

    # Initialize InMemoryStorage with our test sessions
    storage = InMemoryStorage(sessions=[session1, session2])
    query = Query(storage=storage)

    # Test with_duration_between() for fast tests (< 1.0s)
    result = query.filter_by_test().with_duration_between(0.0, 1.0).apply().execute()
    assert len(result) == 2
    assert result.sessions[0].session_id == "api-session"
    assert len(result.sessions[0].test_results) == 1
    assert result.sessions[0].test_results[0].duration <= 1.0
    assert result.sessions[1].session_id == "ui-session"
    assert len(result.sessions[1].test_results) == 1
    assert result.sessions[1].test_results[0].duration <= 1.0
    del result
    del query

    # Test with_duration_between() for medium tests (1.0s - 10.0s)
    query = Query(storage=storage)
    result = query.filter_by_test().with_duration_between(1.0, 10.0).apply().execute()
    assert len(result) == 2
    assert result.sessions[0].session_id == "api-session"
    assert len(result.sessions[0].test_results) == 1
    assert 1.0 <= result.sessions[0].test_results[0].duration <= 10.0
    assert result.sessions[1].session_id == "ui-session"
    assert len(result.sessions[1].test_results) == 2  # Both tests in session2 are within range
    assert all(1.0 <= r.duration <= 10.0 for r in result.sessions[1].test_results)
    del result
    del query

    # Test with_duration_between() for slow tests (> 10.0s)
    query = Query(storage=storage)
    result = query.filter_by_test().with_duration_between(10.0, float("inf")).apply().execute()
    assert len(result) == 2
    assert result.sessions[0].session_id == "api-session"
    assert len(result.sessions[0].test_results) == 1
    assert result.sessions[0].test_results[0].duration > 10.0
    del result
    del query

    # Test invalid parameters
    query = Query(storage=storage)
    with pytest.raises(InvalidQueryParameterError):
        query.filter_by_test().with_duration_between(-1.0, 10.0).apply().execute()

    query = Query(storage=storage)
    with pytest.raises(InvalidQueryParameterError):
        query.filter_by_test().with_duration_between(5.0, 3.0).apply().execute()


def test_outcome_based_filtering(get_test_time):
    """Test outcome-based filtering methods.

    This test verifies that:
        - passed() correctly filters tests that passed
        - failed() correctly filters tests that failed
        - skipped() correctly filters tests that were skipped
        - xfailed() correctly filters tests that were expected to fail
        - Original order of matching tests is maintained
        - Session metadata is preserved in both cases
    """
    # Create test sessions with tests of varying outcomes
    # Session with mixed outcomes
    mixed_session = TestSession(
        sut_name="api",
        session_id="mixed-outcomes",
        session_tags={"type": "regression"},
        session_start_time=get_test_time(-3600),  # 1 hour ago
        session_stop_time=get_test_time(-3600 + 300),  # 5 minutes later
        test_results=[
            TestResult(
                nodeid="test_api.py::test_get",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-3600 + 10),
                duration=1.0,
            ),
            TestResult(
                nodeid="test_api.py::test_post",
                outcome=TestOutcome.FAILED,
                start_time=get_test_time(-3600 + 20),
                duration=1.5,
            ),
            TestResult(
                nodeid="test_api.py::test_put",
                outcome=TestOutcome.SKIPPED,
                start_time=get_test_time(-3600 + 30),
                duration=0.1,
            ),
            TestResult(
                nodeid="test_api.py::test_delete",
                outcome=TestOutcome.XFAILED,
                start_time=get_test_time(-3600 + 40),
                duration=0.5,
            ),
        ],
    )

    # Session with only passed tests
    passed_session = TestSession(
        sut_name="ui",
        session_id="passed-tests",
        session_tags={"type": "smoke"},
        session_start_time=get_test_time(-7200),  # 2 hours ago
        session_stop_time=get_test_time(-7200 + 300),  # 5 minutes later
        test_results=[
            TestResult(
                nodeid="test_ui.py::test_login",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-7200 + 10),
                duration=1.0,
            ),
            TestResult(
                nodeid="test_ui.py::test_dashboard",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-7200 + 20),
                duration=0.8,
            ),
        ],
    )

    # Session with only failed tests
    failed_session = TestSession(
        sut_name="database",
        session_id="failed-tests",
        session_tags={"type": "integration"},
        session_start_time=get_test_time(-10800),  # 3 hours ago
        session_stop_time=get_test_time(-10800 + 300),  # 5 minutes later
        test_results=[
            TestResult(
                nodeid="test_db.py::test_migration",
                outcome=TestOutcome.FAILED,
                start_time=get_test_time(-10800 + 10),
                duration=2.0,
            ),
            TestResult(
                nodeid="test_db.py::test_backup",
                outcome=TestOutcome.FAILED,
                start_time=get_test_time(-10800 + 20),
                duration=3.0,
            ),
        ],
    )

    # Create a Query instance with InMemoryStorage
    storage = InMemoryStorage(sessions=[mixed_session, passed_session, failed_session])
    query = Query(storage=storage)

    # Test passed() - should return tests that passed
    result = query.with_outcome(TestOutcome.PASSED).execute()
    assert len(result) == 2
    assert result.sessions[0].session_id == "mixed-outcomes"
    assert len([r for r in result.sessions[0].test_results if r.outcome == TestOutcome.PASSED]) == 1
    assert result.sessions[1].session_id == "passed-tests"
    assert len([r for r in result.sessions[1].test_results if r.outcome == TestOutcome.PASSED]) == 2
    del query
    del result

    # Test failed() - should return tests that failed
    query = Query(storage=storage)
    result = query.with_outcome(TestOutcome.FAILED).execute()
    assert len(result) == 2
    assert result.sessions[0].session_id == "mixed-outcomes"
    assert len([r for r in result.sessions[0].test_results if r.outcome == TestOutcome.FAILED]) == 1
    assert result.sessions[1].session_id == "failed-tests"
    assert len([r for r in result.sessions[1].test_results if r.outcome == TestOutcome.FAILED]) == 2
    del query
    del result

    # Test skipped() - should return tests that were skipped
    query = Query(storage=storage)
    result = query.with_outcome(TestOutcome.SKIPPED).execute()
    assert len(result) == 1
    assert result.sessions[0].session_id == "mixed-outcomes"
    assert len([r for r in result.sessions[0].test_results if r.outcome == TestOutcome.SKIPPED]) == 1
    del query
    del result

    # Test xfailed() - should return tests that were expected to fail
    query = Query(storage=storage)
    result = query.with_outcome(TestOutcome.XFAILED).execute()
    assert len(result) == 1
    assert result.sessions[0].session_id == "mixed-outcomes"
    assert len([r for r in result.sessions[0].test_results if r.outcome == TestOutcome.XFAILED]) == 1
    del query
    del result

    # Test combining outcome filters
    query = Query(storage=storage)
    result = query.with_outcome(TestOutcome.PASSED).with_outcome(TestOutcome.FAILED).execute()
    assert len(result) == 1
    assert result.sessions[0].session_id == "mixed-outcomes"
    assert (
        len([r for r in result.sessions[0].test_results if r.outcome in [TestOutcome.PASSED, TestOutcome.FAILED]]) == 2
    )
    del query
    del result
