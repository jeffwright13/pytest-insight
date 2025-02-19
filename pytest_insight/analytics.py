"""Analytics queries for pytest-insight."""

from collections import Counter
from statistics import mean, stdev
from typing import Dict, List, Set

from pytest_insight.models import TestResult, TestSession


class SUTAnalytics:
    """Analytics queries for a specific SUT's test history."""

    def __init__(self, sessions: List[TestSession]):
        self.sessions = sessions
        self._nodeids = self._get_all_nodeids()

    def _get_all_nodeids(self) -> Set[str]:
        """Get all unique test nodeids across sessions."""
        return {test.nodeid for s in self.sessions for test in s.test_results}

    def stability_metrics(self) -> Dict:
        """Calculate test stability metrics."""
        flaky_tests = set()
        failure_rates = {}
        rerun_rates = {}

        for nodeid in self._nodeids:
            test_runs = self._get_test_history(nodeid)
            failure_rates[nodeid] = sum(
                1 for t in test_runs if t.outcome == "FAILED"
            ) / len(test_runs)
            rerun_rates[nodeid] = sum(
                1 for t in test_runs if t.outcome == "RERUN"
            ) / len(test_runs)
            if rerun_rates[nodeid] > 0:
                flaky_tests.add(nodeid)

        return {
            "flaky_tests": flaky_tests,
            "failure_rates": failure_rates,
            "rerun_rates": rerun_rates,
            "most_unstable": sorted(
                failure_rates.items(), key=lambda x: x[1], reverse=True
            )[:5],
        }

    def performance_metrics(self) -> Dict:
        """Calculate performance metrics across sessions."""
        durations: Dict[str, List[float]] = {}

        for nodeid in self._nodeids:
            test_runs = self._get_test_history(nodeid)
            durations[nodeid] = [t.duration for t in test_runs]

        return {
            "avg_duration": {k: mean(v) for k, v in durations.items()},
            "std_deviation": {
                k: stdev(v) if len(v) > 1 else 0 for k, v in durations.items()
            },
            "slowest_tests": sorted(
                [(k, mean(v)) for k, v in durations.items()],
                key=lambda x: x[1],
                reverse=True,
            )[:5],
        }

    def warning_metrics(self) -> Dict:
        """Analyze warning patterns."""
        warnings = []
        for session in self.sessions:
            for test in session.test_results:
                if test.has_warning:
                    warnings.append((test.nodeid, test.caplog))

        return {
            "warning_freq": Counter(w[0] for w in warnings),
            "common_warnings": Counter(w[1] for w in warnings).most_common(5),
        }

    def _get_test_history(self, nodeid: str) -> List[TestResult]:
        """Get all results for a specific test across sessions."""
        return [
            test
            for session in self.sessions
            for test in session.test_results
            if test.nodeid == nodeid
        ]

    def health_score(self) -> Dict[str, float]:
        """Calculate overall health score for each test."""
        stability = self.stability_metrics()
        perf = self.performance_metrics()
        warnings = self.warning_metrics()

        scores = {}
        for nodeid in self._nodeids:
            scores[nodeid] = (
                (1 - stability["failure_rates"].get(nodeid, 0))
                * 0.4  # Stability weight
                + (1 - min(perf["avg_duration"].get(nodeid, 0) / 10.0, 1.0))
                * 0.3  # Performance weight
                + (1 - (warnings["warning_freq"].get(nodeid, 0) / len(self.sessions)))
                * 0.3  # Warning weight
            ) * 100

        return scores
