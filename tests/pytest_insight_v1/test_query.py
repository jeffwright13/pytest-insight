import uuid

import pytest
from pytest_insight.core.models import TestOutcome, TestResult, TestSession
from pytest_insight.core.query import InvalidQueryParameterError, Query
from pytest_insight.core.storage import ProfileManager, get_storage_instance

# All tests in this file use test_profile_name as the profile argument for Query. If any test profile setup is needed, use create_test_profile.
# Example (add to setup if needed):
# create_test_profile(name=test_profile_name, file_path="/tmp/test-profile.json", profiles_path="/tmp/profiles.json")


def test_session_with_tags(get_test_time, monkeypatch):
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

    # Create a profile manager and a test profile
    profile_manager = ProfileManager()

    # Create a test profile with in-memory storage
    test_profile_name = f"test-tags-profile-{uuid.uuid4().hex[:8]}"
    profile_manager._create_profile(test_profile_name, "memory")

    # Mock get_profile_manager to return our test instance
    monkeypatch.setattr("pytest_insight.core.storage.get_profile_manager", lambda: profile_manager)

    # Get the storage instance and add our test sessions
    storage = get_storage_instance(profile_name=test_profile_name)
    storage.save_session(prod_session)
    storage.save_session(staging_session)
    storage.save_session(dev_session)

    # Create a list of all sessions for testing
    all_sessions = [prod_session, staging_session, dev_session]

    # Test with_session_tag() - filter by environment tag
    query = Query(profile_name=test_profile_name)
    result = query.with_session_tag("env", "prod").execute(sessions=all_sessions)
    assert len(result) == 1
    assert result.sessions[0].session_id == "prod-run-123"
    assert result.sessions[0].session_tags["env"] == "prod"
    assert len(result.sessions[0].test_results) == 1  # All tests are preserved

    # Test with_session_tag() - filter by region tag
    query = Query(profile_name=test_profile_name)
    result = query.with_session_tag("region", "us-east").execute(sessions=all_sessions)
    assert len(result) == 1
    assert result.sessions[0].session_id == "staging-run-456"
    assert result.sessions[0].session_tags["region"] == "us-east"
    assert len(result.sessions[0].test_results) == 1  # All tests are preserved

    # Test with_session_id_pattern() - filter by ID pattern
    query = Query(profile_name=test_profile_name)
    result = query.with_session_id_pattern("*-run-*").execute(sessions=all_sessions)
    assert len(result) == 3
    assert {s.session_id for s in result.sessions} == {
        "prod-run-123",
        "staging-run-456",
        "dev-run-789",
    }
    assert all(len(s.test_results) == 1 for s in result.sessions)  # All tests are preserved

    # Test with_session_id_pattern() - filter by specific ID pattern
    query = Query(profile_name=test_profile_name)
    result = query.with_session_id_pattern("dev-*").execute(sessions=all_sessions)
    assert len(result) == 1
    assert result.sessions[0].session_id == "dev-run-789"
    assert len(result.sessions[0].test_results) == 1  # All tests are preserved

    # Test combining filters - prod environment in us-west region
    query = Query(profile_name=test_profile_name)
    result = query.with_session_tag("env", "prod").with_session_tag("region", "us-west").execute(sessions=all_sessions)
    assert len(result) == 1
    assert result.sessions[0].session_id == "prod-run-123"
    assert result.sessions[0].session_tags["env"] == "prod"
    assert result.sessions[0].session_tags["region"] == "us-west"
    assert len(result.sessions[0].test_results) == 1  # All tests are preserved

    # Test combining filters with OR - sessions in prod OR staging environment
    query = Query(profile_name=test_profile_name)
    result = (
        query.with_session_tag("env", "prod")
        .with_session_tag("env", "staging", combine_with_or=True)
        .execute(sessions=all_sessions)
    )
    assert len(result) == 2
    assert {s.session_id for s in result.sessions} == {
        "prod-run-123",
        "staging-run-456",
    }

    # Test invalid parameters
    query = Query(profile_name=test_profile_name)
    with pytest.raises(InvalidQueryParameterError):
        query.with_session_tag("", "value").execute(sessions=all_sessions)

    with pytest.raises(InvalidQueryParameterError):
        query.with_session_id_pattern("").execute(sessions=all_sessions)


