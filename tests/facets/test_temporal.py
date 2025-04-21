import pytest
from types import SimpleNamespace
import datetime as dt
from pytest_insight.facets.temporal import TemporalInsight

@pytest.fixture
def make_test_session():
    def _make(session_id, start_time, results=None):
        return SimpleNamespace(
            session_id=session_id,
            session_start_time=start_time,
            test_results=results or []
        )
    return _make

@pytest.fixture
def make_test_result():
    def _make(outcome):
        return SimpleNamespace(outcome=outcome)
    return _make

def test_temporal_insight_init(make_test_session):
    s1 = make_test_session('s1', dt.datetime(2023,1,1))
    ti = TemporalInsight([s1])
    assert ti.sessions == [s1]

def test_trend_over_time_empty():
    ti = TemporalInsight([])
    assert ti.trend_over_time() == []

def test_trend_over_time_single_day_all_pass(make_test_session, make_test_result):
    results = [make_test_result('passed') for _ in range(5)]
    s = make_test_session('s1', dt.datetime(2023,1,1), results)
    ti = TemporalInsight([s])
    series = ti.trend_over_time()
    assert len(series) == 1
    assert series[0]['reliability'] == 1.0
    assert series[0]['total_tests'] == 5

def test_trend_over_time_single_day_some_fail(make_test_session, make_test_result):
    results = [make_test_result('passed')]*3 + [make_test_result('failed')]*2
    s = make_test_session('s1', dt.datetime(2023,1,1), results)
    ti = TemporalInsight([s])
    series = ti.trend_over_time()
    assert series[0]['reliability'] == 0.6
    assert series[0]['total_tests'] == 5

def test_trend_over_time_multiple_days(make_test_session, make_test_result):
    r_pass = [make_test_result('passed')]*2
    r_fail = [make_test_result('failed')]*2
    s1 = make_test_session('s1', dt.datetime(2023,1,1), r_pass)
    s2 = make_test_session('s2', dt.datetime(2023,1,2), r_fail)
    ti = TemporalInsight([s1,s2])
    series = ti.trend_over_time()
    assert len(series) == 2
    assert series[0]['reliability'] == 1.0
    assert series[1]['reliability'] == 0.0

def test_trend_over_time_zero_tests(make_test_session):
    s = make_test_session('s1', dt.datetime(2023,1,1), [])
    ti = TemporalInsight([s])
    series = ti.trend_over_time()
    assert series[0]['reliability'] is None
    assert series[0]['total_tests'] == 0

def test_insight_trend_tabular(make_test_session, make_test_result):
    results = [make_test_result('passed')]*2
    s = make_test_session('s1', dt.datetime(2023,1,1), results)
    ti = TemporalInsight([s])
    out = ti.insight(kind="trend", tabular=True)
    assert "Interval" in out and "Reliability" in out
    assert "100.00%" in out

def test_insight_trend_notabular(make_test_session, make_test_result):
    results = [make_test_result('passed')]*2
    s = make_test_session('s1', dt.datetime(2023,1,1), results)
    ti = TemporalInsight([s])
    out = ti.insight(kind="trend", tabular=False)
    assert "Most recent reliability:" in out
    assert "100.00%" in out

def test_insight_trend_no_data():
    ti = TemporalInsight([])
    out = ti.insight(kind="trend", tabular=True)
    assert out == "No trend data."

def test_insight_summary_health_dispatch(mocker, make_test_session):
    s = make_test_session('s1', dt.datetime(2023,1,1))
    ti = TemporalInsight([s])
    mock_summary = mocker.patch("pytest_insight.facets.summary.SummaryInsight", autospec=True)
    out = ti.insight(kind="summary")
    assert mock_summary.called
    out2 = ti.insight(kind="health")
    assert mock_summary.called

def test_insight_invalid_kind(make_test_session):
    s = make_test_session('s1', dt.datetime(2023,1,1))
    ti = TemporalInsight([s])
    with pytest.raises(ValueError):
        ti.insight(kind="nonsense")

def test_as_dict(make_test_session):
    s1 = make_test_session('s1', dt.datetime(2023,1,1))
    s2 = make_test_session('s2', dt.datetime(2023,1,2))
    ti = TemporalInsight([s1,s2])
    d = ti.as_dict()
    assert d == {"sessions": ["s1", "s2"]}
