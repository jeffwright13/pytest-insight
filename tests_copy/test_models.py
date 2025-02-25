from datetime import datetime, timedelta

from pytest_insight.models import (
    RerunTestGroup,
    TestHistory,
    TestResult,
    TestSession,
)


def test_random_test_results(random_test_result):
    """Test random test result properties."""
    assert random_test_result.nodeid != ""
    assert isinstance(random_test_result.nodeid, str)
    assert random_test_result.outcome in [
        "PASSED",
        "FAILED",
        "SKIPPED",
        "XFAILED",
        "XPASSED",
        "RERUN",
        "ERROR",
    ]
    assert isinstance(random_test_result.start_time, datetime)
    assert isinstance(random_test_result.duration, float)
    assert isinstance(random_test_result.has_warning, bool)

    # Fields that can be empty but must be strings
    assert isinstance(random_test_result.caplog, str)
    assert isinstance(random_test_result.capstderr, str)
    assert isinstance(random_test_result.capstdout, str)
    assert isinstance(random_test_result.longreprtext, str)


def test_random_test_session(random_test_session):
    """Test random test session properties and methods."""
    assert isinstance(random_test_session.sut_name, str) and random_test_session.sut_name.startswith("SUT-")
    assert isinstance(random_test_session.session_id, str) and random_test_session.session_id.startswith("session-")

    assert isinstance(random_test_session.session_start_time, datetime)
    assert isinstance(random_test_session.session_stop_time, datetime)
    assert isinstance(random_test_session.session_duration, timedelta)
    assert random_test_session.session_stop_time > random_test_session.session_start_time

    # Ensure test results and rerun groups are populated
    assert len(random_test_session.test_results) >= 2
    assert len(random_test_session.rerun_test_groups) >= 1

    # Test outcome categorization
    outcomes = {test.outcome for test in random_test_session.test_results}
    warnings = any(test.has_warning for test in random_test_session.test_results)

    # Verify we have at least one test result with a meaningful outcome
    assert any(
        [
            "PASSED" in outcomes,
            "FAILED" in outcomes,
            "SKIPPED" in outcomes,
            "XFAILED" in outcomes,
            "XPASSED" in outcomes,
            "RERUN" in outcomes,
            "ERROR" in outcomes,
            warnings,
        ]
    )


def test_test_session():
    """Test basic TestSession functionality."""
    start_time = datetime.utcnow()
    stop_time = start_time + timedelta(seconds=10)

    session = TestSession(
        sut_name="SUT-1",
        session_id="session-123",
        session_start_time=start_time,
        session_stop_time=stop_time,
    )

    # Add test results
    for _ in range(5):
        session.add_test_result(
            TestResult(
                nodeid="test_pass",
                outcome="PASSED",
                start_time=start_time,
                duration=0.1,
            )
        )

    assert len(session.test_results) == 5
    assert session.session_duration.total_seconds() == 10.0


def test_rerun_test_group():
    """Test RerunTestGroup functionality."""
    group = RerunTestGroup("test_example.py::test_case", "FAILED")
    now = datetime.utcnow()

    result1 = TestResult(
        nodeid="test_example.py::test_case",
        outcome="FAILED",
        start_time=now,
        duration=0.5,
    )
    result2 = TestResult(
        nodeid="test_example.py::test_case",
        outcome="PASSED",
        start_time=now + timedelta(seconds=1),
        duration=0.7,
    )

    # Use proper methods to add results
    group.add_rerun(result1)
    group.add_test(result1)
    group.add_test(result2)

    assert group.nodeid == "test_example.py::test_case"
    assert group.final_outcome == "FAILED"
    assert group.final_test == result2
    assert len(group.reruns) == 1
    assert len(group.full_test_list) == 2


def test_history():
    """Test TestHistory functionality."""
    history = TestHistory()
    now = datetime.utcnow()
    stop_time1 = now + timedelta(seconds=5)
    stop_time2 = now + timedelta(seconds=20)

    session1 = TestSession("SUT-1", "session-001", now, stop_time1, [], [])
    session2 = TestSession("SUT-1", "session-002", now + timedelta(seconds=10), stop_time2, [], [])

    history.add_test_session(session1)
    history.add_test_session(session2)

    assert len(history.sessions) == 2
    assert history.latest_session() == session2


def test_test_result_timing_calculations():
    """Test that timing values are calculated correctly on initialization."""
    now = datetime.now()

    # Test initialization with duration
    result1 = TestResult(
        nodeid="test_example.py::test_case",
        outcome="PASSED",
        start_time=now,
        duration=5.0,
    )
    assert result1.stop_time == now + timedelta(seconds=5.0)
    assert result1.duration == 5.0

    # Test initialization with stop_time
    stop_time = now + timedelta(seconds=10.0)
    result2 = TestResult(
        nodeid="test_example.py::test_case",
        outcome="PASSED",
        start_time=now,
        stop_time=stop_time,
    )
    assert result2.stop_time == stop_time
    assert result2.duration == 10.0
