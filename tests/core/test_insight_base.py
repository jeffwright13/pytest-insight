import pytest

from pytest_insight.core.insight_base import Insight


class DummyInsight(Insight):
    pass


def test_base_methods_raise_not_implemented():
    ins = DummyInsight()
    # Each method should raise NotImplementedError
    with pytest.raises(NotImplementedError):
        ins.insight("foo")
    with pytest.raises(NotImplementedError):
        ins.tests()
    with pytest.raises(NotImplementedError):
        ins.sessions()
    with pytest.raises(NotImplementedError):
        ins.summary()
    with pytest.raises(NotImplementedError):
        ins.reliability()
    with pytest.raises(NotImplementedError):
        ins.trends()
    with pytest.raises(NotImplementedError):
        ins.comparison()
    with pytest.raises(NotImplementedError):
        ins.meta()
    with pytest.raises(NotImplementedError):
        ins.predict()
    with pytest.raises(NotImplementedError):
        ins.temporal()


def test_concrete_override():
    class CustomInsight(Insight):
        def summary(self):
            return "summary!"

    ins = CustomInsight()
    assert ins.summary() == "summary!"
    # All others still raise
    with pytest.raises(NotImplementedError):
        ins.insight("foo")
