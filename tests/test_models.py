from datetime import datetime, timedelta, timezone

import pytest
from pytest_insight.models import RerunTestGroup, TestOutcome, TestResult, TestSession
from pytest_insight.utils import NormalizedDatetime


# ---- TestOutcome Enum ----
def test_testoutcome_from_str_and_to_str():
    assert TestOutcome.from_str("passed") == TestOutcome.PASSED
    assert TestOutcome.from_str("FAILED") == TestOutcome.FAILED
    assert TestOutcome.PASSED.to_str() == "passed"
    assert TestOutcome.FAILED.to_str() == "failed"
    assert TestOutcome.to_list() == [o.value.lower() for o in TestOutcome]
    with pytest.raises(ValueError):
        TestOutcome.from_str("not_a_real_outcome")


def test_testoutcome_is_failed():
    assert TestOutcome.FAILED.is_failed() is True
    assert TestOutcome.ERROR.is_failed() is True
    assert TestOutcome.PASSED.is_failed() is False
    assert TestOutcome.SKIPPED.is_failed() is False


# ---- TestResult ----
def test_testresult_init_and_to_dict():
    start = NormalizedDatetime(datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
    stop = start + timedelta(seconds=2)
    result = TestResult(
        nodeid="test_foo.py::test_foo",
        outcome=TestOutcome.PASSED,
        start_time=start,
        stop_time=stop,
        duration=None,
        caplog="",
        capstderr="",
        capstdout="",
        longreprtext="",
        has_warning=False,
    )
    d = result.to_dict()
    assert d["nodeid"] == "test_foo.py::test_foo"
    assert d["outcome"] == "passed"
    assert NormalizedDatetime.from_iso(d["start_time"]) == start
    assert NormalizedDatetime.from_iso(d["stop_time"]) == stop
    assert d["duration"] == 2.0


def test_testresult_from_dict():
    start = NormalizedDatetime(datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
    stop = start + timedelta(seconds=2)
    d = {
        "nodeid": "test_bar.py::test_bar",
        "outcome": "failed",
        "start_time": start.to_iso(),
        "stop_time": stop.to_iso(),
        "duration": 2.0,
        "caplog": "",
        "capstderr": "",
        "capstdout": "",
        "longreprtext": "",
        "has_warning": False,
    }
    result = TestResult.from_dict(d)
    assert result.nodeid == "test_bar.py::test_bar"
    assert result.outcome == TestOutcome.FAILED
    assert result.duration == 2.0
    assert result.start_time == start
    assert result.stop_time == stop


# ---- RerunTestGroup ----
def test_reruntestgroup_add_and_final_outcome():
    start = NormalizedDatetime(datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
    tr1 = TestResult(
        "foo",
        TestOutcome.RERUN,
        start,
        stop_time=start + timedelta(seconds=1),
        duration=1,
    )
    tr2 = TestResult(
        "foo",
        TestOutcome.FAILED,
        start + timedelta(seconds=1),
        stop_time=start + timedelta(seconds=2),
        duration=1,
    )
    group = RerunTestGroup(nodeid="foo")
    group.add_test(tr1)
    group.add_test(tr2)
    assert group.final_outcome == TestOutcome.FAILED
    d = group.to_dict()
    assert d["nodeid"] == "foo"
    assert len(d["tests"]) == 2
    group2 = RerunTestGroup.from_dict(d)
    assert group2.nodeid == "foo"
    assert group2.tests[1].outcome == TestOutcome.FAILED
    # Check datetimes normalized
    assert group2.tests[0].start_time == start


# ---- TestSession ----
def test_testsession_add_and_to_from_dict():
    start = NormalizedDatetime(datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
    stop = start + timedelta(seconds=10)
    tr = TestResult(
        "foo",
        TestOutcome.PASSED,
        start,
        stop_time=start + timedelta(seconds=2),
        duration=2,
    )
    group = RerunTestGroup(nodeid="foo")
    group.add_test(tr)
    session = TestSession(
        sut_name="my-sut",
        testing_system={"host": "localhost"},
        session_id="abc123",
        session_start_time=start,
        session_stop_time=stop,
        session_duration=None,
        session_tags={"env": "dev"},
        rerun_test_groups=[group],
        test_results=[tr],
    )
    d = session.to_dict()
    assert d["sut_name"] == "my-sut"
    assert d["session_id"] == "abc123"
    assert d["testing_system"]["host"] == "localhost"
    session2 = TestSession.from_dict(d)
    assert session2.sut_name == "my-sut"
    assert session2.session_id == "abc123"
    assert session2.testing_system["host"] == "localhost"
    assert session2.test_results[0].nodeid == "foo"
    assert session2.rerun_test_groups[0].nodeid == "foo"
    assert session2.session_start_time == start
    assert session2.session_stop_time == stop
