"""
Unit tests for core models: TestOutcome, TestResult, RerunTestGroup, TestSession.
Covers enum conversion, serialization, context preservation, and error handling.
"""
import pytest
from datetime import datetime, timedelta
from pytest_insight.core.models import TestOutcome, TestResult, RerunTestGroup, TestSession

def test_testoutcome_from_str_and_to_str():
    assert TestOutcome.from_str("passed") == TestOutcome.PASSED
    assert TestOutcome.from_str("FAILED") == TestOutcome.FAILED
    assert TestOutcome.from_str(None) == TestOutcome.SKIPPED
    with pytest.raises(ValueError):
        TestOutcome.from_str("not_a_real_outcome")
    assert TestOutcome.PASSED.to_str() == "passed"
    assert set(TestOutcome.to_list()) == {"passed", "failed", "skipped", "xfailed", "xpassed", "rerun", "error"}
    assert TestOutcome.FAILED.is_failed() is True
    assert TestOutcome.PASSED.is_failed() is False

def test_testresult_init_and_serialization():
    t0 = datetime(2025, 4, 21, 10, 0, 0)
    t1 = t0 + timedelta(seconds=2)
    # Only duration provided
    tr1 = TestResult(nodeid="test_foo", outcome=TestOutcome.PASSED, start_time=t0, duration=2.0)
    assert tr1.stop_time == t1
    # Only stop_time provided
    tr2 = TestResult(nodeid="test_bar", outcome=TestOutcome.FAILED, start_time=t0, stop_time=t1)
    assert tr2.duration == 2.0
    # Both provided
    tr3 = TestResult(nodeid="test_baz", outcome=TestOutcome.SKIPPED, start_time=t0, stop_time=t1, duration=2.0)
    assert tr3.duration == 2.0 and tr3.stop_time == t1
    # Serialization
    d = tr1.to_dict()
    tr1_restored = TestResult.from_dict(d)
    assert tr1_restored.nodeid == "test_foo"
    assert tr1_restored.outcome == TestOutcome.PASSED
    assert tr1_restored.duration == 2.0

def test_testresult_invalid_init():
    t0 = datetime(2025, 4, 21, 10, 0, 0)
    with pytest.raises(ValueError):
        TestResult(nodeid="test_fail", outcome=TestOutcome.PASSED, start_time=t0)

def test_reruntestgroup_add_and_final_outcome():
    t0 = datetime(2025, 4, 21, 10, 0, 0)
    tr1 = TestResult(nodeid="test_foo", outcome=TestOutcome.RERUN, start_time=t0, duration=1.0)
    tr2 = TestResult(nodeid="test_foo", outcome=TestOutcome.FAILED, start_time=t0, duration=1.0)
    group = RerunTestGroup(nodeid="test_foo")
    group.add_test(tr1)
    group.add_test(tr2)
    assert group.final_outcome == TestOutcome.FAILED
    # Serialization
    d = group.to_dict()
    group_restored = RerunTestGroup.from_dict(d)
    assert group_restored.nodeid == "test_foo"
    assert group_restored.final_outcome == TestOutcome.FAILED

def test_testsession_add_and_serialization():
    t0 = datetime(2025, 4, 21, 10, 0, 0)
    t1 = t0 + timedelta(seconds=10)
    tr = TestResult(nodeid="test_foo", outcome=TestOutcome.PASSED, start_time=t0, duration=2.0)
    group = RerunTestGroup(nodeid="test_foo")
    group.add_test(tr)
    session = TestSession(
        sut_name="api-service",
        session_id="sess1",
        session_start_time=t0,
        session_stop_time=t1,
    )
    session.add_test_result(tr)
    session.add_rerun_group(group)
    d = session.to_dict()
    session_restored = TestSession.from_dict(d)
    assert session_restored.sut_name == "api-service"
    assert session_restored.session_id == "sess1"
    assert session_restored.test_results[0].nodeid == "test_foo"
    assert session_restored.rerun_test_groups[0].nodeid == "test_foo"
    # Error cases
    with pytest.raises(ValueError):
        session.add_test_result("not_a_testresult")
    with pytest.raises(ValueError):
        session.add_rerun_group("not_a_rerungroup")
