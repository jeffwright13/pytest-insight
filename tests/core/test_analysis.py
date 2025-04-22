"""
Unit tests for analysis utilities (calculate_reliability) in pytest-insight.
Covers correct calculation, edge cases, and error handling.
"""
from datetime import datetime

from pytest_insight.core.analysis import calculate_reliability
from pytest_insight.core.models import TestOutcome, TestResult, TestSession


def make_session(test_results, session_id="sess1"):
    t0 = datetime(2025, 4, 21, 10, 0, 0)
    t1 = t0
    return TestSession(
        sut_name="service-a",
        session_id=session_id,
        session_start_time=t0,
        session_stop_time=t1,
        test_results=test_results,
    )


def test_calculate_reliability_all_passed():
    tests = [
        TestResult(
            nodeid="test_foo", outcome=TestOutcome.PASSED, start_time=datetime(2025, 4, 21, 10, 0, 0), duration=1.0
        )
    ]
    sessions = [make_session(tests)]
    assert calculate_reliability(sessions) == 1.0


def test_calculate_reliability_some_failed():
    tests1 = [
        TestResult(
            nodeid="test_foo", outcome=TestOutcome.PASSED, start_time=datetime(2025, 4, 21, 10, 0, 0), duration=1.0
        )
    ]
    tests2 = [
        TestResult(
            nodeid="test_foo", outcome=TestOutcome.FAILED, start_time=datetime(2025, 4, 21, 11, 0, 0), duration=1.0
        )
    ]
    sessions = [make_session(tests1, "sess1"), make_session(tests2, "sess2")]
    assert calculate_reliability(sessions) == 0.5


def test_calculate_reliability_multiple_tests():
    t0 = datetime(2025, 4, 21, 10, 0, 0)
    t1 = datetime(2025, 4, 21, 11, 0, 0)
    tests1 = [
        TestResult(nodeid="test_foo", outcome=TestOutcome.PASSED, start_time=t0, duration=1.0),
        TestResult(nodeid="test_bar", outcome=TestOutcome.FAILED, start_time=t0, duration=1.0),
    ]
    tests2 = [
        TestResult(nodeid="test_foo", outcome=TestOutcome.PASSED, start_time=t1, duration=1.0),
        TestResult(nodeid="test_bar", outcome=TestOutcome.PASSED, start_time=t1, duration=1.0),
    ]
    sessions = [make_session(tests1, "sess1"), make_session(tests2, "sess2")]
    # test_foo: 2/2 passed, test_bar: 1/2 passed => (2+1)/(2+2)=0.75
    assert calculate_reliability(sessions) == 0.75


def test_calculate_reliability_empty():
    assert calculate_reliability([]) == 0.0


def test_calculate_reliability_no_tests():
    session = make_session([])
    assert calculate_reliability([session]) == 0.0
