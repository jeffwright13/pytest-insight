from types import SimpleNamespace

import pytest
from pytest_insight.facets.meta import MetaInsight


def make_test_result(nodeid):
    return SimpleNamespace(nodeid=nodeid)


def make_session(session_id, results=None):
    return SimpleNamespace(session_id=session_id, test_results=results or [])


def test_meta_insight_init():
    s1 = make_session("s1")
    mi = MetaInsight([s1])
    assert mi._sessions == [s1]


def test_maintenance_burden_empty():
    mi = MetaInsight([])
    burden = mi.maintenance_burden()
    assert burden["unique_tests"] == 0
    assert burden["total_sessions"] == 0
    assert burden["tests_per_session"] is None


def test_maintenance_burden_mixed():
    r1 = make_test_result("a")
    r2 = make_test_result("b")
    r3 = make_test_result("a")
    s1 = make_session("s1", [r1, r2])
    s2 = make_session("s2", [r3])
    mi = MetaInsight([s1, s2])
    burden = mi.maintenance_burden()
    assert burden["unique_tests"] == 2
    assert burden["total_sessions"] == 2
    assert burden["tests_per_session"] == 1.0


def test_as_dict():
    s1 = make_session("s1", [make_test_result("a")])
    mi = MetaInsight([s1])
    d = mi.as_dict()
    assert "unique_tests" in d and "total_sessions" in d and "tests_per_session" in d


def test_insight_meta_tabular_and_plain():
    r1 = make_test_result("a")
    r2 = make_test_result("b")
    s1 = make_session("s1", [r1, r2])
    mi = MetaInsight([s1])
    tabular = mi.insight(kind="meta", tabular=True)
    plain = mi.insight(kind="meta", tabular=False)
    # Both must be dicts with expected keys
    for output in (tabular, plain):
        assert isinstance(output, dict)
        assert "unique_tests" in output
        assert "total_sessions" in output
        assert "tests_per_session" in output


def test_insight_summary_health_dispatch(mocker):
    s1 = make_session("s1")
    mi = MetaInsight([s1])
    mock_summary = mocker.patch("pytest_insight.facets.summary.SummaryInsight", autospec=True)
    mi.insight(kind="summary")
    assert mock_summary.called
    mi.insight(kind="health")
    assert mock_summary.called
    with pytest.raises(ValueError):
        mi.insight(kind="nonsense")


def test_meta_insight_interface_methods():
    mi = MetaInsight([])
    # insight() is implemented and tested elsewhere
    # All other base methods should raise NotImplementedError unless implemented
    with pytest.raises(NotImplementedError):
        mi.tests()
    with pytest.raises(NotImplementedError):
        mi.sessions()
    with pytest.raises(NotImplementedError):
        mi.summary()
    with pytest.raises(NotImplementedError):
        mi.reliability()
    with pytest.raises(NotImplementedError):
        mi.trends()
    with pytest.raises(NotImplementedError):
        mi.comparison()
    with pytest.raises(NotImplementedError):
        mi.predict()
    with pytest.raises(NotImplementedError):
        mi.temporal()
