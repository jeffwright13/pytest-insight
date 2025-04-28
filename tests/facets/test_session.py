import pytest

# All profile creation for tests must use create_test_profile to ensure realistic setup and teardown.
# Example usage:
# test_profile = create_test_profile(name="test_profile", file_path="/tmp/test_profile.json", profiles_path="/tmp/profiles.json")
from pytest_insight.facets.session import SessionInsight


class DummySessionInsight(SessionInsight):
    def trends(self):
        raise NotImplementedError("DummySessionInsight.trends is not implemented")


def test_session_inherits_insight_methods():
    ins = DummySessionInsight([])
    # SessionInsight implements insight(), which raises ValueError for unknown kinds
    with pytest.raises(ValueError):
        ins.insight("foo")
    # All other base methods should raise NotImplementedError
    with pytest.raises(NotImplementedError):
        ins.tests()
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


def test_session_custom_method():
    class CustomSessionInsight(SessionInsight):
        def summary(self):
            return "session summary!"

    ins = CustomSessionInsight([])
    assert ins.summary() == "session summary!"
    # Others still raise or error as appropriate
    with pytest.raises(ValueError):
        ins.insight("foo")