def test_time_based_filtering(get_test_time, monkeypatch):
    """Test time-based filtering methods.

    This test verifies that:
        - before() correctly filters sessions that started before a given time
        - after() correctly filters sessions that started after a given time
        - between() correctly filters sessions that started between two times
        - Original order of matching sessions is maintained
        - Session metadata is preserved in both cases
    """
    # Create test sessions with different start times
    # Session from 1 hour ago
    recent_session = TestSession(
        sut_name="api",
        session_id="recent-run",
        session_tags={"type": "smoke"},
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

    # Session from 1 day ago
    day_old_session = TestSession(
        sut_name="api",
        session_id="day-old-run",
        session_tags={"type": "regression"},
        session_start_time=get_test_time(-86400),  # 1 day ago
        session_stop_time=get_test_time(-86400 + 300),  # 5 minutes later
        test_results=[
            TestResult(
                nodeid="test_api.py::test_endpoint",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-86400 + 10),
                duration=1.0,
            ),
        ],
    )

    # Session from 1 week ago
    week_old_session = TestSession(
        sut_name="api",
        session_id="week-old-run",
        session_tags={"type": "full"},
        session_start_time=get_test_time(-604800),  # 1 week ago
        session_stop_time=get_test_time(-604800 + 300),  # 5 minutes later
        test_results=[
            TestResult(
                nodeid="test_api.py::test_endpoint",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-604800 + 10),
                duration=1.0,
            ),
        ],
    )

    # Create a profile manager and a test profile
    profile_manager = ProfileManager()

    # Create a test profile with in-memory storage
    test_profile_name = f"test-time-profile-{uuid.uuid4().hex[:8]}"
    profile_manager._create_profile(test_profile_name, "memory")

    # Mock get_profile_manager to return our test instance
    monkeypatch.setattr("pytest_insight.core.storage.get_profile_manager", lambda: profile_manager)

    # Get the storage instance and add our test sessions
    storage = get_storage_instance(profile_name=test_profile_name)
    storage.save_session(recent_session)
    storage.save_session(day_old_session)
    storage.save_session(week_old_session)

    # Create a list of all sessions for testing
    all_sessions = [recent_session, day_old_session, week_old_session]

    # Test before() - sessions before 12 hours ago
    twelve_hours_ago = get_test_time(-43200)  # 12 hours ago
    query = Query(profile_name=test_profile_name)
    result = query.before(twelve_hours_ago).execute(sessions=all_sessions)
    assert len(result) == 2
    assert [s.session_id for s in result.sessions] == ["day-old-run", "week-old-run"]

    # Test after() - sessions after 2 days ago
    two_days_ago = get_test_time(-172800)  # 2 days ago
    query = Query(profile_name=test_profile_name)
    result = query.after(two_days_ago).execute(sessions=all_sessions)
    assert len(result) == 2
    assert [s.session_id for s in result.sessions] == ["recent-run", "day-old-run"]

    # Test between() - sessions between 2 days ago and 12 hours ago
    query = Query(profile_name=test_profile_name)
    result = query.between(two_days_ago, twelve_hours_ago).execute(sessions=all_sessions)
    assert len(result) == 1
    assert result.sessions[0].session_id == "day-old-run"

    # Test combining filters - sessions before 12 hours ago AND with tag type=full
    query = Query(profile_name=test_profile_name)
    result = query.before(twelve_hours_ago).with_session_tag("type", "full").execute(sessions=all_sessions)
    assert len(result) == 1
    assert result.sessions[0].session_id == "week-old-run"


