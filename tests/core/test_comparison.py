"""
Unit tests for comparison utilities (compare_suts) in pytest-insight.
Covers output structure, correct mapping, and edge cases.
"""

from datetime import datetime

from pytest_insight.core.comparison import compare_suts
from pytest_insight.core.models import TestOutcome, TestResult, TestSession


def make_session(sut_name, test_results, session_id):
    t0 = datetime(2025, 4, 21, 10, 0, 0)
    t1 = t0
    return TestSession(
        sut_name=sut_name,
        session_id=session_id,
        session_start_time=t0,
        session_stop_time=t1,
        test_results=test_results,
    )


def test_compare_suts_output_structure():
    sessions = []
    result = compare_suts(sessions, "sutA", "sutB")
    assert isinstance(result, dict)
    assert set(result.keys()) == {"sutA", "sutB"}


def test_compare_suts_with_sessions():
    tests_a = [
        TestResult(
            nodeid="test_foo",
            outcome=TestOutcome.PASSED,
            start_time=datetime(2025, 4, 21, 10, 0, 0),
            duration=1.0,
        )
    ]
    tests_b = [
        TestResult(
            nodeid="test_bar",
            outcome=TestOutcome.FAILED,
            start_time=datetime(2025, 4, 21, 10, 0, 0),
            duration=1.0,
        )
    ]
    sessions = [
        make_session("sutA", tests_a, "sess1"),
        make_session("sutB", tests_b, "sess2"),
    ]
    result = compare_suts(sessions, "sutA", "sutB")
    assert set(result.keys()) == {"sutA", "sutB"}
    assert isinstance(result["sutA"], float)
    assert isinstance(result["sutB"], float)


def test_compare_suts_edge_cases():
    # Unknown SUTs
    sessions = []
    result = compare_suts(sessions, "unknownA", "unknownB")
    assert set(result.keys()) == {"unknownA", "unknownB"}
    # SUTs with no sessions
    tests = [
        TestResult(
            nodeid="test_foo",
            outcome=TestOutcome.PASSED,
            start_time=datetime(2025, 4, 21, 10, 0, 0),
            duration=1.0,
        )
    ]
    sessions = [make_session("sutA", tests, "sess1")]
    result = compare_suts(sessions, "sutA", "sutB")
    assert set(result.keys()) == {"sutA", "sutB"}
