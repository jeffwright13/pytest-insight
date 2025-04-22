from types import SimpleNamespace

import pytest
from pytest_insight.facets.comparative import ComparativeInsight


@pytest.fixture
def sessions_factory():
    def _make(suts_tests):
        # suts_tests: {sut_name: [[outcome, ...], ...]}
        sessions = []
        for sut, test_lists in suts_tests.items():
            for test_outcomes in test_lists:
                test_results = [SimpleNamespace(outcome=o) for o in test_outcomes]
                sessions.append(SimpleNamespace(sut_name=sut, test_results=test_results))
        return sessions

    return _make


def test_init_empty_and_nonempty(sessions_factory):
    assert ComparativeInsight([]).sessions == []
    s = sessions_factory({"A": [["passed"]]})
    assert ComparativeInsight(s).sessions == s


def test_compare_suts_basic(sessions_factory):
    s = sessions_factory(
        {
            "A": [["passed", "failed"], ["passed"]],
            "B": [["failed"], ["passed", "passed"]],
        }
    )
    ci = ComparativeInsight(s)
    result = ci.compare_suts("A", "B")
    assert result["A"]["sessions"] == 2
    assert result["B"]["sessions"] == 2
    assert result["A"]["passes"] == 2
    assert result["B"]["passes"] == 2
    assert result["A"]["reliability"] == 2 / 3
    assert result["B"]["reliability"] == 2 / 3


def test_compare_suts_zero_and_missing(sessions_factory):
    s = sessions_factory({"A": [[]], "B": [[]]})
    ci = ComparativeInsight(s)
    r = ci.compare_suts("A", "B")
    assert r["A"]["reliability"] is None
    assert r["B"]["reliability"] is None
    # SUT not present
    ci = ComparativeInsight([])
    r = ci.compare_suts("A", "B")
    assert r["A"]["reliability"] is None
    assert r["B"]["reliability"] is None


def test_insight_regression_tabular_and_nontabular(sessions_factory):
    s = sessions_factory(
        {
            "A": [["passed", "failed"]],
            "B": [["passed"]],
        }
    )
    ci = ComparativeInsight(s)
    tab = ci.insight(kind="regression", tabular=True)
    assert "Reliability" in tab and "A" in tab
    nontab = ci.insight(kind="regression", tabular=False)
    assert "Reliability by SUT" in nontab


def test_insight_summary_health_dispatch(mocker, sessions_factory):
    s = sessions_factory({"A": [["passed"]]})
    ci = ComparativeInsight(s)
    fake = object()
    # Patch where SummaryInsight is imported (facets.summary)
    mocker.patch("pytest_insight.facets.summary.SummaryInsight", return_value=fake)
    for kind in ("summary", "health"):
        assert ci.insight(kind=kind) is fake


def test_insight_invalid_kind(sessions_factory):
    ci = ComparativeInsight(sessions_factory({}))
    with pytest.raises(ValueError):
        ci.insight(kind="notareal")


def test_as_dict_two_and_one_sut(sessions_factory):
    # Two SUTs triggers comparison
    s = sessions_factory({"A": [["passed"]], "B": [["failed"]]})
    ci = ComparativeInsight(s)
    d = ci.as_dict()
    assert "sut_comparison" in d and d["sut_comparison"] is not None
    # One SUT returns None
    s = sessions_factory({"A": [["passed"]]})
    ci = ComparativeInsight(s)
    d = ci.as_dict()
    assert d["sut_comparison"] is None