def test_pattern_based_filtering(get_test_time, monkeypatch):
    """Test pattern-based filtering methods.

    This test verifies that:
        - test_nodeid_contains() correctly filters tests by nodeid pattern
        - with_session_id_pattern() correctly filters sessions by ID pattern
        - Original order of matching sessions is maintained
        - Session metadata is preserved
    """
    # Create sessions with different test nodeids
    # Session with API tests
    api_session = TestSession(
        sut_name="api",
        session_id="api-run-123",
        session_start_time=get_test_time(-3600),  # 1 hour ago
        session_stop_time=get_test_time(-3600 + 300),  # 5 minutes later
        test_results=[
            TestResult(
                nodeid="test_api.py::test_get_endpoint",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-3600 + 10),
                duration=1.0,
            ),
            TestResult(
                nodeid="test_api.py::test_post_endpoint",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-3600 + 20),
                duration=1.2,
            ),
            TestResult(
                nodeid="test_api.py::test_delete_endpoint",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-3600 + 30),
                duration=0.8,
            ),
        ],
    )

    # Session with UI tests
    ui_session = TestSession(
        sut_name="ui",
        session_id="ui-run-456",
        session_start_time=get_test_time(-7200),  # 2 hours ago
        session_stop_time=get_test_time(-7200 + 300),  # 5 minutes later
        test_results=[
            TestResult(
                nodeid="test_ui.py::test_login_page",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-7200 + 10),
                duration=1.5,
            ),
            TestResult(
                nodeid="test_ui.py::test_dashboard_page",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-7200 + 20),
                duration=2.0,
            ),
        ],
    )

    # Session with database tests
    db_session = TestSession(
        sut_name="database",
        session_id="db-run-789",
        session_start_time=get_test_time(-10800),  # 3 hours ago
        session_stop_time=get_test_time(-10800 + 300),  # 5 minutes later
        test_results=[
            TestResult(
                nodeid="test_db.py::test_connection",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-10800 + 10),
                duration=0.5,
            ),
            TestResult(
                nodeid="test_db.py::test_query_performance",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-10800 + 20),
                duration=3.0,
            ),
        ],
    )

    # Create a profile manager and a test profile
    profile_manager = ProfileManager()

    # Create a test profile with in-memory storage
    test_profile_name = f"test-pattern-profile-{uuid.uuid4().hex[:8]}"
    profile_manager._create_profile(test_profile_name, "memory")

    # Mock get_profile_manager to return our test instance
    monkeypatch.setattr("pytest_insight.core.storage.get_profile_manager", lambda: profile_manager)

    # Get the storage instance and add our test sessions
    storage = get_storage_instance(profile_name=test_profile_name)
    storage.save_session(api_session)
    storage.save_session(ui_session)
    storage.save_session(db_session)

    # Create a list of all sessions for testing
    all_sessions = [api_session, ui_session, db_session]

    # Test test_nodeid_contains() - filter API tests
    query = Query(profile_name=test_profile_name)
    result = query.test_nodeid_contains("test_api.py").execute(sessions=all_sessions)
    assert len(result) == 1
    assert result.sessions[0].session_id == "api-run-123"
    assert len(result.sessions[0].test_results) == 3

    # Test test_nodeid_contains() - filter UI tests
    query = Query(profile_name=test_profile_name)
    result = query.test_nodeid_contains("test_ui.py").execute(sessions=all_sessions)
    assert len(result) == 1
    assert result.sessions[0].session_id == "ui-run-456"
    assert len(result.sessions[0].test_results) == 2

    # Test filter_by_test() with pattern - filter specific test
    query = Query(profile_name=test_profile_name)
    result = (
        query.filter_by_test().with_nodeid_containing("test_query_performance").apply().execute(sessions=all_sessions)
    )
    assert len(result) == 1
    assert result.sessions[0].session_id == "db-run-789"
    assert len(result.sessions[0].test_results) == 1
    assert result.sessions[0].test_results[0].nodeid == "test_db.py::test_query_performance"

    # Test with_session_id_pattern() - filter by session ID pattern
    query = Query(profile_name=test_profile_name)
    result = query.with_session_id_pattern("*-run-*").execute(sessions=all_sessions)
    assert len(result) == 3
    assert {s.session_id for s in result.sessions} == {
        "api-run-123",
        "ui-run-456",
        "db-run-789",
    }

    # Test combining filters - API tests with specific pattern
    query = Query(profile_name=test_profile_name)
    result = query.test_nodeid_contains("test_api.py").execute(sessions=all_sessions)
    assert len(result) == 1
    assert result.sessions[0].session_id == "api-run-123"
    assert len(result.sessions[0].test_results) == 3  # All tests match the pattern


