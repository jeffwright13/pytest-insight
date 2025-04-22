from pytest_insight.core.insight_base import Insight
from pytest_insight.core.models import TestSession


class MetaInsight(Insight):
    """
    Insights about the test process itself (maintenance burden, stability over time).
    Inherits the Insight base interface.
    """

    def __init__(self, sessions: list[TestSession]):
        self._sessions = sessions

    def maintenance_burden(self):
        unique_tests = set()
        for s in self._sessions:
            for t in s.test_results:
                unique_tests.add(t.nodeid)
        return {
            "unique_tests": len(unique_tests),
            "total_sessions": len(self._sessions),
            "tests_per_session": (len(unique_tests) / len(self._sessions) if self._sessions else None),
        }

    def as_dict(self):
        """Return meta-insight metrics as a dict for dashboard rendering."""
        return self.maintenance_burden()

    def insight(self, kind: str = "meta", tabular: bool = True, **kwargs):
        if kind in {"summary", "health"}:
            from pytest_insight.facets.summary import SummaryInsight

            return SummaryInsight(self._sessions).as_dict()
        if kind == "meta":
            burden = self.maintenance_burden()
            # Always return structured data
            return {
                "unique_tests": burden["unique_tests"],
                "total_sessions": burden["total_sessions"],
                "tests_per_session": burden["tests_per_session"],
            }
        raise ValueError(f"Unsupported insight kind: {kind}")
