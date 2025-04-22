from types import SimpleNamespace

import pytest
from pytest_insight.facets.summary import SummaryInsight


class FakeEnum:
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value

    def __repr__(self):
        return f"FakeEnum({self.value})"


def make_test_result(outcome, duration=1.0, nodeid="test_x"):
    return SimpleNamespace(outcome=outcome, duration=duration, nodeid=nodeid)


def make_session(session_id, results=None):
    return SimpleNamespace(session_id=session_id, test_results=results or [])


def test_summary_insight_init():
    s1 = make_session("s1")
    si = SummaryInsight([s1])
    assert si.sessions == [s1]


def test_aggregate_stats_empty():
    si = SummaryInsight([])
    stats = si.aggregate_stats()
    assert stats["total_sessions"] == 0
    assert stats["total_tests"] == 0
    assert stats["reliability"] == 0.0 or stats["reliability"] is None
    for v in stats["outcome_counts"].values():
        assert v == 0
    for v in stats["outcome_percentages"].values():
        assert v == 0.0


def test_aggregate_stats_mixed_outcomes():
    # Mix of string and enum outcomes
    passed_enum = FakeEnum("passed")
    failed_enum = FakeEnum("failed")
    results = [
        make_test_result("passed"),
        make_test_result(passed_enum),
        make_test_result("failed"),
        make_test_result(failed_enum),
    ]
    s = make_session("s1", results)
    si = SummaryInsight([s])
    stats = si.aggregate_stats()
    assert stats["total_sessions"] == 1
    assert stats["total_tests"] == 4
    assert stats["outcome_counts"]["passed"] == 2
    assert stats["outcome_counts"]["failed"] == 2
    assert stats["outcome_percentages"]["passed"] == 50.0
    assert stats["outcome_percentages"]["failed"] == 50.0


def test_aggregate_stats_unexpected_outcomes():
    # Outcomes not in TestOutcome, should not be counted
    results = [make_test_result("skipped"), make_test_result("foo")]  # "skipped" is valid, "foo" is not
    s = make_session("s1", results)
    si = SummaryInsight([s])
    stats = si.aggregate_stats()
    assert stats["outcome_counts"].get("skipped", 0) == 1  # "skipped" is a valid outcome
    assert stats["outcome_counts"].get("foo", 0) == 0  # "foo" is not a valid outcome


def test_suite_level_metrics_empty():
    si = SummaryInsight([])
    metrics = si.suite_level_metrics()
    assert metrics["avg_duration"] is None


def test_suite_level_metrics_average():
    r1 = make_test_result("passed", duration=2.0)
    r2 = make_test_result("failed", duration=4.0)
    s1 = make_session("s1", [r1, r2])
    s2 = make_session("s2", [make_test_result("passed", duration=6.0)])
    si = SummaryInsight([s1, s2])
    metrics = si.suite_level_metrics()
    # (2+4)+(6) = 12 / 2 sessions = 6.0
    assert metrics["avg_duration"] == 6.0


def test_insight_valid_kinds():
    s = make_session("s1")
    si = SummaryInsight([s])
    assert si.insight(kind="summary") is si
    assert si.insight(kind="health") is si


def test_insight_invalid_kind():
    s = make_session("s1")
    si = SummaryInsight([s])
    with pytest.raises(ValueError):
        si.insight(kind="nonsense")


def test_as_dict_empty():
    si = SummaryInsight([])
    d = si.as_dict()
    assert d["total_sessions"] == 0
    assert d["total_tests"] == 0
    assert d["pass_rate"] == 0.0
    assert d["fail_rate"] == 0.0
    for v in d["outcome_counts"].values():
        assert v == 0


def test_as_dict_mixed():
    r1 = make_test_result("passed")
    r2 = make_test_result("failed")
    r3 = make_test_result(FakeEnum("passed"))
    s1 = make_session("s1", [r1, r2, r3])
    si = SummaryInsight([s1])
    d = si.as_dict()
    assert d["total_sessions"] == 1
    assert d["total_tests"] == 3
    assert d["pass_rate"] == pytest.approx(66.666, rel=1e-2)
    assert d["fail_rate"] == pytest.approx(33.333, rel=1e-2)
    assert d["outcome_counts"]["passed"] == 2
    assert d["outcome_counts"]["failed"] == 1