def test_duration_based_filtering(get_test_time, monkeypatch):
    """Test duration-based filtering methods.

    This test verifies that:
        - filter_by_test() with duration filters correctly filters tests by duration
        - Original order of matching sessions is maintained
        - Session metadata is preserved
    """
    # Create sessions with tests of different durations
    # Session with mixed duration tests
    mixed_duration_session = TestSession(
        sut_name="api",
        session_id="mixed-duration-run",
        session_start_time=get_test_time(-3600),  # 1 hour ago
        session_stop_time=get_test_time(-3600 + 300),  # 5 minutes later
        test_results=[
            TestResult(
                nodeid="test_api.py::test_fast",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-3600 + 10),
                duration=0.5,  # Fast test
            ),
            TestResult(
                nodeid="test_api.py::test_medium",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-3600 + 20),
                duration=2.0,  # Medium test
            ),
            TestResult(
                nodeid="test_api.py::test_slow",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-3600 + 30),
                duration=5.0,  # Slow test
            ),
        ],
    )

    # Session with only fast tests
    fast_tests_session = TestSession(
        sut_name="ui",
        session_id="fast-tests-run",
        session_start_time=get_test_time(-7200),  # 2 hours ago
        session_stop_time=get_test_time(-7200 + 300),  # 5 minutes later
        test_results=[
            TestResult(
                nodeid="test_ui.py::test_login",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-7200 + 10),
                duration=0.3,  # Fast test
            ),
            TestResult(
                nodeid="test_ui.py::test_dashboard",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-7200 + 20),
                duration=0.7,  # Fast test
            ),
        ],
    )

    # Session with only slow tests
    slow_tests_session = TestSession(
        sut_name="database",
        session_id="slow-tests-run",
        session_start_time=get_test_time(-10800),  # 3 hours ago
        session_stop_time=get_test_time(-10800 + 300),  # 5 minutes later
        test_results=[
            TestResult(
                nodeid="test_db.py::test_migration",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-10800 + 10),
                duration=4.0,  # Slow test
            ),
            TestResult(
                nodeid="test_db.py::test_backup",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(-10800 + 20),
                duration=6.0,  # Very slow test
            ),
        ],
    )

    # Create a profile manager and a test profile
    profile_manager = ProfileManager()

    # Create a test profile with in-memory storage
    test_profile_name = f"test-duration-profile-{uuid.uuid4().hex[:8]}"
    profile_manager._create_profile(test_profile_name, "memory")

    # Mock get_profile_manager to return our test instance
    monkeypatch.setattr("pytest_insight.core.storage.get_profile_manager", lambda: profile_manager)

    # Get the storage instance and add our test sessions
    storage = get_storage_instance(profile_name=test_profile_name)
    storage.save_session(mixed_duration_session)
    storage.save_session(fast_tests_session)
    storage.save_session(slow_tests_session)

    # Create a list of all sessions for testing
    all_sessions = [mixed_duration_session, fast_tests_session, slow_tests_session]

    # Test filter_by_test() with duration between - tests with duration between 1 and 3 seconds
    query = Query(profile_name=test_profile_name)
    result = query.filter_by_test().with_duration_between(1.0, 3.0).apply().execute(sessions=all_sessions)
    assert len(result) == 1  # Only mixed_duration_session has tests in the 1-3 second range
    assert result.sessions[0].session_id == "mixed-duration-run"
    # Check that only tests within the duration range are included
    assert len(result.sessions[0].test_results) == 1  # Only the medium test
    assert result.sessions[0].test_results[0].nodeid == "test_api.py::test_medium"

    # Test filter_by_test() with duration between - tests with duration between 3 and 5 seconds
    query = Query(profile_name=test_profile_name)
    result = query.filter_by_test().with_duration_between(3.0, 5.0).apply().execute(sessions=all_sessions)
    assert len(result) == 2
    assert {s.session_id for s in result.sessions} == {
        "mixed-duration-run",
        "slow-tests-run",
    }
    # Check that only tests within the duration range are included
    assert len(result.sessions[0].test_results) == 1  # Only the slow test
    assert result.sessions[0].test_results[0].nodeid == "test_api.py::test_slow"
    assert len(result.sessions[1].test_results) == 1  # Only the migration test
    assert result.sessions[1].test_results[0].nodeid == "test_db.py::test_migration"

    # Test filter_by_test() with custom filter - tests with duration > 4 seconds
    query = Query(profile_name=test_profile_name)
    result = (
        query.filter_by_test()
        .with_custom_filter(lambda test: test.duration > 4.0, "duration_greater_than_4")
        .apply()
        .execute(sessions=all_sessions)
    )
    assert len(result) == 2
    assert {s.session_id for s in result.sessions} == {
        "mixed-duration-run",
        "slow-tests-run",
    }
    # Check that only tests with duration > 4 seconds are included
    assert len(result.sessions[0].test_results) == 1  # Only the slow test
    assert result.sessions[0].test_results[0].nodeid == "test_api.py::test_slow"
    assert len(result.sessions[1].test_results) == 1  # Only the backup test
    assert result.sessions[1].test_results[0].nodeid == "test_db.py::test_backup"

    # Test filter_by_test() with custom filter - tests with duration < 1 second
    query = Query(profile_name=test_profile_name)
    result = (
        query.filter_by_test()
        .with_custom_filter(lambda test: test.duration < 1.0, "duration_less_than_1")
        .apply()
        .execute(sessions=all_sessions)
    )
    assert len(result) == 2
    assert {s.session_id for s in result.sessions} == {
        "mixed-duration-run",
        "fast-tests-run",
    }
    # Check that only tests with duration < 1 second are included
    assert len(result.sessions[0].test_results) == 1  # Only the fast test
    assert result.sessions[0].test_results[0].nodeid == "test_api.py::test_fast"
    assert len(result.sessions[1].test_results) == 2  # Both fast tests
    assert {t.nodeid for t in result.sessions[1].test_results} == {
        "test_ui.py::test_login",
        "test_ui.py::test_dashboard",
    }


