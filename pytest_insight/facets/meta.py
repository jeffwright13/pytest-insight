from tabulate import tabulate

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
            "tests_per_session": (
                len(unique_tests) / len(self._sessions) if self._sessions else None
            ),
        }

    def as_dict(self):
        """Return meta-insight metrics as a dict for dashboard rendering."""
        return self.maintenance_burden()

    def insight(self, kind: str = "meta", tabular: bool = True, **kwargs):
        if kind in {"summary", "health"}:
            from pytest_insight.facets.summary import SummaryInsight

            return SummaryInsight(self._sessions)
        if kind == "meta":
            burden = self.maintenance_burden()
            if tabular:
                rows = [
                    [
                        burden["unique_tests"],
                        burden["total_sessions"],
                        (
                            f"{burden['tests_per_session']:.2f}"
                            if burden["tests_per_session"] is not None
                            else "N/A"
                        ),
                    ]
                ]
                return tabulate(
                    rows,
                    headers=["Unique Tests", "Sessions", "Tests/Session"],
                    tablefmt="github",
                )
            else:
                return (
                    f"Unique tests: {burden['unique_tests']}, "
                    f"Sessions: {burden['total_sessions']}, "
                    f"Tests/session: {burden['tests_per_session']:.2f}"
                    if burden["tests_per_session"] is not None
                    else "Tests/session: N/A"
                )
        raise ValueError(f"Unsupported insight kind: {kind}")
