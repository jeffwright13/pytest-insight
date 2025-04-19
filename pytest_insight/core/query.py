"""Query/filter logic with fluent interface."""

from .models import TestSession
from typing import List, Callable

class SessionQuery:
    def __init__(self, sessions: List[TestSession]):
        self.sessions = sessions
        self.filters = []

    def for_sut(self, sut_name: str):
        self.filters.append(lambda s: getattr(s, "sut_name", None) == sut_name)
        return self

    def in_last_days(self, days: int):
        # TODO: Implement date filtering
        return self

    def filter_by_test(self):
        return TestQuery(self)

    def insight(self, kind: str = "summary"):
        filtered = self.execute()
        if kind == "summary":
            return {"total_sessions": len(filtered)}
        elif kind == "health":
            # Example health metric: percent sessions with all tests passed
            healthy = sum(all(t.outcome == "passed" for t in s.test_results) for s in filtered)
            return {"healthy_sessions": healthy, "total_sessions": len(filtered)}
        else:
            return {"info": f"Unknown insight kind: {kind}"}

    def execute(self) -> List[TestSession]:
        result = self.sessions
        for f in self.filters:
            result = [s for s in result if f(s)]
        return result

class TestQuery:
    def __init__(self, parent_query: SessionQuery):
        self.parent_query = parent_query
        self.test_filters = []

    def with_name(self, name: str):
        self.test_filters.append(lambda t: getattr(t, "nodeid", None) == name)
        return self

    def with_duration(self, min_dur: float, max_dur: float):
        self.test_filters.append(lambda t: min_dur <= getattr(t, "duration", 0) <= max_dur)
        return self

    def apply(self):
        # Filter sessions by test criteria
        filtered_sessions = []
        for session in self.parent_query.execute():
            if any(all(f(t) for f in self.test_filters) for t in session.test_results):
                filtered_sessions.append(session)
        self.parent_query.sessions = filtered_sessions
        return self.parent_query

    def insight(self, kind: str = "reliability"):
        # Example: compute per-test reliability (pass rate)
        filtered_sessions = self.parent_query.execute()
        stats = {}
        for s in filtered_sessions:
            for t in s.test_results:
                if all(f(t) for f in self.test_filters):
                    d = stats.setdefault(t.nodeid, {"runs": 0, "passes": 0, "failures": 0, "total_duration": 0.0})
                    d["runs"] += 1
                    d["passes"] += int(t.outcome == "passed")
                    d["failures"] += int(t.outcome == "failed")
                    d["total_duration"] += t.duration
        report = []
        for nodeid, d in stats.items():
            reliability = d["passes"] / d["runs"] if d["runs"] else None
            avg_duration = d["total_duration"] / d["runs"] if d["runs"] else None
            report.append({
                "nodeid": nodeid,
                "runs": d["runs"],
                "reliability": reliability,
                "avg_duration": avg_duration,
                "failures": d["failures"]
            })
        return report