def test_outcome_based_filtering(get_test_time, monkeypatch):
    """Test outcome-based filtering methods.

    This test verifies that:
        - with_outcome() correctly filters tests by outcome
        - Original order of matching sessions is maintained
        - Session metadata is preserved
    """
    # Create sessions with tests of different outcomes
    # Session with mixed outcomes
    mixed_session = TestSession(
        sut_name="api",
        session_id="mixed-outcomes-run",
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
        session_id="passed-tests-run",
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
        session_id="failed-tests-run",
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

    # Create a profile manager and a test profile
    profile_manager = ProfileManager()

    # Create a test profile with in-memory storage
    test_profile_name = f"test-outcome-profile-{uuid.uuid4().hex[:8]}"
    profile_manager._create_profile(test_profile_name, "memory")

    # Mock get_profile_manager to return our test instance
    monkeypatch.setattr("pytest_insight.core.storage.get_profile_manager", lambda: profile_manager)

    # Get the storage instance and add our test sessions
    storage = get_storage_instance(profile_name=test_profile_name)
    storage.save_session(mixed_session)
    storage.save_session(passed_session)
    storage.save_session(failed_session)

    # Create a list of all sessions for testing
    all_sessions = [mixed_session, passed_session, failed_session]

    # Test with_outcome() - should return tests that passed
    query = Query(profile_name=test_profile_name)
    result = query.with_outcome(TestOutcome.PASSED).execute(sessions=all_sessions)
    assert len(result) == 2
    assert {s.session_id for s in result.sessions} == {
        "mixed-outcomes-run",
        "passed-tests-run",
    }
    # Check that only passed tests are included
    assert len(result.sessions[0].test_results) == 1  # Only the passed test from mixed_session
    assert result.sessions[0].test_results[0].outcome == TestOutcome.PASSED
    assert len(result.sessions[1].test_results) == 2
    assert all(t.outcome == TestOutcome.PASSED for t in result.sessions[1].test_results)

    # Test with_outcome() - should return tests that failed
    query = Query(profile_name=test_profile_name)
    result = query.with_outcome(TestOutcome.FAILED).execute(sessions=all_sessions)
    assert len(result) == 2
    assert {s.session_id for s in result.sessions} == {
        "mixed-outcomes-run",
        "failed-tests-run",
    }
    # Check that only failed tests are included
    assert len(result.sessions[0].test_results) == 1
    assert result.sessions[0].test_results[0].outcome == TestOutcome.FAILED
    assert len(result.sessions[1].test_results) == 2
    assert all(t.outcome == TestOutcome.FAILED for t in result.sessions[1].test_results)

    # Test with_outcome() - should return tests that were skipped
    query = Query(profile_name=test_profile_name)
    result = query.with_outcome(TestOutcome.SKIPPED).execute(sessions=all_sessions)
    assert len(result) == 1
    assert result.sessions[0].session_id == "mixed-outcomes-run"
    assert len(result.sessions[0].test_results) == 1
    assert result.sessions[0].test_results[0].outcome == TestOutcome.SKIPPED

    # Test with_outcome() - should return tests that were xfailed
    query = Query(profile_name=test_profile_name)
    result = query.with_outcome(TestOutcome.XFAILED).execute(sessions=all_sessions)
    assert len(result) == 1
    assert result.sessions[0].session_id == "mixed-outcomes-run"
    assert len(result.sessions[0].test_results) == 1
    assert result.sessions[0].test_results[0].outcome == TestOutcome.XFAILED

    # Test combining filters - passed tests in smoke test sessions
    query = Query(profile_name=test_profile_name)
    result = query.with_outcome(TestOutcome.PASSED).with_session_tag("type", "smoke").execute(sessions=all_sessions)
    assert len(result) == 1
    assert result.sessions[0].session_id == "passed-tests-run"
    assert len(result.sessions[0].test_results) == 2
