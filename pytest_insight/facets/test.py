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
        unreliable_list = [
            {"nodeid": nid, **metrics.get(nid, {})}
            for nid in sorted(unreliable)
        ]
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

    def insight(self, kind: str = "reliability"):
        if kind == "reliability":
            report = self.reliability_report()
            if not report:
                return "No test reliability data."
            avg_rel = sum(r['reliability'] for r in report if r['reliability'] is not None) / len(report)
            return f"Avg Test Reliability: {avg_rel:.2%} across {len(report)} tests"
        elif kind == "detailed":
            return {
                "outcome_distribution": self.outcome_distribution(),
                "unreliable_tests": self.unreliable_tests(),
                "slowest_tests": self.slowest_tests(),
                "test_reliability_metrics": self.test_reliability_metrics(),
            }
        raise ValueError(f"Unsupported insight kind: {kind}")
