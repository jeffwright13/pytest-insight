from typing import Dict, List, Optional, Union, Pattern, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
import re
from pytest_insight.models import TestResult, TestSession

@dataclass
class SessionFilter:
    """Filter criteria for session searches."""
    sut: Optional[str] = None
    timespan: Optional[timedelta] = None
    limit: Optional[int] = None
    nodeid: Optional[Union[str, Pattern]] = None
    outcome: Optional[str] = None
    has_warnings: Optional[bool] = None
    tags: Optional[Dict[str, str]] = None

class InsightAnalyzer:
    """Core analytics engine with no UI dependencies."""

    def __init__(self, storage):
        self.storage = storage

    def get_sessions(
        self,
        filters: Optional[SessionFilter] = None
    ) -> List[TestSession]:
        """Get filtered test sessions."""
        sessions = self.storage.load_sessions()
        if not filters:
            return sessions

        filtered = sessions

        if filters.timespan:
            cutoff = datetime.now() - filters.timespan
            filtered = [s for s in filtered if s.session_start_time >= cutoff]

        if filters.sut:
            filtered = [s for s in filtered
                       if s.sut_name == filters.sut]

        if filters.nodeid:
            if isinstance(filters.nodeid, Pattern):
                filtered = [s for s in filtered
                          if any(filters.nodeid.match(t.nodeid)
                                for t in s.test_results)]
            else:
                filtered = [s for s in filtered
                          if any(filters.nodeid in t.nodeid
                                for t in s.test_results)]

        if filters.outcome:
            filtered = [s for s in filtered
                       if any(t.outcome == filters.outcome
                             for t in s.test_results)]

        if filters.has_warnings is not None:
            filtered = [s for s in filtered
                       if any(t.has_warning == filters.has_warnings
                             for t in s.test_results)]

        if filters.tags:
            filtered = [s for s in filtered
                       if all(s.session_tags.get(k) == v
                             for k, v in filters.tags.items())]

        if filters.limit:
            filtered = filtered[:filters.limit]

        return filtered

    def get_test_results(
        self,
        filters: Optional[SessionFilter] = None
    ) -> List[TestResult]:
        """Get filtered test results across all sessions."""
        results = []
        sessions = self.get_sessions(filters)

        for session in sessions:
            for result in session.test_results:
                if filters and filters.nodeid:
                    if isinstance(filters.nodeid, Pattern):
                        if filters.nodeid.match(result.nodeid):
                            results.append(result)
                    else:
                        # Exact match only
                        if result.nodeid == filters.nodeid:
                            results.append(result)
                else:
                    results.append(result)

        return results

    # Core Analysis Primitives
    def calculate_failure_rate(
        self,
        test_results: List[TestResult]
    ) -> float:
        """Calculate failure rate for given test results."""
        if not test_results:
            return 0.0

        # Only consider non-skipped tests
        relevant_tests = [r for r in test_results if r.outcome != "skipped"]
        if not relevant_tests:
            return 0.0

        failures = sum(1 for r in relevant_tests if r.outcome == "failed")
        return failures / len(relevant_tests)

    def calculate_test_metrics(
        self,
        test_results: List[TestResult]
    ) -> Dict[str, float]:
        """
        Calculate basic test metrics.

        Returns:
            Dict containing:
                - total_count: Total number of test runs
                - failure_rate: Rate of failures (0.0 - 1.0)
                - avg_duration: Average test duration
                - min_duration: Minimum test duration
                - max_duration: Maximum test duration
        """
        if not test_results:
            return {
                "total_count": 0,
                "failure_rate": 0.0,
                "avg_duration": 0.0,
                "min_duration": 0.0,
                "max_duration": 0.0
            }

        durations = [r.duration for r in test_results]
        return {
            "total_count": len(test_results),
            "failure_rate": self.calculate_failure_rate(test_results),
            "avg_duration": sum(durations) / len(durations),
            "min_duration": min(durations),
            "max_duration": max(durations)
        }

    def detect_trends(
        self,
        test_results: List[TestResult],
        metric: str = "duration"
    ) -> Dict[str, any]:
        """
        Detect trends in specified metric over time.

        Args:
            test_results: List of test results to analyze
            metric: Metric to analyze (duration, outcome)

        Returns:
            Dict containing trend analysis:
                - trend: Direction of trend (increasing, decreasing, stable)
                - volatility: Measure of result stability
                - data_points: Time series data for plotting
        """
        if not test_results or len(test_results) < 2:
            return {
                "trend": "insufficient_data",
                "volatility": 0.0,
                "data_points": []
            }

        # Sort by time
        sorted_results = sorted(test_results, key=lambda r: r.start_time)

        # Collect time series data
        if metric == "duration":
            values = [r.duration for r in sorted_results]
            times = [r.start_time for r in sorted_results]
        elif metric == "outcome":
            values = [1.0 if r.outcome == "passed" else 0.0 for r in sorted_results]
            times = [r.start_time for r in sorted_results]
        else:
            raise ValueError(f"Unsupported metric: {metric}")

        # Calculate trend
        first_value = sum(values[:3]) / min(3, len(values))  # Average first 3
        last_value = sum(values[-3:]) / min(3, len(values))  # Average last 3

        if abs(last_value - first_value) < 0.1 * first_value:
            trend = "stable"
        else:
            trend = "increasing" if last_value > first_value else "decreasing"

        # Calculate volatility (standard deviation / mean)
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        volatility = (variance ** 0.5) / mean if mean != 0 else 0.0

        return {
            "trend": trend,
            "volatility": volatility,
            "data_points": [
                {"time": t.isoformat(), "value": v}
                for t, v in zip(times, values)
            ]
        }

    def calculate_metrics(self, results: List[TestResult]) -> Dict[str, Any]:
        """Calculate core metrics from test results."""
        base_metrics = self.calculate_test_metrics(results)

        # Add additional metrics
        return {
            **base_metrics,
            "total_duration": sum(r.duration for r in results),
            "success_rate": 1.0 - base_metrics["failure_rate"],
            "skipped_rate": len([r for r in results if r.outcome == "skipped"]) / len(results) if results else 0.0,
            "warning_rate": len([r for r in results if r.has_warning]) / len(results) if results else 0.0
        }

    def analyze_trends(self, results: List[TestResult]) -> Dict[str, Any]:
        """Analyze test result trends."""
        return {
            "duration_trend": self.detect_trends(results, metric="duration"),
            "outcome_trend": self.detect_trends(results, metric="outcome"),
            "total_executions": len(results),
            "unique_tests": len(set(r.nodeid for r in results))
        }

    def detect_patterns(self, results: List[TestResult]) -> Dict[str, Any]:
        """Detect patterns in test failures."""
        failed_results = [r for r in results if r.outcome == "failed"]

        return {
            "failure_patterns": {
                "by_nodeid": self._group_failures_by_nodeid(failed_results),
                "by_time": self._group_failures_by_time(failed_results),
                "by_duration": self._group_failures_by_duration(failed_results)
            },
            "total_failures": len(failed_results),
            "failure_rate_over_time": self.detect_trends(failed_results, metric="outcome")
        }

    def _group_failures_by_nodeid(self, failed_results: List[TestResult]) -> Dict[str, Any]:
        """Group failures by test nodeid and analyze patterns."""
        grouped = {}
        for result in failed_results:
            if result.nodeid not in grouped:
                grouped[result.nodeid] = {
                    "count": 0,
                    "durations": [],
                    "timestamps": []
                }

            data = grouped[result.nodeid]
            data["count"] += 1
            data["durations"].append(result.duration)
            data["timestamps"].append(result.start_time)

        return {
            nodeid: {
                "failure_count": data["count"],
                "avg_duration": sum(data["durations"]) / len(data["durations"]),
                "first_failure": min(data["timestamps"]),
                "last_failure": max(data["timestamps"])
            }
            for nodeid, data in grouped.items()
        }

    def _group_failures_by_time(self, failed_results: List[TestResult]) -> Dict[str, Any]:
        """Group failures by time and analyze patterns."""
        grouped = {}
        for result in failed_results:
            key = result.start_time.replace(second=0, microsecond=0)
            if key not in grouped:
                grouped[key] = {
                    "count": 0,
                    "nodeids": set()
                }

            data = grouped[key]
            data["count"] += 1
            data["nodeids"].add(result.nodeid)

        return {
            time.isoformat(): {
                "failure_count": data["count"],
                "unique_failures": len(data["nodeids"])
            }
            for time, data in grouped.items()
        }

    def _group_failures_by_duration(self, failed_results: List[TestResult]) -> Dict[str, Any]:
        """Group failures by duration and analyze patterns."""
        grouped = {}
        for result in failed_results:
            key = int(result.duration / 10) * 10
            if key not in grouped:
                grouped[key] = {
                    "count": 0,
                    "nodeids": set()
                }

            data = grouped[key]
            data["count"] += 1
            data["nodeids"].add(result.nodeid)

        return {
            f"{key}s": {
                "failure_count": data["count"],
                "unique_failures": len(data["nodeids"])
            }
            for key, data in grouped.items()
        }

    def calculate_health_scores(self, results: List[TestResult]) -> Dict[str, float]:
        """Calculate health scores for each test."""
        metrics = self.calculate_metrics(results)
        trends = self.analyze_trends(results)
        patterns = self.detect_patterns(results)

        scores = {}
        for result in results:
            scores[result.nodeid] = (
                (1 - metrics["failure_rate"])
                * 0.4  # Failure weight
                + (1 - min(metrics["avg_duration"] / 10.0, 1.0))
                * 0.3  # Duration weight
                + (1 - (len([r for r in results if r.has_warning]) / len(results)))
                * 0.3  # Warning weight
            ) * 100

        return scores

    def analyze_warnings(self, results: List[TestResult]) -> Dict[str, Any]:
        """Analyze warning patterns in test results."""
        warnings = [r for r in results if r.has_warning]
        return {
            "warning_freq": len(warnings) / len(results) if results else 0.0,
            "warning_patterns": self._group_warnings_by_nodeid(warnings)
        }

    def _group_warnings_by_nodeid(self, warning_results: List[TestResult]) -> Dict[str, Any]:
        """Group warnings by test nodeid and analyze patterns."""
        grouped = {}
        for result in warning_results:
            if result.nodeid not in grouped:
                grouped[result.nodeid] = {
                    "count": 0,
                    "timestamps": []
                }

            data = grouped[result.nodeid]
            data["count"] += 1
            data["timestamps"].append(result.start_time)

        return {
            nodeid: {
                "warning_count": data["count"],
                "first_warning": min(data["timestamps"]),
                "last_warning": max(data["timestamps"])
            }
            for nodeid, data in grouped.items()
        }
