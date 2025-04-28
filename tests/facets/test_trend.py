from types import SimpleNamespace

# All profile creation for tests must use create_test_profile to ensure realistic setup and teardown.
# Example usage:
# test_profile = create_test_profile(name="test_profile", file_path="/tmp/test_profile.json", profiles_path="/tmp/profiles.json")
import pytest
from pytest_insight.facets.trend import TrendInsight


def make_test_result(nodeid, outcome="passed", duration=1.0):
    return SimpleNamespace(nodeid=nodeid, outcome=outcome, duration=duration)


def make_session(
    session_id,
    results=None,
    session_start_time=None,
    session_duration=None,
    sut_name=None,
):
    return SimpleNamespace(
        session_id=session_id,
        test_results=results or [],
        session_start_time=session_start_time,
        session_duration=session_duration,
        sut_name=sut_name,
    )


def test_trend_insight_init():
    s1 = make_session("s1")
    ti = TrendInsight([s1])
    assert ti.sessions == [s1]


def test_emerging_patterns_failures():
    # 3 failures for nodeid triggers pattern
    results = [make_test_result("t1", "failed", 1.0) for _ in range(3)]
    s = make_session("s1", results, session_start_time=None)
    ti = TrendInsight([s])
    patterns = ti.emerging_patterns()
    assert any(p["nodeid"] == "t1" and "failures" in p["issue"] for p in patterns)


def test_emerging_patterns_slowdown():
    # 6 durations, last is >2x average triggers slowdown
    durations = [1.0] * 5 + [11.0]
    results = [make_test_result("t2", "passed", d) for d in durations]
    s = make_session("s2", results)
    ti = TrendInsight([s])
    patterns = ti.emerging_patterns()
    assert any(p["nodeid"] == "t2" and "slowdown" in p["issue"] for p in patterns)


def test_emerging_patterns_none():
    results = [make_test_result("t3", "passed", 1.0) for _ in range(3)]
    s = make_session("s3", results)
    ti = TrendInsight([s])
    patterns = ti.emerging_patterns()
    assert patterns == []


def test_duration_trends():
    s1 = make_session(
        "s1",
        [],
        session_start_time=SimpleNamespace(date=lambda: "2023-01-01"),
        session_duration=2.0,
    )
    s2 = make_session(
        "s2",
        [],
        session_start_time=SimpleNamespace(date=lambda: "2023-01-01"),
        session_duration=4.0,
    )
    ti = TrendInsight([s1, s2])
    trends = ti.duration_trends()
    assert trends["avg_duration_by_day"]["2023-01-01"] == 3.0


def test_failure_trends():
    s1 = make_session(
        "s1",
        [make_test_result("t4", "failed"), make_test_result("t5", "passed")],
        session_start_time=SimpleNamespace(date=lambda: "2023-01-01"),
    )
    ti = TrendInsight([s1])
    trends = ti.failure_trends()
    day = "2023-01-01"
    assert trends["failures_by_day"][day]["fail_rate"] == 0.5
    assert trends["failures_by_day"][day]["failed"] == 1
    assert trends["failures_by_day"][day]["total"] == 2


def test_insight_trend_and_dispatch(mocker):
    s = make_session("s1")
    ti = TrendInsight([s])
    # trend kind returns dict
    out = ti.insight(kind="trend")
    assert "duration_trends" in out and "failure_trends" in out
    # summary/health dispatch
    mock_summary = mocker.patch("pytest_insight.facets.summary.SummaryInsight", autospec=True)
    ti.insight(kind="summary")
    assert mock_summary.called
    ti.insight(kind="health")
    assert mock_summary.called
    # error
    with pytest.raises(ValueError):
        ti.insight(kind="nonsense")


def test_unified_insight_tabular_and_plain():
    # 3 failures for nodeid triggers pattern
    results = [make_test_result("t6", "failed", 1.0) for _ in range(3)]
    s = make_session("s1", results)
    ti = TrendInsight([s])
    tabular = ti.unified_insight(kind="trend", tabular=True)
    plain = ti.unified_insight(kind="trend", tabular=False)
    # tabular should be a string, plain should be a dict
    assert isinstance(tabular, str), f"tabular output should be str, got {type(tabular)}: {tabular}"
    assert isinstance(plain, dict), f"plain output should be dict, got {type(plain)}: {plain}"


def test_as_dict():
    s = make_session("s1")
    ti = TrendInsight([s])
    d = ti.as_dict()
    assert "duration_trends" in d and "failure_trends" in d and "emerging_patterns" in d


def test_filter_sut_and_nodeid():
    results = [make_test_result("t7"), make_test_result("t8")]
    s1 = make_session("s1", results, sut_name="foo")
    s2 = make_session("s2", results, sut_name="bar")
    ti = TrendInsight([s1, s2])
    # Filter by sut
    ti_foo = ti.filter(sut="foo")
    assert all(s.sut_name == "foo" for s in ti_foo.sessions)
    # Filter by nodeid
    ti_t7 = ti.filter(nodeid="t7")
    assert all(any(t.nodeid == "t7" for t in s.test_results) for s in ti_t7.sessions)
