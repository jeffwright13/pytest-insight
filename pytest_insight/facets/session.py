from tabulate import tabulate

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
            reliability = (
                outcome_counts["passed"] / total_tests if total_tests else None
            )
            avg_duration = (
                sum(t.duration for t in s.test_results) / total_tests
                if total_tests
                else None
            )
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
            if (
                m["skipped"] == m["total_tests"]
                or m["xfailed"] == m["total_tests"]
                or m["rerun"] == m["total_tests"]
            ):
                suspicious.append(m)
        return suspicious

    def top_unreliable_sessions(self, n=5):
        """Return top N sessions with lowest reliability (most failures+errors)."""
        ms = [m for m in self.metrics() if m["total_tests"] > 0]
        ms.sort(key=lambda m: (m["reliability"] if m["reliability"] is not None else 1))
        return ms[:n]

    def health_report(self, tabular: bool = True):
        if not self.sessions:
            return "No session data."
        dist = self.session_reliability_distribution()
        suspicious = self.suspicious_sessions()
        top_unrel = self.top_unreliable_sessions()
        if tabular:
            lines = []
            lines.append("Session Reliability Distribution:")
            dist_table = [
                {"Type": label, "Count": dist[k]}
                for k, label in [
                    ("all_passed", "All Passed"),
                    ("some_failed", "Some Failed"),
                    ("some_errored", "Some Errored"),
                    ("all_skipped", "All Skipped"),
                    ("mixed", "Mixed Outcomes"),
                ]
            ]
            lines.append(tabulate(dist_table, headers="keys", tablefmt="github"))
            lines.append("")
            lines.append("Top 5 Most Unreliable Sessions:")
            unrel_table = []
            for m in top_unrel:
                unrel_table.append(
                    {
                        "Session ID": m["session_id"],
                        "Date": str(m["date"])[:10] if m["date"] else "",
                        "SUT": m["sut"],
                        "Pass": m["passed"],
                        "Fail": m["failed"],
                        "Err": m["error"],
                        "Reliab (%)": (
                            f"{m['reliability']*100:.2f}"
                            if m["reliability"] is not None
                            else "N/A"
                        ),
                    }
                )
            if unrel_table:
                lines.append(tabulate(unrel_table, headers="keys", tablefmt="github"))
            else:
                lines.append("(No unreliable sessions)")
            lines.append("")
            lines.append("Suspicious Sessions (all skipped/xfailed/rerun):")
            susp_table = [
                {
                    "Session ID": m["session_id"],
                    "SUT": m["sut"],
                    "Total Tests": m["total_tests"],
                    "Date": str(m["date"])[:10] if m["date"] else "",
                }
                for m in suspicious
            ]
            if susp_table:
                lines.append(tabulate(susp_table, headers="keys", tablefmt="github"))
            else:
                lines.append("(No suspicious sessions)")
            return "\n".join(lines)
        else:
            lines = []
            lines.append("Session Reliability Distribution:")
            dist_table = [
                {"Type": label, "Count": dist[k]}
                for k, label in [
                    ("all_passed", "All Passed"),
                    ("some_failed", "Some Failed"),
                    ("some_errored", "Some Errored"),
                    ("all_skipped", "All Skipped"),
                    ("mixed", "Mixed Outcomes"),
                ]
            ]
            lines.append(str(dist_table))
            lines.append("")
            lines.append("Top 5 Most Unreliable Sessions:")
            unrel_table = []
            for m in top_unrel:
                unrel_table.append(
                    {
                        "Session ID": m["session_id"],
                        "Date": str(m["date"])[:10] if m["date"] else "",
                        "SUT": m["sut"],
                        "Pass": m["passed"],
                        "Fail": m["failed"],
                        "Err": m["error"],
                        "Reliab (%)": (
                            f"{m['reliability']*100:.2f}"
                            if m["reliability"] is not None
                            else "N/A"
                        ),
                    }
                )
            if unrel_table:
                lines.append(str(unrel_table))
            else:
                lines.append("(No unreliable sessions)")
            lines.append("")
            lines.append("Suspicious Sessions (all skipped/xfailed/rerun):")
            susp_table = [
                {
                    "Session ID": m["session_id"],
                    "SUT": m["sut"],
                    "Total Tests": m["total_tests"],
                    "Date": str(m["date"])[:10] if m["date"] else "",
                }
                for m in suspicious
            ]
            if susp_table:
                lines.append(str(susp_table))
            else:
                lines.append("(No suspicious sessions)")
            return "\n".join(lines)

    def as_dict(self):
        """Return session-level metrics as a dict for dashboard rendering."""
        # Example: aggregate metrics for all sessions
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
                outcome_counts[t.outcome] = outcome_counts.get(t.outcome, 0) + 1
            metrics.append(
                {
                    "session_id": getattr(s, "session_id", ""),
                    "total_tests": total_tests,
                    **outcome_counts,
                }
            )
        return {"session_metrics": metrics}

    def insight(self, kind: str = "health", tabular: bool = True, **kwargs):
        if kind in {"summary", "health"}:
            from pytest_insight.facets.summary import SummaryInsight

            return SummaryInsight(self.sessions).as_dict()
        elif kind == "metrics":
            return self.metrics()
        elif kind == "key_metrics":
            return self.key_metrics()
        raise ValueError(f"Unsupported insight kind: {kind}")

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
            filtered = [
                s for s in filtered if getattr(s, "sut_name", None) == criteria["sut"]
            ]
        if "min_tests" in criteria:
            filtered = [
                s
                for s in filtered
                if len(getattr(s, "test_results", [])) >= criteria["min_tests"]
            ]
        if "max_tests" in criteria:
            filtered = [
                s
                for s in filtered
                if len(getattr(s, "test_results", [])) <= criteria["max_tests"]
            ]
        if "after" in criteria:
            filtered = [
                s
                for s in filtered
                if getattr(s, "session_start_time", None)
                and getattr(s, "session_start_time") >= criteria["after"]
            ]
        if "before" in criteria:
            filtered = [
                s
                for s in filtered
                if getattr(s, "session_start_time", None)
                and getattr(s, "session_start_time") <= criteria["before"]
            ]
        return SessionInsight(filtered)
