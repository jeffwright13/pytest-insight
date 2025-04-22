from collections import defaultdict

from pytest_insight.core.models import TestSession


class TestInsight:
    """Focus on individual tests: reliability, duration, outcome, etc."""

    def __init__(self, sessions: list[TestSession]):
        self.sessions = sessions

    def reliability_report(self):
        """Reliability metrics per test nodeid."""
        stats = defaultdict(lambda: {"runs": 0, "passes": 0, "failures": 0, "total_duration": 0.0})
        for s in self.sessions:
            for t in s.test_results:
                stats[t.nodeid]["runs"] += 1
                stats[t.nodeid]["passes"] += int(t.outcome == "passed")
                stats[t.nodeid]["failures"] += int(t.outcome == "failed")
                stats[t.nodeid]["total_duration"] += t.duration
        # Compute reliability as pass/runs
        report = []
        for nodeid, d in stats.items():
            reliability = d["passes"] / d["runs"] if d["runs"] else None
            avg_duration = d["total_duration"] / d["runs"] if d["runs"] else None
            report.append(
                {
                    "nodeid": nodeid,
                    "runs": d["runs"],
                    "reliability": reliability,
                    "avg_duration": avg_duration,
                    "failures": d["failures"],
                }
            )
        return report

    def outcome_distribution(self) -> dict:
        """Return distribution of test outcomes and total count across all sessions."""
        from collections import Counter

        counts = Counter()
        total = 0
        for s in self.sessions:
            for t in getattr(s, "test_results", []):
                outcome = getattr(t, "outcome", None)
                counts[outcome] += 1
                total += 1
        return {"distribution": dict(counts), "total": total}

    def unreliable_tests(self, limit=5) -> list:
        """Return list of unreliable tests (marked unreliable in any session), with metrics."""
        unreliable = set()
        for s in self.sessions:
            for t in getattr(s, "test_results", []):
                if getattr(t, "unreliable", False):
                    unreliable.add(getattr(t, "nodeid", None))
        metrics = self.test_reliability_metrics()
        unreliable_list = [{"nodeid": nid, **metrics.get(nid, {})} for nid in sorted(unreliable)]
        # Optionally sort by unreliable_rate descending
        unreliable_list.sort(key=lambda x: x.get("unreliable_rate", 0), reverse=True)
        return unreliable_list[:limit]

    def slowest_tests(self, limit=5) -> list:
        """Return the slowest tests across all sessions."""
        tests = []
        for s in self.sessions:
            for t in getattr(s, "test_results", []):
                if t.duration is not None:
                    tests.append({"nodeid": t.nodeid, "duration": t.duration})
        tests.sort(key=lambda x: x["duration"], reverse=True)
        return tests[:limit]

    def test_reliability_metrics(self) -> dict:
        """Compute reliability metrics for all tests."""
        from collections import defaultdict

        results = defaultdict(lambda: {"runs": 0, "unreliable": 0})
        for s in self.sessions:
            for t in getattr(s, "test_results", []):
                nodeid = getattr(t, "nodeid", None)
                results[nodeid]["runs"] += 1
                if getattr(t, "unreliable", False):
                    results[nodeid]["unreliable"] += 1
        metrics = {
            nid: {
                "unreliable_rate": v["unreliable"] / v["runs"] if v["runs"] else 0.0,
                **v,
            }
            for nid, v in results.items()
        }
        return metrics

    def as_dict(self):
        """Return test-level metrics as a dict for dashboard rendering."""
        return {
            "outcome_distribution": self.outcome_distribution(),
            "unreliable_tests": self.unreliable_tests(),
            "slowest_tests": self.slowest_tests(),
            "test_reliability_metrics": self.test_reliability_metrics(),
        }

    def insight(self, kind: str = "reliability", tabular: bool = True, **kwargs):
        if kind in {"summary", "health"}:
            from pytest_insight.facets.summary import SummaryInsight

            return SummaryInsight(self.sessions).as_dict()
        if kind == "detailed":
            return {
                "outcome_distribution": self.outcome_distribution(),
                "unreliable_tests": self.unreliable_tests(),
                "slowest_tests": self.slowest_tests(),
                "test_reliability_metrics": self.test_reliability_metrics(),
            }
        raise ValueError(f"Unsupported insight kind: {kind}")

    def filter(self, **criteria):
        """Return a new TestInsight with sessions containing tests matching given criteria.
        Example: .filter(nodeid="test_login", min_duration=1.0)
        Supported criteria:
            - nodeid: filter sessions containing a test with this nodeid
            - outcome: filter sessions containing a test with this outcome
            - min_duration: sessions with a test whose duration >= min_duration
            - max_duration: sessions with a test whose duration <= max_duration
        Note: Always returns sessions (with context), not isolated tests.
        """
        filtered_sessions = []
        for s in self.sessions:
            for t in getattr(s, "test_results", []):
                match = True
                if "nodeid" in criteria and getattr(t, "nodeid", None) != criteria["nodeid"]:
                    match = False
                if "outcome" in criteria and getattr(t, "outcome", None) != criteria["outcome"]:
                    match = False
                if (
                    "min_duration" in criteria
                    and getattr(t, "duration", None) is not None
                    and t.duration < criteria["min_duration"]
                ):
                    match = False
                if (
                    "max_duration" in criteria
                    and getattr(t, "duration", None) is not None
                    and t.duration > criteria["max_duration"]
                ):
                    match = False
                if match:
                    filtered_sessions.append(s)
                    break  # Only need one matching test per session
        return TestInsight(filtered_sessions)
