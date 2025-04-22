from tabulate import tabulate

from pytest_insight.core.models import TestSession


class TrendInsight:
    """Detect and highlight emerging patterns."""

    def __init__(self, sessions: list[TestSession]):
        self.sessions = sessions

    def emerging_patterns(self):
        """
        Detect emerging patterns such as sudden increases in failures, slowdowns, or correlated issues.
        Returns a list of pattern dicts.
        """
        # Group by test nodeid and look for sudden changes in reliability
        from collections import defaultdict

        patterns = []
        test_history = defaultdict(list)
        for s in self.sessions:
            for t in s.test_results:
                test_history[t.nodeid].append((getattr(s, "session_start_time", None), t.outcome, t.duration))
        for nodeid, records in test_history.items():
            failures = [r for r in records if r[1] == "failed"]
            if len(failures) > 2:
                patterns.append(
                    {
                        "nodeid": nodeid,
                        "issue": f"{len(failures)} failures detected",
                        "recent_failure_time": failures[-1][0],
                    }
                )
            # Detect slowdowns
            durations = [r[2] for r in records]
            if len(durations) > 5 and max(durations) > 2 * sum(durations) / len(durations):
                patterns.append(
                    {
                        "nodeid": nodeid,
                        "issue": "Significant slowdown detected",
                        "max_duration": max(durations),
                    }
                )
        return patterns

    def duration_trends(self) -> dict:
        """Analyze duration trends over time. Returns average duration by day."""
        from collections import defaultdict

        by_date = defaultdict(list)
        for s in self.sessions:
            dt = getattr(s, "session_start_time", None)
            dur = getattr(s, "session_duration", None)
            if dt and dur:
                by_date[str(dt.date())].append(dur)
        trends = {d: sum(durs) / len(durs) for d, durs in by_date.items() if durs}
        return {"avg_duration_by_day": trends}

    def failure_trends(self) -> dict:
        """Analyze failure trends over time. Returns failure rates by day."""
        from collections import defaultdict

        by_date = defaultdict(lambda: {"failed": 0, "total": 0})
        for s in self.sessions:
            dt = getattr(s, "session_start_time", None)
            for t in getattr(s, "test_results", []):
                if dt:
                    by_date[str(dt.date())]["total"] += 1
                    outcome = getattr(t, "outcome", None)
                    if hasattr(outcome, "to_str"):
                        outcome = outcome.to_str()
                    if outcome and outcome.lower() == "failed":
                        by_date[str(dt.date())]["failed"] += 1
        trends = {d: {"fail_rate": v["failed"] / v["total"] if v["total"] else 0.0, **v} for d, v in by_date.items()}
        return {"failures_by_day": trends}

    def insight(self, kind: str = "trend", tabular: bool = True, **kwargs):
        if kind in {"summary", "health"}:
            from pytest_insight.facets.summary import SummaryInsight

            return SummaryInsight(self.sessions)
        if kind == "trend":
            return {
                "duration_trends": self.duration_trends(),
                "failure_trends": self.failure_trends(),
            }
        raise ValueError(f"Unsupported insight kind: {kind}")

    def unified_insight(self, kind: str = "trend", tabular: bool = True):
        """
        Return a summary of detected emerging patterns.
        Args:
            kind (str): The kind of insight to return.
            tabular (bool): If True, returns a tabular string; else, returns a plain string.
        """
        if kind == "trend":
            patterns = self.emerging_patterns()
            if not patterns:
                return "No emerging trends detected."
            if tabular:
                rows = []
                for p in patterns:
                    rows.append(
                        [
                            p.get("nodeid", ""),
                            p.get("issue", ""),
                            p.get("recent_failure_time", p.get("max_duration", "")),
                        ]
                    )
                return tabulate(rows, headers=["NodeID", "Issue", "Detail"], tablefmt="github")
            else:
                msg = f"Detected {len(patterns)} emerging pattern(s):\n"
                for p in patterns[:5]:
                    msg += f"- {p['nodeid']}: {p['issue']}\n"
                if len(patterns) > 5:
                    msg += f"...and {len(patterns) - 5} more."
                return msg
        raise ValueError(f"Unsupported insight kind: {kind}")

    def as_dict(self):
        """Return trend-level metrics as a dict for dashboard rendering."""
        return {
            "duration_trends": self.duration_trends(),
            "failure_trends": self.failure_trends(),
            "emerging_patterns": self.emerging_patterns() if hasattr(self, "emerging_patterns") else None,
        }

    def filter(self, sut: str = None, nodeid: str = None):
        """Return a new TrendInsight filtered by SUT or test nodeid.
        Args:
            sut (str): Filter sessions by SUT name.
            nodeid (str): Only consider trends for a specific test nodeid.
        """
        filtered_sessions = self.sessions
        if sut is not None:
            filtered_sessions = [s for s in filtered_sessions if getattr(s, "sut_name", None) == sut]
        if nodeid is not None:
            # Only keep sessions that have at least one test with the nodeid
            filtered_sessions = [
                s
                for s in filtered_sessions
                if any(getattr(t, "nodeid", None) == nodeid for t in getattr(s, "test_results", []))
            ]
        return TrendInsight(filtered_sessions)
