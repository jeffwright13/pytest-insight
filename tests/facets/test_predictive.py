from types import SimpleNamespace

import pytest

from pytest_insight.facets.predictive import PredictiveInsight


def make_test_result(outcome):
    return SimpleNamespace(outcome=outcome)


def make_session(session_start_time=None, test_results=None):
    return SimpleNamespace(
        session_start_time=session_start_time, test_results=test_results or []
    )


def test_init_empty_and_nonempty():
    assert PredictiveInsight([])._sessions == []
    s = [make_session()]
    assert PredictiveInsight(s)._sessions == s


def test_forecast_no_sessions():
    pi = PredictiveInsight([])
    result = pi.forecast()
    assert result["future_reliability"] is None
    assert result["trend"] is None
    assert "No sessions" in result["warning"]


def test_forecast_one_session():
    dt = SimpleNamespace(date=lambda: "2023-01-01")
    s = make_session(session_start_time=dt, test_results=[make_test_result("passed")])
    pi = PredictiveInsight([s])
    result = pi.forecast()
    assert result["future_reliability"] == 1.0
    assert result["trend"] is None
    assert "Not enough data" in result["warning"]


def test_forecast_trend_downward():
    # Two days, reliability drops
    dt1 = SimpleNamespace(date=lambda: "2023-01-01")
    dt2 = SimpleNamespace(date=lambda: "2023-01-02")
    s1 = make_session(session_start_time=dt1, test_results=[make_test_result("passed")])
    s2 = make_session(session_start_time=dt2, test_results=[make_test_result("failed")])
    pi = PredictiveInsight([s1, s2])
    result = pi.forecast()
    assert result["future_reliability"] < 1.0
    assert result["trend"] < 0
    assert "downward" in (result["warning"] or "")


def test_forecast_trend_upward():
    dt1 = SimpleNamespace(date=lambda: "2023-01-01")
    dt2 = SimpleNamespace(date=lambda: "2023-01-02")
    s1 = make_session(session_start_time=dt1, test_results=[make_test_result("failed")])
    s2 = make_session(session_start_time=dt2, test_results=[make_test_result("passed")])
    pi = PredictiveInsight([s1, s2])
    result = pi.forecast()
    assert result["future_reliability"] > 0.0
    assert result["trend"] > 0
    assert result["warning"] is None


def test_insight_predictive_tabular_and_plain():
    dt1 = SimpleNamespace(date=lambda: "2023-01-01")
    dt2 = SimpleNamespace(date=lambda: "2023-01-02")
    s1 = make_session(session_start_time=dt1, test_results=[make_test_result("passed")])
    s2 = make_session(session_start_time=dt2, test_results=[make_test_result("failed")])
    pi = PredictiveInsight([s1, s2])
    tab = pi.insight(kind="predictive_failure", tabular=True)
    plain = pi.insight(kind="predictive_failure", tabular=False)
    assert "Forecasted Reliability" in tab
    assert "forecasted reliability" in plain.lower()


def test_insight_summary_health_dispatch(mocker):
    s = [make_session()]
    pi = PredictiveInsight(s)
    fake = object()
    mocker.patch("pytest_insight.facets.summary.SummaryInsight", return_value=fake)
    for kind in ("summary", "health"):
        assert pi.insight(kind=kind) is fake


def test_insight_invalid_kind():
    pi = PredictiveInsight([])
    with pytest.raises(ValueError):
        pi.insight(kind="notareal")


def test_as_dict():
    dt1 = SimpleNamespace(date=lambda: "2023-01-01")
    dt2 = SimpleNamespace(date=lambda: "2023-01-02")
    s1 = make_session(session_start_time=dt1, test_results=[make_test_result("passed")])
    s2 = make_session(session_start_time=dt2, test_results=[make_test_result("failed")])
    pi = PredictiveInsight([s1, s2])
    d = pi.as_dict()
    assert "future_reliability" in d and "trend" in d and "warning" in d


def test_predictive_insight_interface_methods():
    pi = PredictiveInsight([])
    # insight() is implemented and tested elsewhere
    # All other base methods should raise NotImplementedError unless implemented
    with pytest.raises(NotImplementedError):
        pi.tests()
    with pytest.raises(NotImplementedError):
        pi.sessions()
    with pytest.raises(NotImplementedError):
        pi.summary()
    with pytest.raises(NotImplementedError):
        pi.reliability()
    with pytest.raises(NotImplementedError):
        pi.trends()
    with pytest.raises(NotImplementedError):
        pi.comparison()
    with pytest.raises(NotImplementedError):
        pi.meta()
    with pytest.raises(NotImplementedError):
        pi.temporal()
