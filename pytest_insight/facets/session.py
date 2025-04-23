from pytest_insight.core.insight_base import Insight
from pytest_insight.core.models import TestSession


class SessionInsight(Insight):
    """
    Provides session-level analytics and metrics.
    Inherits the Insight base interface.
    """

    def __init__(self, sessions: list[TestSession]):
        self.sessions = sessions

    def metrics(self):
        metrics = []
        for s in self.sessions:
            total_tests = len(s.test_results)
            outcome_counts = {
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "xfailed": 0,
                "xpassed": 0,
                "rerun": 0,
                "error": 0,
            }
            for t in s.test_results:
                outcome = getattr(t, "outcome", None)
                if hasattr(outcome, "value"):
                    outcome_key = outcome.value.lower()
                else:
                    outcome_key = str(outcome).lower()
                if outcome_key in outcome_counts:
                    outcome_counts[outcome_key] += 1
            reliability = outcome_counts["passed"] / total_tests if total_tests else None
            avg_duration = sum(t.duration for t in s.test_results) / total_tests if total_tests else None
            metrics.append(
                {
                    "session_id": s.session_id,
                    "sut": getattr(s, "sut_name", ""),
                    "date": getattr(s, "session_start_time", None),
                    "total_tests": total_tests,
                    "reliability": reliability,
                    "avg_duration": avg_duration,
                    **{k: outcome_counts[k] for k in outcome_counts},
                }
            )
        return metrics

    def session_reliability_distribution(self):
        """Return a dict with counts of session types (all passed, some failed, etc.)"""
        dist = {
            "all_passed": 0,
            "some_failed": 0,
            "some_errored": 0,
            "all_skipped": 0,
            "mixed": 0,
        }
        for m in self.metrics():
            if m["total_tests"] == 0:
                continue
            if m["passed"] == m["total_tests"]:
                dist["all_passed"] += 1
            elif m["failed"] > 0 and m["failed"] + m["passed"] == m["total_tests"]:
                dist["some_failed"] += 1
            elif m["error"] > 0:
                dist["some_errored"] += 1
            elif m["skipped"] == m["total_tests"]:
                dist["all_skipped"] += 1
            else:
                dist["mixed"] += 1
        return dist

    def suspicious_sessions(self):
        """Return sessions where all tests are skipped, xfailed, or rerun."""
        suspicious = []
        for m in self.metrics():
            if m["total_tests"] == 0:
                continue
            if m["skipped"] == m["total_tests"] or m["xfailed"] == m["total_tests"] or m["rerun"] == m["total_tests"]:
                suspicious.append(m)
        return suspicious

    def top_unreliable_sessions(self, n=5):
        """Return top N sessions with lowest reliability (most failures+errors)."""
        ms = [m for m in self.metrics() if m["total_tests"] > 0]
        ms.sort(key=lambda m: (m["reliability"] if m["reliability"] is not None else 1))
        return ms[:n]

    def health_report(self, tabular: bool = True):
        if not self.sessions:
            return {"error": "No session data."}
        dist = self.session_reliability_distribution()
        suspicious = self.suspicious_sessions()
        top_unrel = self.top_unreliable_sessions()
        return {
            "session_reliability_distribution": dist,
            "suspicious_sessions": suspicious,
            "top_unreliable_sessions": top_unrel,
        }

    def as_dict(self):
        """
        Return all sessions as a list of dicts for serialization.
        """
        return [s.as_dict() if hasattr(s, 'as_dict') else s.__dict__ for s in self.sessions]

    def metrics_as_dict(self):
        """
        Return session-level metrics as a dict for dashboard rendering.
        """
        metrics = []
        for s in self.sessions:
            total_tests = len(s.test_results)
            outcome_counts = {
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "xfailed": 0,
                "xpassed": 0,
                "rerun": 0,
                "error": 0,
            }
            for t in s.test_results:
                outcome = getattr(t, "outcome", None)
                if hasattr(outcome, "value"):
                    outcome_key = outcome.value.lower()
                else:
                    outcome_key = str(outcome).lower()
                if outcome_key in outcome_counts:
                    outcome_counts[outcome_key] += 1
            reliability = outcome_counts["passed"] / total_tests if total_tests else None
            avg_duration = sum(t.duration for t in s.test_results) / total_tests if total_tests else None
            metrics.append(
                {
                    "session_id": s.session_id,
                    "sut": getattr(s, "sut_name", ""),
                    "date": getattr(s, "session_start_time", None),
                    "total_tests": total_tests,
                    "reliability": reliability,
                    "avg_duration": avg_duration,
                    **{k: outcome_counts[k] for k in outcome_counts},
                }
            )
        return metrics

    def insight(self, kind: str = "health", tabular: bool = True, **kwargs):
        if kind in {"summary", "health"}:
            from pytest_insight.facets.summary import SummaryInsight

            return SummaryInsight(self.sessions).as_dict()
        elif kind == "metrics":
            return self.metrics()
        elif kind == "key_metrics":
            return self.key_metrics()
        raise ValueError(f"Unsupported insight kind: {kind}")

    def available_insights(self):
        """
        Return the available insight types for session-level analytics.
        """
        return ["summary", "health", "session"]

    def filter(self, **criteria):
        """Return a new SessionInsight with sessions matching the given criteria.
        Example: .filter(sut="service", min_tests=5)
        Supported criteria:
            - sut: filter by sut_name
            - min_tests: minimum number of tests in session
            - max_tests: maximum number of tests in session
            - after: only sessions after this datetime
            - before: only sessions before this datetime
        """
        filtered = self.sessions
        if "sut" in criteria:
            filtered = [s for s in filtered if getattr(s, "sut_name", None) == criteria["sut"]]
        if "min_tests" in criteria:
            filtered = [s for s in filtered if len(getattr(s, "test_results", [])) >= criteria["min_tests"]]
        if "max_tests" in criteria:
            filtered = [s for s in filtered if len(getattr(s, "test_results", [])) <= criteria["max_tests"]]
        if "after" in criteria:
            filtered = [
                s
                for s in filtered
                if getattr(s, "session_start_time", None) and getattr(s, "session_start_time") >= criteria["after"]
            ]
        if "before" in criteria:
            filtered = [
                s
                for s in filtered
                if getattr(s, "session_start_time", None) and getattr(s, "session_start_time") <= criteria["before"]
            ]
        return SessionInsight(filtered)

    def trends(self):
        """
        Return a TrendInsight object for these sessions (Everything Is Insight pattern).
        """
        from pytest_insight.facets.trend import TrendInsight
        return TrendInsight(self.sessions)
