from pytest_insight.core.insight_base import Insight
from pytest_insight.core.models import TestSession


class ComparativeInsight(Insight):
    """
    Compare across SUTs, code versions, environments, etc.
    Inherits the Insight base interface.
    """

    def __init__(self, sessions: list[TestSession]):
        self._sessions = sessions

    def compare_suts(self, sut_a, sut_b):
        """Compare reliability between two SUTs."""
        # Assume TestSession has .sut_name attribute
        results = {
            sut_a: {"sessions": 0, "passes": 0, "tests": 0},
            sut_b: {"sessions": 0, "passes": 0, "tests": 0},
        }
        for s in self._sessions:
            if getattr(s, "sut_name", None) == sut_a:
                results[sut_a]["sessions"] += 1
                results[sut_a]["tests"] += len(s.test_results)
                results[sut_a]["passes"] += sum(t.outcome == "passed" for t in s.test_results)
            elif getattr(s, "sut_name", None) == sut_b:
                results[sut_b]["sessions"] += 1
                results[sut_b]["tests"] += len(s.test_results)
                results[sut_b]["passes"] += sum(t.outcome == "passed" for t in s.test_results)
        for k in [sut_a, sut_b]:
            if results[k]["tests"]:
                results[k]["reliability"] = results[k]["passes"] / results[k]["tests"]
            else:
                results[k]["reliability"] = None
        return results

    def insight(self, kind: str = "regression", **kwargs):
        if kind in {"summary", "health"}:
            from pytest_insight.facets.summary import SummaryInsight

            return SummaryInsight(self._sessions).as_dict()
        if kind == "regression":
            suts = {}
            for s in self._sessions:
                suts.setdefault(s.sut_name, []).append(s)
            summary = []
            for sut, sess in suts.items():
                total_tests = sum(len(s.test_results) for s in sess)
                passes = sum(1 for s in sess for t in s.test_results if t.outcome == "passed")
                reliability = passes / total_tests if total_tests else None
                summary.append(
                    {
                        "SUT": sut,
                        "reliability": reliability,
                        "total_tests": total_tests,
                    }
                )
            # Always return structured data
            return {"sut_reliability": summary}
        raise ValueError(f"Unsupported insight kind: {kind}")

    def available_insights(self):
        """
        Return the available insight types for comparative analytics.
        """
        return ["compare"]

    def as_dict(self):
        """Return comparative metrics as a dict for dashboard rendering."""
        # Example: compare SUTs if at least two present
        suts = list({getattr(s, "sut_name", None) for s in self._sessions})
        if len(suts) >= 2:
            return {"sut_comparison": self.compare_suts(suts[0], suts[1])}
        return {"sut_comparison": None}
