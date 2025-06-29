"""Analysis components for pytest-insight.

This module provides classes for analyzing test patterns and health:
1. Analysis - Top-level entry point for analysis
2. SessionAnalysis - Session-level analytics
3. TestAnalysis - Test-level analytics
4. MetricsAnalysis - High-level metrics

The implementation follows the query system design by:
- Always preserving session context when analyzing tests
- Using pattern matching for test filtering
- Maintaining relationships between tests within sessions
- Supporting both session and test-level filtering

SessionAnalysis Class:
- Implements session-level analytics with failure rate calculation and test metrics
- Preserves session context when analyzing trends
- Provides detailed trend detection for duration, failures, and warnings

TestAnalysis Class:
- Focuses on individual test patterns while maintaining session relationships
- Implements stability metrics with reliability detection
- Provides performance analysis with outlier detection
- Analyzes warning patterns and correlations

MetricsAnalysis Class:
- Calculates overall health scores with weighted components
- Generates actionable recommendations based on analysis
- Preserves session context for accurate trend detection
- Implements sophisticated scoring algorithms for stability, performance, and warnings

Analysis Class:
- Serves as the top-level entry point
- Provides unified access to all analysis components
- Maintains consistent session context across components
"""

from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean, stdev
from typing import Any, Callable, Dict, List, Optional
from zoneinfo import ZoneInfo

from pytest_insight.core.insights import TestInsights
from pytest_insight.core.models import (
    TestOutcome,
    TestSession,
)
from pytest_insight.core.query import Query
from pytest_insight.core.storage import BaseStorage, get_storage_instance
from pytest_insight.utils.utils import NormalizedDatetime


class AnalysisBase:
    """Base class for all analysis classes."""

    def __init__(self):
        """Initialize base analysis class."""
        pass

    def _filter_sessions_by_days(self, days: Optional[int]) -> List[TestSession]:
        """Filter sessions by the number of days from the most recent session.

        Args:
            days: Number of days to look back from the most recent session

        Returns:
            List of filtered sessions
        """
        if not hasattr(self, "_sessions") or self._sessions is None or days is None:
            return getattr(self, "_sessions", [])

        # Find the most recent session timestamp
        timestamps = []
        for s in self._sessions:
            if hasattr(s, "session_start_time") and s.session_start_time is not None:
                timestamps.append(s.session_start_time)
            elif hasattr(s, "timestamp") and s.timestamp is not None:
                timestamps.append(s.timestamp)

        if not timestamps:
            return self._sessions

        most_recent = max(timestamps)

        # Calculate the cutoff date
        cutoff = most_recent - timedelta(days=days)

        # Filter sessions by timestamp
        filtered_sessions = []
        for s in self._sessions:
            session_time = None
            if hasattr(s, "session_start_time") and s.session_start_time is not None:
                session_time = s.session_start_time
            elif hasattr(s, "timestamp") and s.timestamp is not None:
                session_time = s.timestamp

            if session_time is not None and session_time >= cutoff:
                filtered_sessions.append(s)

        return filtered_sessions

    def _get_all_test_results(self):
        """
        Get all test results from all sessions.

        Returns:
            List of all test results across all sessions
        """
        all_tests = []
        for session in getattr(self, "_sessions", []):
            if hasattr(session, "tests") and session.tests:
                all_tests.extend(session.tests)
        return all_tests


class SessionAnalysis(AnalysisBase):
    """Session-level analytics.

    Analyzes patterns and metrics at the test session level:
    - Failure rates over time
    - Test execution metrics
    - Trend detection
    """

    def __init__(
        self,
        storage: Optional[BaseStorage] = None,
        sessions: Optional[List[TestSession]] = None,
        profile_name: Optional[str] = None,
    ):
        """Initialize with storage and optional session list.

        Args:
            storage: Storage instance for accessing test data. If None, uses profile_name.
            sessions: Optional list of sessions to analyze. If not provided,
                     will analyze all sessions from storage.
            profile_name: Optional profile name to use for storage configuration.
                         Takes precedence over storage parameter if both are provided.
        """
        super().__init__()
        self._profile_name = profile_name

        if storage is None and profile_name is not None:
            storage = get_storage_instance(profile_name=profile_name)
        elif storage is not None and profile_name is None:
            # Try to get profile name from storage if available
            profile_name = getattr(storage, "profile_name", None)

        self.storage = storage
        self._sessions = sessions
        # Use profile-only approach for Query initialization
        self._query = Query(profile_name=profile_name)

    def _get_sessions(self, days: Optional[int] = None) -> List[TestSession]:
        """Get sessions to analyze, optionally filtered by date range.

        Args:
            days: Optional number of days to look back

        Returns:
            List of sessions to analyze
        """
        if self._sessions is not None:
            sessions = self._sessions
            if days:
                cutoff = datetime.now(ZoneInfo("UTC")) - timedelta(days=days)
                sessions = [s for s in sessions if s.session_start_time >= cutoff]
            return sessions

        query = self._query
        if days:
            query = query.in_last_days(days)
        return query.execute().sessions

    def failure_rate(self, days: Optional[int] = None) -> float:
        """Calculate session failure rate.

        Calculates the rate of sessions containing any failed tests over
        the total number of sessions in the time period.

        Args:
            days: Optional number of days to look back. If not provided,
                 calculates over all available sessions.

        Returns:
            Failure rate as float between 0 and 1
        """
        sessions = self._get_sessions(days)
        if not sessions:
            return 0.0

        failed_sessions = sum(
            1 for session in sessions if any(test.outcome == TestOutcome.FAILED for test in session.test_results)
        )

        return failed_sessions / len(sessions)

    def test_metrics(self, days: Optional[int] = None, chunk_size: int = 1000) -> Dict[str, Any]:
        """Calculate key test metrics for sessions.

        Analyzes test metrics while preserving session context to identify:
        - Overall execution statistics
        - Test uniqueness and repetition
        - Unreliable test detection

        Args:
            days: Optional number of days to look back
            chunk_size: Number of sessions to process at once for large datasets

        Returns:
            Dict containing metrics:
            - total_tests: Total number of tests executed
            - unique_tests: Number of unique test nodeids
            - avg_duration: Average test duration in seconds
            - max_duration: Maximum test duration in seconds
            - min_duration: Minimum test duration in seconds
            - failed_tests: Number of failed tests
            - passed_tests: Number of passed tests
            - skipped_tests: Number of skipped tests
            - avg_tests_per_session: Average tests per session
        """
        sessions = self._get_sessions(days)

        if not sessions:
            return {
                "total_tests": 0,
                "unique_tests": 0,
                "avg_duration": 0,
                "max_duration": 0,
                "min_duration": 0,
                "failed_tests": 0,
                "passed_tests": 0,
                "skipped_tests": 0,
                "avg_tests_per_session": 0,
            }

        # Initialize counters
        total_tests = 0
        unique_tests = set()
        durations = []
        failed_tests = 0
        passed_tests = 0
        skipped_tests = 0

        # Process sessions in chunks for large datasets
        session_chunks = [sessions[i : i + chunk_size] for i in range(0, len(sessions), chunk_size)]

        session_count = 0
        for chunk in session_chunks:
            for session in chunk:
                # Process each test result
                for test_result in session.test_results:
                    total_tests += 1
                    unique_tests.add(test_result.nodeid)

                    if test_result.duration is not None:
                        durations.append(test_result.duration)

                    if test_result.outcome == TestOutcome.FAILED:
                        failed_tests += 1
                    elif test_result.outcome == TestOutcome.PASSED:
                        passed_tests += 1
                    elif test_result.outcome == TestOutcome.SKIPPED:
                        skipped_tests += 1

                session_count += 1

        # Calculate metrics
        avg_duration = mean(durations) if durations else 0
        max_duration = max(durations) if durations else 0
        min_duration = min(durations) if durations else 0
        avg_tests_per_session = total_tests / len(sessions) if sessions else 0

        return {
            "total_tests": total_tests,
            "unique_tests": len(unique_tests),
            "avg_duration": avg_duration,
            "max_duration": max_duration,
            "min_duration": min_duration,
            "failed_tests": failed_tests,
            "passed_tests": passed_tests,
            "skipped_tests": skipped_tests,
            "avg_tests_per_session": avg_tests_per_session,
        }

    def detect_trends(self, days: Optional[int] = None, window_size: int = 7) -> Dict[str, Any]:
        """Detect significant trends in session data.

        Analyzes trends while preserving session context to identify:
        - Changes in execution time
        - Changes in failure patterns
        - Changes in warning patterns

        Args:
            days: Optional number of days to look back
            window_size: Size of the window for trend analysis (in days)

        Returns:
            Dict containing trend information:
            - duration: Dict with duration trend info
                - direction: 'increasing', 'decreasing', or 'stable'
                - change_percent: Percentage change
                - significant: Boolean indicating if change is statistically significant
            - failures: Dict with failure trend info
                - direction: 'increasing', 'decreasing', or 'stable'
                - change_percent: Percentage change
                - significant: Boolean indicating if change is statistically significant
            - warnings: Dict with warning trend info
                - direction: 'increasing', 'decreasing', or 'stable'
                - change_percent: Percentage change
                - significant: Boolean indicating if change is statistically significant
                - common_warnings: Most frequent warning types
        """
        sessions = self._get_sessions(days)

        if not sessions:
            return {
                "duration": {
                    "direction": "stable",
                    "change_percent": 0.0,
                    "significant": False,
                },
                "failures": {
                    "direction": "stable",
                    "change_percent": 0.0,
                    "significant": False,
                },
                "warnings": {
                    "direction": "stable",
                    "change_percent": 0.0,
                    "significant": False,
                    "common_warnings": [],
                },
            }

        # Sort sessions by start time using NormalizedDatetime to handle timezone differences
        def get_session_time(session):
            if hasattr(session, "session_start_time") and session.session_start_time:
                return NormalizedDatetime(session.session_start_time)
            elif hasattr(session, "timestamp") and session.timestamp:
                return NormalizedDatetime(session.timestamp)
            else:
                # Default to epoch start if no timestamp available
                return NormalizedDatetime(datetime.fromtimestamp(0, tz=ZoneInfo("UTC")))

        sessions = sorted(sessions, key=get_session_time)

        # Limit to a reasonable number of sessions for trend analysis
        MAX_SESSIONS = 100
        if len(sessions) > MAX_SESSIONS:
            # Take evenly distributed samples if we have too many sessions
            step = len(sessions) // MAX_SESSIONS
            sessions = [sessions[i] for i in range(0, len(sessions), step)][:MAX_SESSIONS]

        # Analyze duration trends
        duration_trend = self._analyze_duration_trend(sessions, window_size)

        # Analyze failure trends
        failure_trend = self._analyze_failure_trend(sessions, window_size)

        # Analyze warning trends
        warning_trend = self._analyze_warning_trend(sessions, window_size)

        return {
            "duration": duration_trend,
            "failures": failure_trend,
            "warnings": warning_trend,
        }

    def _analyze_duration_trend(self, sessions: List[TestSession], window_size: int) -> Dict[str, Any]:
        """Analyze trends in test execution duration."""
        # Calculate average duration per session (with a limit on tests per session)
        MAX_TESTS_PER_SESSION = 1000
        durations = []

        for session in sessions:
            # Limit the number of tests to process
            test_results = (
                session.test_results[:MAX_TESTS_PER_SESSION]
                if len(session.test_results) > MAX_TESTS_PER_SESSION
                else session.test_results
            )
            session_duration = sum(t.duration for t in test_results)
            durations.append(session_duration)

        if len(durations) < 2:
            return {"direction": "stable", "change_percent": 0.0, "significant": False}

        # Fast trend calculation using numpy if available
        try:
            import numpy as np

            x = np.arange(len(durations))
            A = np.vstack([x, np.ones(len(x))]).T
            slope, _ = np.linalg.lstsq(A, durations, rcond=None)[0]
        except ImportError:
            # Fallback to simple calculation if numpy not available
            x = list(range(len(durations)))
            x_mean = sum(x) / len(x)
            y_mean = sum(durations) / len(durations)

            numerator = sum((x[i] - x_mean) * (y - y_mean) for i, y in enumerate(durations))
            denominator = sum((x[i] - x_mean) ** 2 for i in x)

            if abs(denominator) < 1e-10:
                slope = 0
            else:
                slope = numerator / denominator

        return {
            "direction": ("increasing" if slope > 0.1 else "decreasing" if slope < -0.1 else "stable"),
            "change_percent": (abs(slope) * 100 if abs(slope) < 100 else 100),  # Cap at 100%
            "significant": False,  # TODO: Implement significance check
        }

    def _analyze_failure_trend(self, sessions: List[TestSession], window_size: int) -> Dict[str, Any]:
        """Analyze trends in test failures while preserving session context."""
        # Strict limits to prevent excessive computation
        MAX_TESTS_PER_SESSION = 500
        MAX_WINDOWS = 20

        # Group sessions by time window (limit number of windows)
        windows = []
        current_window = []
        window_count = 0

        for session in sessions:
            current_window.append(session)
            if len(current_window) >= window_size:
                windows.append(current_window)
                current_window = []
                window_count += 1
                if window_count >= MAX_WINDOWS:
                    break

        if current_window:
            windows.append(current_window)

        # Calculate failure rate for each window
        failure_rates = []
        for window in windows:
            failed_sessions = 0
            for s in window:
                # Limit tests to process
                test_results = (
                    s.test_results[:MAX_TESTS_PER_SESSION]
                    if len(s.test_results) > MAX_TESTS_PER_SESSION
                    else s.test_results
                )
                if any(t.outcome == TestOutcome.FAILED for t in test_results):
                    failed_sessions += 1

            failure_rate = failed_sessions / len(window) if window else 0
            failure_rates.append(failure_rate)

        # Skip correlated failures calculation - it's expensive and not used in the output

        if len(failure_rates) < 2:
            return {"direction": "stable", "change_percent": 0.0, "significant": False}

        # Fast trend calculation using numpy if available
        try:
            import numpy as np

            x = np.arange(len(failure_rates))
            A = np.vstack([x, np.ones(len(x))]).T
            slope, _ = np.linalg.lstsq(A, failure_rates, rcond=None)[0]
        except ImportError:
            # Fallback to simple calculation
            x = list(range(len(failure_rates)))
            x_mean = sum(x) / len(x)
            y_mean = sum(failure_rates) / len(failure_rates)

            numerator = sum((i - x_mean) * (rate - y_mean) for i, rate in enumerate(failure_rates))
            denominator = sum((i - x_mean) ** 2 for i in x)

            if abs(denominator) < 1e-10:
                slope = 0
            else:
                slope = numerator / denominator

        return {
            "direction": ("worsening" if slope > 0.05 else "improving" if slope < -0.05 else "stable"),
            "change_percent": (abs(slope) * 100 if abs(slope) < 100 else 100),  # Cap at 100%
            "significant": False,  # TODO: Implement significance check
        }

    def _analyze_warning_trend(self, sessions: List[TestSession], window_size: int) -> Dict[str, Any]:
        """Analyze trends in test warnings."""
        # Strict limits to prevent excessive computation
        MAX_TESTS_PER_SESSION = 500
        MAX_WARNINGS_TO_TRACK = 100

        # Track warnings per session
        warning_counts = []
        warning_types = defaultdict(int)
        warning_types_count = 0

        for session in sessions:
            # Limit tests to process
            test_results = (
                session.test_results[:MAX_TESTS_PER_SESSION]
                if len(session.test_results) > MAX_TESTS_PER_SESSION
                else session.test_results
            )

            session_warnings = sum(1 for test in test_results if test.has_warning)
            warning_counts.append(session_warnings)

            # Track warning types (limited)
            for test in test_results:
                if test.has_warning and warning_types_count < MAX_WARNINGS_TO_TRACK:
                    warning_types[test.nodeid] += 1
                    warning_types_count += 1

        if len(warning_counts) < 2:
            return {"direction": "stable", "change_percent": 0.0, "significant": False}

        # Fast trend calculation using numpy if available
        try:
            import numpy as np

            x = np.arange(len(warning_counts))
            A = np.vstack([x, np.ones(len(x))]).T
            slope, _ = np.linalg.lstsq(A, warning_counts, rcond=None)[0]
        except ImportError:
            # Fallback to simple calculation
            x = list(range(len(warning_counts)))
            x_mean = sum(x) / len(x)
            y_mean = sum(warning_counts) / len(warning_counts)

            numerator = sum((i - x_mean) * (count - y_mean) for i, count in enumerate(warning_counts))
            denominator = sum((i - x_mean) ** 2 for i in x)

            if abs(denominator) < 1e-10:
                slope = 0
            else:
                slope = numerator / denominator

        # Find most common warning types (limit to top 5)
        common_warnings = sorted(
            ((test, count) for test, count in warning_types.items()),
            key=lambda x: x[1],
            reverse=True,
        )[:5]

        return {
            "direction": ("increasing" if slope > 0.05 else "decreasing" if slope < -0.05 else "stable"),
            "change_percent": (abs(slope) * 100 if abs(slope) < 100 else 100),  # Cap at 100%
            "significant": False,  # TODO: Implement significance check
            "common_warnings": [{"test": test, "count": count} for test, count in common_warnings],
        }

    def outcome_distribution(self, days: Optional[int] = None) -> Dict[str, int]:
        """
        Calculate the distribution of test outcomes across sessions.

        Args:
            days: Optional number of days to limit the analysis to

        Returns:
            Dictionary mapping outcome names to counts
        """
        # Filter sessions by days if specified
        sessions = self._filter_sessions_by_days(days) if days else self._sessions

        if not sessions:
            return {}

        # Initialize outcome counter
        outcome_counts = {}

        # Process each session
        for session in sessions:
            # Count outcomes in this session
            for test_result in session.test_results:
                outcome_str = test_result.outcome.to_str()
                outcome_counts[outcome_str] = outcome_counts.get(outcome_str, 0) + 1

        return outcome_counts

    def co_failures(self, min_correlation: float = 0.7, min_occurrences: int = 3) -> List[Dict[str, Any]]:
        """
        Identify clusters of tests that tend to fail together.

        Args:
            min_correlation: Minimum correlation coefficient to consider tests related
            min_occurrences: Minimum number of co-occurrences to consider

        Returns:
            List of co-failure clusters with correlation scores
        """
        if not self._sessions:
            return []

        # Extract all test failures from sessions
        test_failures = {}
        session_failures = {}

        # Process each session
        for session in self._sessions:
            # Record failures in this session
            session_id = session.session_id
            session_failures[session_id] = []

            for test_result in session.test_results:
                if test_result.outcome.is_failed():
                    test_id = test_result.nodeid

                    # Initialize test entry if not exists
                    if test_id not in test_failures:
                        test_failures[test_id] = set()

                    # Record that this test failed in this session
                    test_failures[test_id].add(session_id)
                    session_failures[session_id].append(test_id)

        # Find correlations between tests
        correlations = {}
        test_ids = list(test_failures.keys())

        # Skip if not enough tests
        if len(test_ids) < 2:
            return []

        # Compare each pair of tests
        for i in range(len(test_ids)):
            for j in range(i + 1, len(test_ids)):
                test_a = test_ids[i]
                test_b = test_ids[j]

                # Get sessions where each test failed
                sessions_a = test_failures[test_a]
                sessions_b = test_failures[test_b]

                # Calculate co-occurrence
                co_failures = sessions_a.intersection(sessions_b)

                # Skip if not enough co-occurrences
                if len(co_failures) < min_occurrences:
                    continue

                # Calculate correlation coefficient (Jaccard similarity)
                correlation = len(co_failures) / len(sessions_a.union(sessions_b))

                # Record if above threshold
                if correlation >= min_correlation:
                    pair_key = (test_a, test_b)
                    correlations[pair_key] = {
                        "correlation": correlation,
                        "co_failures": len(co_failures),
                        "tests": [test_a, test_b],
                    }

        # Build clusters from correlations
        clusters = []
        processed_pairs = set()

        # Sort correlations by strength
        sorted_correlations = sorted(correlations.items(), key=lambda x: x[1]["correlation"], reverse=True)

        # Process each correlation
        for (test_a, test_b), data in sorted_correlations:
            # Skip if already in a cluster
            if (test_a, test_b) in processed_pairs:
                continue

            # Start new cluster
            cluster = {
                "correlation": data["correlation"],
                "co_failures": data["co_failures"],
                "tests": [test_a, test_b],
            }
            processed_pairs.add((test_a, test_b))

            # Try to expand cluster
            for (other_a, other_b), other_data in sorted_correlations:
                # Skip if already processed
                if (other_a, other_b) in processed_pairs:
                    continue

                # Check if connected to cluster
                if other_a in cluster["tests"] or other_b in cluster["tests"]:
                    # Add the test not in the cluster
                    new_test = other_b if other_a in cluster["tests"] else other_a
                    if new_test not in cluster["tests"]:
                        cluster["tests"].append(new_test)

                    # Mark as processed
                    processed_pairs.add((other_a, other_b))

                    # Update correlation (use average)
                    cluster["correlation"] = (cluster["correlation"] + other_data["correlation"]) / 2

            # Add cluster to results
            clusters.append(cluster)

        return clusters

    def health_score(self) -> Dict[str, Any]:
        """
        Calculate a health score for the test suite based on various metrics.

        Returns:
            Dictionary with overall health score and component scores
        """
        if not self._sessions:
            return {}

        # Initialize scores
        stability_score = 0.0
        performance_score = 0.0

        # Get stability metrics
        stability_data = self.stability()
        unreliable_tests = stability_data.get("unreliable_tests", [])
        unstable_tests = stability_data.get("unstable_tests", [])

        # Calculate stability score (100 - percentage of unreliable/unstable tests)
        test_results = self._get_all_test_results()
        unique_tests = set(test.nodeid for test in test_results)
        total_unique_tests = len(unique_tests)

        if total_unique_tests > 0:
            unreliable_count = len(unreliable_tests)
            unstable_count = len(unstable_tests)
            problem_tests_pct = (unreliable_count + unstable_count) / total_unique_tests * 100
            stability_score = max(0, 100 - problem_tests_pct)

        # Get session analysis for trends
        session_analysis = SessionAnalysis(self._sessions)

        # Calculate performance score based on duration trends
        trends = session_analysis.detect_trends()
        duration_trend = trends.get("duration", {})

        # Base performance score on trend direction and significance
        performance_score = 70  # Default score

        if duration_trend:
            direction = duration_trend.get("direction", "stable")
            significant = duration_trend.get("significant", False)
            change_percent = duration_trend.get("change_percent", 0)

            if direction == "improving":
                # Tests getting faster
                performance_score += 20 if significant else 10
            elif direction == "degrading":
                # Tests getting slower
                performance_score -= 20 if significant else 10

            # Adjust based on magnitude of change
            if abs(change_percent) > 20:
                performance_score += 10 if direction == "improving" else -10

        # Ensure scores are within 0-100 range
        stability_score = max(0, min(100, stability_score))
        performance_score = max(0, min(100, performance_score))

        # Calculate overall score (weighted average)
        overall_score = 0.7 * stability_score + 0.3 * performance_score

        # Calculate category scores
        categories = {}

        # Group tests by category (using directory structure)
        test_by_category = {}
        for test in test_results:
            # Extract category from nodeid (first directory)
            parts = test.nodeid.split("/")
            category = parts[0] if len(parts) > 1 else "unknown"

            if category not in test_by_category:
                test_by_category[category] = []

            test_by_category[category].append(test)

        # Calculate score for each category
        for category, tests in test_by_category.items():
            # Skip categories with too few tests
            if len(tests) < 5:
                continue

            # Calculate failure rate
            failures = sum(1 for test in tests if test.outcome.is_failed())
            failure_rate = failures / len(tests) if tests else 0

            # Calculate category score
            category_score = 100 - (failure_rate * 100)
            categories[category] = category_score

        return {
            "overall_score": overall_score,
            "stability_score": stability_score,
            "performance_score": performance_score,
            "categories": categories,
        }

    def behavior_changes(self, days: Optional[int] = 30) -> Dict[str, List[Dict[str, Any]]]:
        """
        Identify tests that have recently changed behavior (passing to failing or vice versa).

        Args:
            days: Number of days to consider for "recent" changes

        Returns:
            Dictionary with lists of recently failing and recently passing tests
        """
        if not self._sessions:
            return {}

        # Filter sessions by days if specified
        session_analysis = SessionAnalysis(self._sessions)
        sessions = session_analysis._filter_sessions_by_days(days) if days else self._sessions

        if not sessions:
            return {}

        # Sort sessions by timestamp
        sessions = sorted(sessions, key=lambda s: s.session_start_time)

        # Get test outcomes by test ID
        test_outcomes = defaultdict(list)
        for session in sessions:
            for test in session.test_results:
                test_outcomes[test.nodeid].append({"outcome": test.outcome, "timestamp": session.session_start_time})

        # Identify tests with behavior changes
        recently_failing = []
        recently_passing = []

        # Process each test to identify behavior changes
        for test_id, history in test_outcomes.items():
            # Skip if not enough history
            if len(history) < 6:
                continue

            # Split history into recent and older
            recent_outcomes = history[-3:]
            older_outcomes = history[:-3]

            # Check if recently failing
            was_passing = all(not o["outcome"].is_failed() for o in older_outcomes[-3:])
            now_failing = all(o["outcome"].is_failed() for o in recent_outcomes)

            if was_passing and now_failing:
                # Find last passed timestamp
                last_passed = None
                for o in reversed(history):
                    if not o["outcome"].is_failed():
                        last_passed = o["timestamp"]
                        break

                recently_failing.append(
                    {
                        "nodeid": test_id,
                        "last_passed": last_passed,
                        "failure_streak": sum(1 for o in recent_outcomes if o["outcome"].is_failed()),
                    }
                )

            # Check if recently passing
            was_failing = all(o["outcome"].is_failed() for o in older_outcomes[-3:])
            now_passing = all(not o["outcome"].is_failed() for o in recent_outcomes)

            if was_failing and now_passing:
                # Find last failed timestamp
                last_failed = None
                for o in reversed(history):
                    if o["outcome"].is_failed():
                        last_failed = o["timestamp"]
                        break

                recently_passing.append(
                    {
                        "nodeid": test_id,
                        "last_failed": last_failed,
                        "success_streak": sum(1 for o in recent_outcomes if not o["outcome"].is_failed()),
                    }
                )

        return {
            "recently_failing": recently_failing,
            "recently_passing": recently_passing,
        }

    def top_failing_tests(self, days: Optional[int] = None, limit: int = 10) -> Dict[str, Any]:
        """Identify tests that fail most frequently across sessions.

        This metric helps identify systemic issues or brittle tests by clustering
        failures and ranking tests by their failure frequency.

        Args:
            days: Optional number of days to look back
            limit: Maximum number of tests to return

        Returns:
            Dict containing:
            - top_failing: List of dicts with test nodeids and their failure metrics
            - failure_distribution: Distribution of failures across tests
            - total_failures: Total number of test failures
        """
        sessions = self._get_sessions(days)

        # Track failures by test
        failure_counts = defaultdict(int)
        total_runs = defaultdict(int)

        # Collect failure data from all sessions
        for session in sessions:
            if hasattr(session, "test_results") and session.test_results:
                for test in session.test_results:
                    total_runs[test.nodeid] += 1
                    if test.outcome == TestOutcome.FAILED:
                        failure_counts[test.nodeid] += 1

        # Calculate failure rates and sort
        failing_tests = []
        for nodeid, failures in failure_counts.items():
            runs = total_runs[nodeid]
            failure_rate = failures / runs if runs > 0 else 0

            if failures > 0:  # Only include tests that have failed at least once
                failing_tests.append(
                    {
                        "nodeid": nodeid,
                        "failures": failures,
                        "total_runs": runs,
                        "failure_rate": failure_rate,
                    }
                )

        # Sort by number of failures (descending)
        top_failing = sorted(
            failing_tests,
            key=lambda x: (x["failures"], x["failure_rate"]),
            reverse=True,
        )[:limit]

        # Calculate failure distribution
        total_failures = sum(test["failures"] for test in failing_tests)
        failure_distribution = {}

        if total_failures > 0:
            for test in top_failing:
                failure_distribution[test["nodeid"]] = test["failures"] / total_failures

        return {
            "top_failing": top_failing,
            "failure_distribution": failure_distribution,
            "total_failures": total_failures,
        }

    def regression_rate(self, days: Optional[int] = None) -> Dict[str, Any]:
        """Calculate the regression rate of tests.

        Regression rate is the percentage of tests that were passing in previous sessions
        but failed in the most recent session. This metric helps identify newly introduced
        instability.

        Args:
            days: Optional number of days to look back

        Returns:
            Dict containing:
            - regression_rate: Percentage of tests that regressed
            - regressed_tests: List of tests that regressed
            - total_regressions: Number of tests that regressed
        """
        sessions = self._get_sessions(days)

        if len(sessions) < 2:
            return {
                "regression_rate": 0.0,
                "regressed_tests": [],
                "total_regressions": 0,
            }

        # Sort sessions by timestamp
        sorted_sessions = sorted(
            sessions,
            key=lambda s: (s.session_start_time if hasattr(s, "session_start_time") else datetime.min),
        )

        # Get the most recent session
        latest_session = sorted_sessions[-1]

        # Track test outcomes across sessions
        test_history = defaultdict(list)

        # Process all sessions except the latest
        for session in sorted_sessions[:-1]:
            if hasattr(session, "test_results") and session.test_results:
                for test in session.test_results:
                    nodeid = test.nodeid
                    test_history[nodeid].append(test.outcome)

        # Identify tests that regressed in the latest session
        regressed_tests = []

        if hasattr(latest_session, "test_results") and latest_session.test_results:
            for test in latest_session.test_results:
                nodeid = test.nodeid

                # Check if test failed in the latest session
                if test.outcome == TestOutcome.FAILED:
                    # Check if test was previously passing
                    if nodeid in test_history and TestOutcome.PASSED in test_history[nodeid]:
                        regressed_tests.append(
                            {
                                "nodeid": nodeid,
                                "previous_outcomes": test_history[nodeid],
                                "latest_outcome": test.outcome,
                            }
                        )

        # Calculate regression rate
        total_tests = len(set(nodeid for session in sessions for test in session.test_results))
        regression_rate = len(regressed_tests) / total_tests if total_tests > 0 else 0.0

        return {
            "regression_rate": regression_rate,
            "regressed_tests": regressed_tests,
            "total_regressions": len(regressed_tests),
        }

    def longest_running_tests(self, days: Optional[int] = None, limit: int = 10) -> Dict[str, Any]:
        """Identify the longest running tests across sessions.

        This metric helps guide optimization efforts by identifying tests that
        consume the most execution time.

        Args:
            days: Optional number of days to look back
            limit: Maximum number of tests to return

        Returns:
            Dict containing:
            - longest_tests: List of dicts with test nodeids and their duration metrics
            - total_duration: Total test execution time
            - avg_duration: Average test duration
        """
        sessions = self._get_sessions(days)

        # Track durations by test
        test_durations = defaultdict(list)

        # Collect duration data from all sessions
        for session in sessions:
            if hasattr(session, "test_results") and session.test_results:
                for test in session.test_results:
                    if hasattr(test, "duration") and test.duration is not None:
                        nodeid = test.nodeid
                        test_durations[nodeid].append(test.duration)

        # Calculate average durations and sort
        avg_durations = [(nodeid, sum(durations) / len(durations)) for nodeid, durations in test_durations.items()]

        # Sort by duration (descending) and return top N
        longest_tests = sorted(avg_durations, key=lambda x: x[1], reverse=True)[:limit]

        # Calculate overall metrics
        all_durations = [d for durations in test_durations.values() for d in durations]
        total_duration = sum(all_durations)
        avg_duration = total_duration / len(all_durations) if all_durations else 0

        return {
            "longest_tests": longest_tests,
            "total_duration": total_duration,
            "avg_duration": avg_duration,
        }

    def test_suite_duration_trend(self, days: Optional[int] = None, window_size: int = 7) -> Dict[str, Any]:
        """Analyze the trend in test suite duration over time.

        This metric helps detect slow creep in runtime cost by tracking how the
        total execution time changes over time.

        Args:
            days: Optional number of days to look back
            window_size: Size of the window for trend analysis

        Returns:
            Dict containing:
            - trend: Dict with trend metrics
            - durations: List of session durations over time
            - significant: Boolean indicating if the trend is statistically significant
        """
        sessions = self._get_sessions(days)

        if len(sessions) < 2:
            return {
                "trend": {"change": 0, "direction": "stable"},
                "durations": [],
                "significant": False,
            }

        # Sort sessions by timestamp
        sorted_sessions = sorted(
            sessions,
            key=lambda s: (s.session_start_time if hasattr(s, "session_start_time") else datetime.min),
        )

        # Calculate session durations
        session_durations = []
        for session in sorted_sessions:
            if (
                hasattr(session, "session_start_time")
                and hasattr(session, "session_stop_time")
                and session.session_start_time
                and session.session_stop_time
            ):
                duration = (session.session_stop_time - session.session_start_time).total_seconds()
                timestamp = session.session_start_time

                session_durations.append(
                    {
                        "session_id": session.session_id,
                        "timestamp": timestamp,
                        "duration": duration,
                    }
                )

        if not session_durations:
            return {
                "trend": {"change": 0, "direction": "stable"},
                "durations": [],
                "significant": False,
            }

        # Analyze trend
        if len(session_durations) >= window_size:
            # Compare recent window to previous window
            recent_window = session_durations[-window_size:]
            previous_window = session_durations[-2 * window_size : -window_size]

            if previous_window:  # Ensure we have enough data for comparison
                recent_avg = sum(d["duration"] for d in recent_window) / len(recent_window)
                previous_avg = sum(d["duration"] for d in previous_window) / len(previous_window)

                # Calculate percent change
                if previous_avg > 0:
                    percent_change = ((recent_avg - previous_avg) / previous_avg) * 100
                else:
                    percent_change = 0

                # Determine if change is significant (> 10%)
                significant = abs(percent_change) > 10

                trend = {
                    "change": percent_change,
                    "direction": (
                        "increasing" if percent_change > 0 else "decreasing" if percent_change < 0 else "stable"
                    ),
                }
            else:
                trend = {"change": 0, "direction": "stable"}
                significant = False
        else:
            trend = {"change": 0, "direction": "stable"}
            significant = False

        return {
            "trend": trend,
            "durations": session_durations,
            "significant": significant,
        }


class TestAnalysis(AnalysisBase):
    """Test-level analytics.

    Analyzes patterns and metrics at individual test level:
    - Test stability
    - Performance patterns
    - Warning analysis
    """

    def __init__(
        self,
        storage: Optional[BaseStorage] = None,
        sessions: Optional[List[TestSession]] = None,
        profile_name: Optional[str] = None,
    ):
        """Initialize with storage and optional session list.

        Args:
            storage: Storage instance for accessing test data. If None, uses profile_name.
            sessions: Optional list of sessions to analyze. If not provided,
                     will analyze all sessions from storage.
            profile_name: Optional profile name to use for storage configuration.
                         Takes precedence over storage parameter if both are provided.
        """
        super().__init__()
        self._profile_name = profile_name

        if storage is None and profile_name is not None:
            storage = get_storage_instance(profile_name=profile_name)
        elif storage is not None and profile_name is None:
            # Try to get profile name from storage if available
            profile_name = getattr(storage, "profile_name", None)

        self.storage = storage
        self._sessions = sessions
        # Use profile-only approach for Query initialization
        self._query = Query(profile_name=profile_name)

    def stability(self, chunk_size: int = 1000) -> Dict[str, Any]:
        """Analyze test stability.

        Args:
            chunk_size: Number of tests to process at once for large datasets

        Returns:
            Dict of stability metrics including:
            - unreliable_tests: List of tests with inconsistent outcomes
            - unstable_tests: List of consistently failing tests
        """
        if self._sessions is None:
            return {"unreliable_tests": [], "unstable_tests": []}

        sessions = self._sessions
        if not sessions:
            return {"unreliable_tests": [], "unstable_tests": []}

        # Track test outcomes across sessions
        test_history = defaultdict(list)

        # Process sessions in chunks for large datasets
        session_chunks = [sessions[i : i + chunk_size] for i in range(0, len(sessions), chunk_size)]

        session_count = 0
        for chunk in session_chunks:
            for session in chunk:
                session_timestamp = session.session_start_time

                # Process each test result
                for test_result in session.test_results:
                    test_history[test_result.nodeid].append((session_timestamp, test_result.outcome))

                session_count += 1

        # Analyze unreliable tests
        unreliable_tests = []
        for nodeid, outcomes in test_history.items():
            # A test is unreliable if it has different outcomes
            unique_outcomes = set(outcome for _, outcome in outcomes)
            if len(unique_outcomes) > 1:
                # Calculate reliability rate
                outcome_counts = defaultdict(int)
                for _, outcome in outcomes:
                    outcome_counts[outcome] += 1

                total_runs = len(outcomes)
                most_common_outcome = max(outcome_counts.items(), key=lambda x: x[1])[0]
                most_common_count = outcome_counts[most_common_outcome]

                reliability_rate = most_common_count / total_runs

                unreliable_tests.append(
                    {
                        "nodeid": nodeid,
                        "outcomes": [{"outcome": str(o), "count": c} for o, c in outcome_counts.items()],
                        "reliability_rate": reliability_rate,
                        "total_runs": total_runs,
                    }
                )

        # Sort by reliability rate (ascending)
        unreliable_tests.sort(key=lambda x: x["reliability_rate"], reverse=False)

        # Find consistently failing tests (separate from unreliable tests)
        unstable_tests = []
        for nodeid, outcomes in test_history.items():
            # Skip tests that are already identified as unreliable
            if any(test["nodeid"] == nodeid for test in unreliable_tests):
                continue

            # A test is unstable if it consistently fails
            if all(outcome == TestOutcome.FAILED for _, outcome in outcomes) and len(outcomes) >= 2:
                unstable_tests.append(
                    {
                        "nodeid": nodeid,
                        "failure_count": len(outcomes),
                        "first_failure": min(timestamp for timestamp, _ in outcomes),
                        "last_failure": max(timestamp for timestamp, _ in outcomes),
                    }
                )

        # Sort by failure count (descending)
        unstable_tests.sort(key=lambda x: x["failure_count"], reverse=True)

        return {
            "unreliable_tests": unreliable_tests,
            "unstable_tests": unstable_tests,
        }

    def performance(self) -> Dict[str, Any]:
        """Analyze test performance patterns.

        Returns:
            Dict of performance metrics including:
            - slow_tests: List of slow tests
            - duration_changes: Tests with significant duration changes
            - bottlenecks: Identified performance bottlenecks
        """
        # TODO: Implement performance analysis
        pass

    def warnings(self) -> Dict[str, Any]:
        """Analyze test warning patterns.

        Returns:
            Dict of warning metrics including:
            - warning_types: Frequency of different warning types
            - warning_patterns: Common warning patterns
            - warning_trends: Changes in warning patterns
        """
        # TODO: Implement warning analysis
        pass

    def outcome_distribution(self, days: Optional[int] = None) -> Dict[str, int]:
        """
        Calculate the distribution of test outcomes across sessions.

        Args:
            days: Optional number of days to limit the analysis to

        Returns:
            Dictionary mapping outcome names to counts
        """
        # Filter sessions by days if specified
        sessions = self._filter_sessions_by_days(days) if days else self._sessions

        if not sessions:
            return {}

        # Initialize outcome counter
        outcome_counts = {}

        # Process each session
        for session in sessions:
            # Count outcomes in this session
            for test_result in session.test_results:
                outcome_str = test_result.outcome.to_str()
                outcome_counts[outcome_str] = outcome_counts.get(outcome_str, 0) + 1

        return outcome_counts

    def co_failures(self, min_correlation: float = 0.7, min_occurrences: int = 3) -> List[Dict[str, Any]]:
        """
        Identify clusters of tests that tend to fail together.

        Args:
            min_correlation: Minimum correlation coefficient to consider tests related
            min_occurrences: Minimum number of co-occurrences to consider

        Returns:
            List of co-failure clusters with correlation scores
        """
        if not self._sessions:
            return []

        # Extract all test failures from sessions
        test_failures = {}
        session_failures = {}

        # Process each session
        for session in self._sessions:
            # Record failures in this session
            session_id = session.session_id
            session_failures[session_id] = []

            for test_result in session.test_results:
                if test_result.outcome.is_failed():
                    test_id = test_result.nodeid

                    # Initialize test entry if not exists
                    if test_id not in test_failures:
                        test_failures[test_id] = set()

                    # Record that this test failed in this session
                    test_failures[test_id].add(session_id)
                    session_failures[session_id].append(test_id)

        # Find correlations between tests
        correlations = {}
        test_ids = list(test_failures.keys())

        # Skip if not enough tests
        if len(test_ids) < 2:
            return []

        # Compare each pair of tests
        for i in range(len(test_ids)):
            for j in range(i + 1, len(test_ids)):
                test_a = test_ids[i]
                test_b = test_ids[j]

                # Get sessions where each test failed
                sessions_a = test_failures[test_a]
                sessions_b = test_failures[test_b]

                # Calculate co-occurrence
                co_failures = sessions_a.intersection(sessions_b)

                # Skip if not enough co-occurrences
                if len(co_failures) < min_occurrences:
                    continue

                # Calculate correlation coefficient (Jaccard similarity)
                correlation = len(co_failures) / len(sessions_a.union(sessions_b))

                # Record if above threshold
                if correlation >= min_correlation:
                    pair_key = (test_a, test_b)
                    correlations[pair_key] = {
                        "correlation": correlation,
                        "co_failures": len(co_failures),
                        "tests": [test_a, test_b],
                    }

        # Build clusters from correlations
        clusters = []
        processed_pairs = set()

        # Sort correlations by strength
        sorted_correlations = sorted(correlations.items(), key=lambda x: x[1]["correlation"], reverse=True)

        # Process each correlation
        for (test_a, test_b), data in sorted_correlations:
            # Skip if already in a cluster
            if (test_a, test_b) in processed_pairs:
                continue

            # Start new cluster
            cluster = {
                "correlation": data["correlation"],
                "co_failures": data["co_failures"],
                "tests": [test_a, test_b],
            }
            processed_pairs.add((test_a, test_b))

            # Try to expand cluster
            for (other_a, other_b), other_data in sorted_correlations:
                # Skip if already processed
                if (other_a, other_b) in processed_pairs:
                    continue

                # Check if connected to cluster
                if other_a in cluster["tests"] or other_b in cluster["tests"]:
                    # Add the test not in the cluster
                    new_test = other_b if other_a in cluster["tests"] else other_a
                    if new_test not in cluster["tests"]:
                        cluster["tests"].append(new_test)

                    # Mark as processed
                    processed_pairs.add((other_a, other_b))

                    # Update correlation (use average)
                    cluster["correlation"] = (cluster["correlation"] + other_data["correlation"]) / 2

            # Add cluster to results
            clusters.append(cluster)

        return clusters

    def health_score(self) -> Dict[str, Any]:
        """
        Calculate a health score for the test suite based on various metrics.

        Returns:
            Dictionary with overall health score and component scores
        """
        if not self._sessions:
            return {}

        # Initialize scores
        stability_score = 0.0
        performance_score = 0.0

        # Get stability metrics
        stability_data = self.stability()
        unreliable_tests = stability_data.get("unreliable_tests", [])
        unstable_tests = stability_data.get("unstable_tests", [])

        # Calculate stability score (100 - percentage of unreliable/unstable tests)
        test_results = self._get_all_test_results()
        unique_tests = set(test.nodeid for test in test_results)
        total_unique_tests = len(unique_tests)

        if total_unique_tests > 0:
            unreliable_count = len(unreliable_tests)
            unstable_count = len(unstable_tests)
            problem_tests_pct = (unreliable_count + unstable_count) / total_unique_tests * 100
            stability_score = max(0, 100 - problem_tests_pct)

        # Get session analysis for trends
        session_analysis = SessionAnalysis(self._sessions)

        # Calculate performance score based on duration trends
        trends = session_analysis.detect_trends()
        duration_trend = trends.get("duration", {})

        # Base performance score on trend direction and significance
        performance_score = 70  # Default score

        if duration_trend:
            direction = duration_trend.get("direction", "stable")
            significant = duration_trend.get("significant", False)
            change_percent = duration_trend.get("change_percent", 0)

            if direction == "improving":
                # Tests getting faster
                performance_score += 20 if significant else 10
            elif direction == "degrading":
                # Tests getting slower
                performance_score -= 20 if significant else 10

            # Adjust based on magnitude of change
            if abs(change_percent) > 20:
                performance_score += 10 if direction == "improving" else -10

        # Ensure scores are within 0-100 range
        stability_score = max(0, min(100, stability_score))
        performance_score = max(0, min(100, performance_score))

        # Calculate overall score (weighted average)
        overall_score = 0.7 * stability_score + 0.3 * performance_score

        # Calculate category scores
        categories = {}

        # Group tests by category (using directory structure)
        test_by_category = {}
        for test in test_results:
            # Extract category from nodeid (first directory)
            parts = test.nodeid.split("/")
            category = parts[0] if len(parts) > 1 else "unknown"

            if category not in test_by_category:
                test_by_category[category] = []

            test_by_category[category].append(test)

        # Calculate score for each category
        for category, tests in test_by_category.items():
            # Skip categories with too few tests
            if len(tests) < 5:
                continue

            # Calculate failure rate
            failures = sum(1 for test in tests if test.outcome.is_failed())
            failure_rate = failures / len(tests) if tests else 0

            # Calculate category score
            category_score = 100 - (failure_rate * 100)
            categories[category] = category_score

        return {
            "overall_score": overall_score,
            "stability_score": stability_score,
            "performance_score": performance_score,
            "categories": categories,
        }

    def behavior_changes(self, days: Optional[int] = 30, threshold: int = 3) -> Dict[str, List[Dict[str, Any]]]:
        """
        Detect tests that have recently changed behavior (failing or passing).

        Args:
            days: Number of days to look back
            threshold: Minimum number of consecutive failures/passes to consider

        Returns:
            Dictionary with lists of recently failing and recently passing tests
        """
        # Filter sessions by days if specified
        sessions = self._filter_sessions_by_days(days) if days else self._sessions

        if not sessions:
            return {"recently_failing": [], "recently_passing": []}

        # Sort sessions by timestamp
        sessions = sorted(sessions, key=lambda s: s.session_start_time)

        # Get test outcomes by test ID
        test_outcomes = defaultdict(list)
        for session in sessions:
            for test in session.test_results:
                test_outcomes[test.nodeid].append({"outcome": test.outcome, "timestamp": session.session_start_time})

        # Identify tests with behavior changes
        recently_failing = []
        recently_passing = []

        # Process each test to identify behavior changes
        for test_id, history in test_outcomes.items():
            # Skip if not enough history
            if len(history) < threshold * 2:
                continue

            # Split history into recent and older
            recent_outcomes = history[-threshold:]
            older_outcomes = history[:-threshold]

            # Check if recently failing
            was_passing = all(not o["outcome"].is_failed() for o in older_outcomes[-3:])
            now_failing = all(o["outcome"].is_failed() for o in recent_outcomes)

            if was_passing and now_failing:
                # Find last passed timestamp
                last_passed = None
                for o in reversed(history):
                    if not o["outcome"].is_failed():
                        last_passed = o["timestamp"]
                        break

                recently_failing.append(
                    {
                        "nodeid": test_id,
                        "last_passed": last_passed,
                        "failure_streak": sum(1 for o in recent_outcomes if o["outcome"].is_failed()),
                    }
                )

            # Check if recently passing
            was_failing = all(o["outcome"].is_failed() for o in older_outcomes[-3:])
            now_passing = all(not o["outcome"].is_failed() for o in recent_outcomes)

            if was_failing and now_passing:
                # Find last failed timestamp
                last_failed = None
                for o in reversed(history):
                    if o["outcome"].is_failed():
                        last_failed = o["timestamp"]
                        break

                recently_passing.append(
                    {
                        "nodeid": test_id,
                        "last_failed": last_failed,
                        "success_streak": sum(1 for o in recent_outcomes if not o["outcome"].is_failed()),
                    }
                )

        return {
            "recently_failing": recently_failing,
            "recently_passing": recently_passing,
        }


class MetricsAnalysis(AnalysisBase):
    """High-level metrics analysis.

    Provides aggregated metrics and health scores:
    - Overall health score
    - Failure pattern analysis
    - Test suite efficiency
    - Test coverage trends
    """

    def __init__(
        self,
        storage: Optional[BaseStorage] = None,
        sessions: Optional[List[TestSession]] = None,
        profile_name: Optional[str] = None,
    ):
        """Initialize with storage and optional session list.

        Args:
            storage: Storage instance for accessing test data. If None, uses profile_name.
            sessions: Optional list of sessions to analyze. If not provided,
                     will analyze all sessions from storage.
            profile_name: Optional profile name to use for storage configuration.
                         Takes precedence over storage parameter if both are provided.
        """
        super().__init__()
        self._profile_name = profile_name

        if storage is not None:
            self.storage = storage
        elif profile_name is not None:
            self.storage = get_storage_instance(profile_name=profile_name)
        else:
            self.storage = get_storage_instance()

        if sessions is not None:
            self._sessions = sessions
        else:
            self._sessions = self.storage.load_sessions()

    def _get_sessions(self, days: Optional[int] = None) -> List[TestSession]:
        """Get sessions to analyze, optionally filtered by date range."""
        if self._sessions is not None:
            sessions = self._sessions
            if days:
                cutoff = datetime.now(ZoneInfo("UTC")) - timedelta(days=days)
                sessions = [s for s in sessions if s.session_start_time >= cutoff]
            return sessions

        query = self._query
        if days:
            query = query.in_last_days(days)
        return query.execute().sessions

    def health_score(self, days: Optional[int] = None) -> Dict[str, Any]:
        """Calculate overall test suite health score.

        Analyzes multiple factors while preserving session context:
        - Failure rates and patterns
        - Test stability and reliability
        - Performance and resource usage
        - Warning patterns

        Args:
            days: Optional number of days to look back

        Returns:
            Dict containing:
            - overall_score: 0-100 score indicating test suite health
            - component_scores: Individual scores for each component
            - recommendations: List of improvement recommendations
        """
        sessions = self._get_sessions(days)
        if not sessions:
            return {"overall_score": 0.0, "component_scores": {}, "recommendations": []}

        # Calculate component scores while preserving session context
        stability_score = self._calculate_stability_score(sessions)
        performance_score = self._calculate_performance_score(sessions)
        warning_score = self._calculate_warning_score(sessions)

        # Calculate additional health metrics
        total_tests = 0
        failed_tests = 0
        total_warnings = 0
        for session in sessions:
            for test in session.test_results:
                total_tests += 1
                if (
                    getattr(test, "outcome", None) == getattr(test, "outcome", None).__class__.FAILED
                    if hasattr(test, "outcome") and hasattr(test.outcome, "__class__")
                    else False
                ):
                    failed_tests += 1

                if getattr(test, "has_warning", False):
                    total_warnings += 1
        failure_rate = (failed_tests / total_tests * 100) if total_tests else 0.0
        warning_rate = (total_warnings / total_tests * 100) if total_tests else 0.0

        # Calculate overall score (weighted average)
        weights = {
            "stability": 0.5,  # Most important
            "performance": 0.3,
            "warnings": 0.2,
        }

        overall_score = (
            stability_score * weights["stability"]
            + performance_score * weights["performance"]
            + warning_score * weights["warnings"]
        )

        # Generate recommendations based on scores
        recommendations = self._generate_recommendations(stability_score, performance_score, warning_score, sessions)

        return {
            "overall_score": overall_score,
            "component_scores": {
                "stability": stability_score,
                "performance": performance_score,
                "warnings": warning_score,
                "failure_rate": failure_rate,
                "warning_rate": warning_rate,
            },
            "recommendations": recommendations,
        }

    def _calculate_stability_score(self, sessions: List[TestSession]) -> float:
        """Calculate stability score based on failures and reliability."""
        if not sessions:
            return 0.0

        total_tests = 0
        failed_tests = 0
        unreliable_tests = 0

        # Analyze each session while preserving context
        for session in sessions:
            session_outcomes = defaultdict(list)

            for test in session.test_results:
                total_tests += 1
                if test.outcome == TestOutcome.FAILED:
                    failed_tests += 1

                # Track outcomes within session for reliability
                session_outcomes[test.nodeid].append(test.outcome)
                if len(session_outcomes[test.nodeid]) > 1:
                    prev = session_outcomes[test.nodeid][-2]
                    curr = session_outcomes[test.nodeid][-1]
                    if prev != curr:
                        unreliable_tests += 1

        if total_tests == 0:
            return 0.0

        # Calculate score components
        failure_ratio = failed_tests / total_tests
        unreliable_ratio = unreliable_tests / total_tests

        # Convert to 0-100 score with penalties
        base_score = 100 * (1 - failure_ratio)
        unreliable_penalty = 20 * unreliable_ratio  # Up to 20 point penalty for unreliability

        return max(0, min(100, base_score - unreliable_penalty))

    def _calculate_performance_score(self, sessions: List[TestSession]) -> float:
        """Calculate performance score based on duration and resource usage."""
        if not sessions:
            return 0.0

        durations = []

        # Analyze each session while preserving context
        for session in sessions:
            session_durations = []
            for test in session.test_results:
                session_durations.append(test.duration)
                durations.append(test.duration)

            # Look for performance degradation within session
            if session_durations:
                session_mean = mean(session_durations)
                session_stddev = stdev(session_durations) if len(session_durations) > 1 else 0

                # Count tests significantly slower than session average
                sum(1 for d in session_durations if d > session_mean + 2 * session_stddev)

        if not durations:
            return 0.0

        # Calculate overall statistics
        avg_duration = mean(durations)
        duration_stddev = stdev(durations) if len(durations) > 1 else 0

        # Score based on consistency and outliers
        consistency_score = 100 * (1 - (duration_stddev / avg_duration if avg_duration > 0 else 0))

        return max(0, min(100, consistency_score))

    def _calculate_warning_score(self, sessions: List[TestSession]) -> float:
        """Calculate warning score based on warning patterns."""
        if not sessions:
            return 0.0

        total_tests = 0
        total_warnings = 0
        repeated_warnings = 0

        # Track warnings while preserving session context
        warning_history = defaultdict(int)

        for session in sessions:
            session_warnings = set()

            for test in session.test_results:
                total_tests += 1
                if test.has_warning:
                    total_warnings += 1
                    session_warnings.add(test.nodeid)

                    # Track repeated warnings
                    warning_history[test.nodeid] += 1
                    if warning_history[test.nodeid] > 1:
                        repeated_warnings += 1

        if total_tests == 0:
            return 0.0

        # Calculate score with penalties for warning frequency and repetition
        warning_ratio = total_warnings / total_tests
        repeat_ratio = repeated_warnings / total_tests if total_tests > 0 else 0

        base_score = 100 * (1 - warning_ratio)
        repeat_penalty = 30 * repeat_ratio  # Up to 30 point penalty for repeated warnings

        return max(0, min(100, base_score - repeat_penalty))

    def _generate_recommendations(
        self,
        stability_score: float,
        performance_score: float,
        warning_score: float,
        sessions: List[TestSession],
    ) -> List[Dict[str, str]]:
        """Generate improvement recommendations based on scores."""
        recommendations = []

        # Analyze stability issues
        if stability_score < 80:
            failed_patterns = self._analyze_failure_patterns(sessions)
            if failed_patterns:
                recommendations.append(
                    {
                        "category": "stability",
                        "priority": "high",
                        "message": "High failure rate detected in tests: " + ", ".join(failed_patterns[:3]),
                    }
                )

        # Analyze performance issues
        if performance_score < 80:
            slow_tests = self._find_slow_tests(sessions)
            if slow_tests:
                recommendations.append(
                    {
                        "category": "performance",
                        "priority": "medium",
                        "message": "Performance bottlenecks identified in: " + ", ".join(slow_tests[:3]),
                    }
                )

        # Analyze warning issues
        if warning_score < 80:
            warning_patterns = self._analyze_warning_patterns(sessions)
            if warning_patterns:
                recommendations.append(
                    {
                        "category": "warnings",
                        "priority": "low",
                        "message": "Recurring warnings found in: " + ", ".join(warning_patterns[:3]),
                    }
                )

        return recommendations

    def _analyze_failure_patterns(self, sessions: List[TestSession]) -> List[str]:
        """Analyze common failure patterns while preserving session context."""
        failure_counts = defaultdict(int)

        for session in sessions:
            # Track failures within session context
            session_failures = set()

            for test in session.test_results:
                if test.outcome == TestOutcome.FAILED:
                    session_failures.add(test.nodeid)
                    failure_counts[test.nodeid] += 1

        # Return tests with highest failure counts
        return [test for test, count in sorted(failure_counts.items(), key=lambda x: x[1], reverse=True)]

    def _find_slow_tests(self, sessions: List[TestSession]) -> List[str]:
        """Identify consistently slow tests while preserving session context."""
        test_durations = defaultdict(list)

        for session in sessions:
            # Track durations within session context
            session_durations = {}

            for test in session.test_results:
                test_durations[test.nodeid].append(test.duration)
                session_durations[test.nodeid] = test.duration

        # Calculate average durations and find slow tests
        slow_tests = []
        for test_id, durations in test_durations.items():
            avg_duration = mean(durations)
            if len(durations) > 1:
                stdev(durations)
                if avg_duration > mean(d for dur in test_durations.values() for d in dur):
                    slow_tests.append((test_id, avg_duration))

        return [test for test, _ in sorted(slow_tests, key=lambda x: x[1], reverse=True)]

    def _analyze_warning_patterns(self, sessions: List[TestSession]) -> List[str]:
        """Analyze warning patterns while preserving session context."""
        warning_counts = defaultdict(int)

        for session in sessions:
            # Track warnings within session context
            session_warnings = set()

            for test in session.test_results:
                if test.has_warning:
                    session_warnings.add(test.nodeid)
                    warning_counts[test.nodeid] += 1

        # Return tests with highest warning counts
        return [test for test, count in sorted(warning_counts.items(), key=lambda x: x[1], reverse=True)]


class Analysis:
    """Top-level entry point for analysis.

    Provides access to all analysis components:
    - SessionAnalysis: Session-level analytics
    - TestAnalysis: Test-level analytics
    - MetricsAnalysis: High-level metrics

    This class follows the fluent interface pattern used by Query and Comparison,
    allowing for intuitive method chaining while preserving session context.

    Storage profiles can be specified to analyze data from different environments
    or configurations.

    Example usage:
        # Basic analysis with Query
        analysis = Analysis()
        health_report = analysis.with_query(lambda q: q.in_last_days(30)).health_report()

        # Specific metrics
        stability_report = analysis.with_query(lambda q: q.for_sut("service")).stability_report()

        # Complex query
        analysis_result = analysis.with_query(
            lambda q: q.filter_by_test()
                      .with_outcome(TestOutcome.FAILED)
                      .apply()
        ).performance_report()

        # Combining with Comparison
        comparison = Comparison().between_suts("service-v1", "service-v2").execute()
        analysis_result = Analysis(sessions=[comparison.base_session, comparison.target_session]).compare_health()

        # Using storage profiles
        analysis = Analysis(profile_name="production")
        prod_report = analysis.health_report()

        # Switch profiles during analysis
        analysis = Analysis()
        dev_report = analysis.with_profile("development").health_report()
    """

    def __init__(
        self,
        sessions: Optional[list] = None,
        profile_name: Optional[str] = None,
        storage: Optional[BaseStorage] = None,
        **kwargs,
    ):
        """Initialize analysis components.

        Args:
            sessions: Optional list of sessions to use
            profile_name: Optional profile name to use
            storage: Optional storage instance to use
            **kwargs: Additional keyword arguments for Analysis
        """
        self._profile_name = profile_name

        if storage is not None:
            self.storage = storage
        elif profile_name is not None:
            self.storage = get_storage_instance(profile_name=profile_name)
        else:
            self.storage = get_storage_instance()

        if sessions is not None:
            self._sessions = sessions
        else:
            self._sessions = self.storage.load_sessions()

        # Initialize analysis components
        self.sessions = SessionAnalysis(self.storage, self._sessions, self._profile_name)
        self.tests = TestAnalysis(self.storage, self._sessions, self._profile_name)
        self.metrics = MetricsAnalysis(self.storage, self._sessions, self._profile_name)

    def with_profile(self, profile_name: str) -> "Analysis":
        """Set the storage profile for analysis.

        Args:
            profile_name: Name of the profile to use

        Returns:
            Analysis instance for chaining

        Example:
            analysis.with_profile("production").health_report()
        """
        self._profile_name = profile_name
        self.storage = get_storage_instance(profile_name=profile_name)

        # Update analysis components with new storage
        self.sessions = SessionAnalysis(self.storage, self._sessions, profile_name)
        self.tests = TestAnalysis(self.storage, self._sessions, profile_name)
        self.metrics = MetricsAnalysis(self.storage, self._sessions, profile_name)

        return self

    def with_query(self, query_func: Callable[[Query], Query]) -> "Analysis":
        """Apply a query function to filter sessions.

        This method allows using the full power of the Query class
        without duplicating its functionality in Analysis.

        Args:
            query_func: A function that takes a Query instance and returns a modified Query

        Returns:
            Analysis instance with filtered sessions

        Example:
            analysis.with_query(lambda q: q.in_last_days(7).for_sut("service"))
        """
        query = Query(profile_name=self._profile_name)
        filtered_query = query_func(query)
        filtered_sessions = filtered_query.execute(sessions=self._sessions).sessions
        return Analysis(
            storage=self.storage,
            sessions=filtered_sessions,
            profile_name=self._profile_name,
        )

    @property
    def session_analysis(self):
        """Backward-compatible alias for self.sessions."""
        return self.sessions

    def health_report(self, days: Optional[int] = None) -> Dict[str, Any]:
        """Generate a comprehensive health report for the test suite.

        Combines metrics from all analysis components to provide a complete
        picture of test suite health.

        Args:
            days: Optional number of days to analyze. If None, uses all sessions.

        Returns:
            Dict containing health metrics, scores, and recommendations
        """
        health_score = self.metrics.health_score(days)
        session_metrics = self.sessions.test_metrics(days)
        trends = self.sessions.detect_trends(days)

        # Get reliability metrics
        insights = TestInsights(self._sessions)
        reliability_metrics = insights.test_reliability_metrics()

        return {
            "health_score": health_score,
            "session_metrics": session_metrics,
            "trends": trends,
            "reliability_metrics": reliability_metrics,
            "timestamp": datetime.now(ZoneInfo("UTC")),
        }

    def stability_report(self) -> Dict[str, Any]:
        """Generate a report focused on test stability.

        Analyzes reliability, consistent failures, and outcome patterns
        while preserving session context.

        Returns:
            Dict containing stability metrics and recommendations
        """
        stability = self.tests.stability()
        failure_rate = self.sessions.failure_rate()

        return {
            "stability": stability,
            "failure_rate": failure_rate,
            "timestamp": datetime.now(ZoneInfo("UTC")),
        }

    def performance_report(self) -> Dict[str, Any]:
        """Generate a report focused on test performance.

        Analyzes execution times, performance trends, and bottlenecks
        while preserving session context.

        Returns:
            Dict containing performance metrics and recommendations
        """
        performance = self.tests.performance()
        session_metrics = self.sessions.test_metrics()

        return {
            "performance": performance,
            "session_metrics": session_metrics,
            "timestamp": datetime.now(ZoneInfo("UTC")),
        }

    def compare_health(
        self,
        base_sessions: Optional[List[TestSession]] = None,
        target_sessions: Optional[List[TestSession]] = None,
    ) -> Dict[str, Any]:
        """Compare health metrics between two sets of sessions.

        This is particularly useful for comparing before/after changes
        or different environments.

        Args:
            base_sessions: Optional base sessions to compare. If None, uses first half of current sessions.
            target_sessions: Optional target sessions to compare. If None, uses second half of current sessions.

        Returns:
            Dict containing comparative health metrics
        """
        if not self._sessions:
            raise ValueError("No sessions available for comparison")

        if base_sessions is None and target_sessions is None:
            # Split current sessions in half chronologically
            sorted_sessions = sorted(self._sessions, key=lambda s: s.session_start_time)
            midpoint = len(sorted_sessions) // 2
            base_sessions = sorted_sessions[:midpoint]
            target_sessions = sorted_sessions[midpoint:]

        base_analysis = Analysis(
            storage=self.storage,
            sessions=base_sessions,
            profile_name=self._profile_name,
        )
        target_analysis = Analysis(
            storage=self.storage,
            sessions=target_sessions,
            profile_name=self._profile_name,
        )

        base_health = base_analysis.health_report()
        target_health = target_analysis.health_report()

        # Calculate differences
        health_diff = target_health["health_score"]["overall_score"] - base_health["health_score"]["overall_score"]

        return {
            "base_health": base_health,
            "target_health": target_health,
            "health_difference": health_diff,
            "improved": health_diff > 0,
            "timestamp": datetime.now(ZoneInfo("UTC")),
        }

    def count_total_tests(self) -> int:
        """Count the total number of tests across all sessions.

        Returns:
            Total number of tests
        """
        if not self._sessions:
            return 0

        return sum(len(session.test_results) for session in self._sessions)

    def calculate_pass_rate(self) -> float:
        """Calculate the overall pass rate across all sessions.

        Returns:
            Pass rate as a float between 0.0 and 1.0
        """
        if not self._sessions:
            return 0.0

        total_tests = 0
        passed_tests = 0

        for session in self._sessions:
            for test in session.test_results:
                total_tests += 1
                if test.outcome == TestOutcome.PASSED:
                    passed_tests += 1

        return passed_tests / total_tests if total_tests > 0 else 0.0

    def calculate_average_duration(self) -> float:
        """Calculate the average test duration across all sessions.

        Returns:
            Average duration in seconds
        """
        if not self._sessions:
            return 0.0

        total_duration = 0.0
        total_tests = 0

        for session in self._sessions:
            for test in session.test_results:
                total_duration += test.duration
                total_tests += 1

        return total_duration / total_tests if total_tests > 0 else 0.0

    def identify_unreliable_tests(self) -> List[str]:
        """Identify tests that have inconsistent outcomes across sessions.

        Returns:
            List of test nodeids that are considered unreliable
        """
        if not self._sessions:
            return []

        # Extract all test failures from sessions
        test_failures = {}
        session_failures = {}

        # Process each session
        for session in self._sessions:
            # Record failures in this session
            session_id = session.session_id
            session_failures[session_id] = []

            for test_result in session.test_results:
                if test_result.outcome.is_failed():
                    test_id = test_result.nodeid

                    # Initialize test entry if not exists
                    if test_id not in test_failures:
                        test_failures[test_id] = set()

                    # Record that this test failed in this session
                    test_failures[test_id].add(session_id)
                    session_failures[session_id].append(test_id)

        # Find correlations between tests
        correlations = {}
        test_ids = list(test_failures.keys())

        # Skip if not enough tests
        if len(test_ids) < 2:
            return []

        # Compare each pair of tests
        for i in range(len(test_ids)):
            for j in range(i + 1, len(test_ids)):
                test_a = test_ids[i]
                test_b = test_ids[j]

                # Get sessions where each test failed
                sessions_a = test_failures[test_a]
                sessions_b = test_failures[test_b]

                # Calculate co-occurrence
                co_failures = sessions_a.intersection(sessions_b)

                # Skip if not enough co-occurrences
                if len(co_failures) < 3:
                    continue

                # Calculate correlation coefficient (Jaccard similarity)
                correlation = len(co_failures) / len(sessions_a.union(sessions_b))

                # Record if above threshold
                if correlation >= 0.7:
                    pair_key = (test_a, test_b)
                    correlations[pair_key] = {
                        "correlation": correlation,
                        "co_failures": len(co_failures),
                        "tests": [test_a, test_b],
                    }

        # Build clusters from correlations
        clusters = []
        processed_pairs = set()

        # Sort correlations by strength
        sorted_correlations = sorted(correlations.items(), key=lambda x: x[1]["correlation"], reverse=True)

        # Process each correlation
        for (test_a, test_b), data in sorted_correlations:
            # Skip if already in a cluster
            if (test_a, test_b) in processed_pairs:
                continue

            # Start new cluster
            cluster = {
                "correlation": data["correlation"],
                "co_failures": data["co_failures"],
                "tests": [test_a, test_b],
            }
            processed_pairs.add((test_a, test_b))

            # Try to expand cluster
            for (other_a, other_b), other_data in sorted_correlations:
                # Skip if already processed
                if (other_a, other_b) in processed_pairs:
                    continue

                # Check if connected to cluster
                if other_a in cluster["tests"] or other_b in cluster["tests"]:
                    # Add the test not in the cluster
                    new_test = other_b if other_a in cluster["tests"] else other_a
                    if new_test not in cluster["tests"]:
                        cluster["tests"].append(new_test)

                    # Mark as processed
                    processed_pairs.add((other_a, other_b))

                    # Update correlation (use average)
                    cluster["correlation"] = (cluster["correlation"] + other_data["correlation"]) / 2

            # Add cluster to results
            clusters.append(cluster)

        return clusters

    def identify_slowest_tests(self, limit: int = 5) -> List[tuple]:
        """Identify the slowest tests based on average duration.

        Args:
            limit: Maximum number of tests to return

        Returns:
            List of (test_nodeid, avg_duration) tuples, sorted by duration (descending)
        """
        if not self._sessions:
            return []

        # Track durations per test
        test_durations = defaultdict(list)

        for session in self._sessions:
            # Process regular test results
            for test in session.test_results:
                test_durations[test.nodeid].append(test.duration)

            # Process rerun groups if available
            if hasattr(session, "rerun_test_groups") and session.rerun_test_groups:
                for rerun_group in session.rerun_test_groups:
                    nodeid = rerun_group.nodeid

                    # For rerun groups, use the final outcome
                    if rerun_group.tests and len(rerun_group.tests) > 0:
                        final_test = rerun_group.tests[-1]
                        final_duration = final_test.duration

                        if nodeid not in test_durations:
                            test_durations[nodeid] = []

                        # Override any previous entry for this test in this session
                        # with the final duration from the rerun group
                        test_durations[nodeid].append(final_duration)

        # Calculate average duration per test
        avg_durations = [(nodeid, sum(durations) / len(durations)) for nodeid, durations in test_durations.items()]

        # Sort by duration (descending) and return top N
        return sorted(avg_durations, key=lambda x: x[1], reverse=True)[:limit]

    def identify_most_failing_tests(self, limit: int = 5) -> List[tuple]:
        """Identify tests with the highest failure counts.

        Args:
            limit: Maximum number of tests to return

        Returns:
            List of (test_nodeid, failure_count) tuples, sorted by count (descending)
        """
        if not self._sessions:
            return []

        # Count failures per test
        failure_counts = defaultdict(int)

        for session in self._sessions:
            # Process regular test results
            for test in session.test_results:
                if test.outcome == TestOutcome.FAILED:
                    failure_counts[test.nodeid] += 1

            # Process rerun groups if available
            if hasattr(session, "rerun_test_groups") and session.rerun_test_groups:
                for rerun_group in session.rerun_test_groups:
                    nodeid = rerun_group.nodeid

                    # For rerun groups, use the final outcome
                    if rerun_group.tests and len(rerun_group.tests) > 0:
                        final_test = rerun_group.tests[-1]
                        final_outcome = final_test.outcome

                        if final_outcome == TestOutcome.FAILED:
                            failure_counts[nodeid] += 1

        # Sort by failure count (descending) and return top N
        return sorted(failure_counts.items(), key=lambda x: x[1], reverse=True)[:limit]

    def identify_consistently_failing_tests(self, min_consecutive_failures: int = 2) -> List[dict]:
        """Identify tests that have consistently failed over time.

        This method tracks tests that have failed in consecutive sessions,
        including tests that were part of rerun groups with a final failure outcome.

        Args:
            min_consecutive_failures: Minimum number of consecutive sessions
                                     where the test must have failed

        Returns:
            List of dicts with details about consistently failing tests, including:
            - nodeid: Test identifier
            - consecutive_failures: Number of consecutive sessions with failures
            - first_failure: Timestamp of first failure in the streak
            - last_failure: Timestamp of most recent failure
            - failure_duration: Time period over which the test has been failing
        """
        if not self._sessions:
            return []

        # Sort sessions by timestamp for proper chronological analysis
        sorted_sessions = sorted(self._sessions, key=lambda s: s.session_start_time)

        # Track test outcomes across sessions
        test_history = {}  # {nodeid: [(session_timestamp, outcome), ...]}

        # First pass: collect test outcomes for each session
        for session in sorted_sessions:
            session_timestamp = session.session_start_time

            # Process regular test results
            for test in session.test_results:
                test_history.setdefault(test.nodeid, []).append((session_timestamp, test.outcome))

            # Process rerun groups if available
            if hasattr(session, "rerun_test_groups") and session.rerun_test_groups:
                for rerun_group in session.rerun_test_groups:
                    nodeid = rerun_group.nodeid

                    # For rerun groups, use the final outcome
                    if rerun_group.tests and len(rerun_group.tests) > 0:
                        final_test = rerun_group.tests[-1]
                        final_outcome = final_test.outcome

                        if nodeid not in test_history:
                            test_history[nodeid] = []

                        # Override any previous entry for this test in this session
                        # with the final outcome from the rerun group
                        test_history[nodeid].append((session_timestamp, final_outcome))

        # Second pass: analyze consecutive failures
        consistently_failing = []

        for nodeid, history in test_history.items():
            # Sort by timestamp to ensure chronological order
            sorted_history = sorted(history, key=lambda x: x[0])

            # Find streaks of consecutive failures
            current_streak = 0
            streak_start = None
            streak_end = None

            for timestamp, outcome in sorted_history:
                if outcome == TestOutcome.FAILED:
                    # Start or continue a streak
                    current_streak += 1
                    if streak_start is None:
                        streak_start = timestamp
                    streak_end = timestamp
                else:
                    # Reset the streak
                    if current_streak >= min_consecutive_failures:
                        # Record the completed streak before resetting
                        consistently_failing.append(
                            {
                                "nodeid": nodeid,
                                "consecutive_failures": current_streak,
                                "first_failure": streak_start,
                                "last_failure": streak_end,
                                "failure_duration": (streak_end - streak_start).total_seconds(),
                            }
                        )

                    current_streak = 0
                    streak_start = None
                    streak_end = None

            # Check if we ended with an active streak
            if current_streak >= min_consecutive_failures:
                consistently_failing.append(
                    {
                        "nodeid": nodeid,
                        "consecutive_failures": current_streak,
                        "first_failure": streak_start,
                        "last_failure": streak_end,
                        "failure_duration": (streak_end - streak_start).total_seconds(),
                    }
                )

        # Sort by consecutive failures (descending) and then by failure duration (descending)
        return sorted(
            consistently_failing,
            key=lambda x: (x["consecutive_failures"], x["failure_duration"]),
            reverse=True,
        )

    def identify_consistently_failing_tests_with_hysteresis(
        self,
        min_consecutive_failures: int = 2,
        hysteresis_threshold: float = 0.2,
        min_failure_rate: float = 0.7,
    ) -> List[dict]:
        """Identify tests that have consistently failed over time, allowing for some passes.

        This method tracks tests that have predominantly failed over time, but allows
        for occasional passes (hysteresis). This is useful for identifying tests that
        are problematic but might occasionally pass due to timing or environmental factors.

        Args:
            min_consecutive_failures: Minimum number of sessions where the test must have failed
            hysteresis_threshold: Maximum fraction of passes allowed within a failure streak
                                 (0.0 means no passes allowed, 1.0 means all passes allowed)
            min_failure_rate: Minimum overall failure rate required for a test to be considered

        Returns:
            List of dicts with details about consistently failing tests, including:
            - nodeid: Test identifier
            - failure_count: Number of failures in the streak
            - pass_count: Number of passes in the streak
            - failure_rate: Fraction of failures in the streak
            - first_occurrence: Timestamp of first occurrence in the streak
            - last_occurrence: Timestamp of most recent occurrence
            - streak_duration: Time period over which the test has been tracked
        """
        if not self._sessions:
            return []

        # Sort sessions by timestamp for proper chronological analysis
        sorted_sessions = sorted(self._sessions, key=lambda s: s.session_start_time)

        # Track test outcomes across sessions
        test_history = {}  # {nodeid: [(session_timestamp, outcome), ...]}

        # First pass: collect test outcomes for each session
        for session in sorted_sessions:
            session_timestamp = session.session_start_time

            # Process regular test results
            for test in session.test_results:
                test_history.setdefault(test.nodeid, []).append((session_timestamp, test.outcome))

            # Process rerun groups if available
            if hasattr(session, "rerun_test_groups") and session.rerun_test_groups:
                for rerun_group in session.rerun_test_groups:
                    nodeid = rerun_group.nodeid

                    # For rerun groups, use the final outcome
                    if rerun_group.tests and len(rerun_group.tests) > 0:
                        final_test = rerun_group.tests[-1]
                        final_outcome = final_test.outcome

                        if nodeid not in test_history:
                            test_history[nodeid] = []

                        # Override any previous entry for this test in this session
                        # with the final outcome from the rerun group
                        test_history[nodeid].append((session_timestamp, final_outcome))

        # Second pass: analyze failure patterns with hysteresis
        failing_with_hysteresis = []

        for nodeid, history in test_history.items():
            # Skip tests with too few occurrences
            if len(history) < min_consecutive_failures:
                continue

            # Analyze the entire history as a single streak with hysteresis
            failure_count = sum(1 for _, outcome in history if outcome == TestOutcome.FAILED)
            total_count = len(history)

            # Calculate failure rate
            failure_rate = failure_count / total_count if total_count > 0 else 0.0

            # Check if this test meets the criteria
            if (
                failure_count >= min_consecutive_failures
                and failure_rate >= min_failure_rate
                and (1.0 - failure_rate) <= hysteresis_threshold
            ):
                # This test is consistently failing with allowed hysteresis
                first_timestamp = history[0][0]
                last_timestamp = history[-1][0]

                failing_with_hysteresis.append(
                    {
                        "nodeid": nodeid,
                        "failure_count": failure_count,
                        "pass_count": total_count - failure_count,
                        "failure_rate": failure_rate,
                        "first_occurrence": first_timestamp,
                        "last_occurrence": last_timestamp,
                        "streak_duration": (last_timestamp - first_timestamp).total_seconds(),
                    }
                )

        # Sort by failure rate (descending) and then by streak duration (descending)
        return sorted(
            failing_with_hysteresis,
            key=lambda x: (x["failure_rate"], x["streak_duration"]),
            reverse=True,
        )


def analysis(sessions: Optional[list] = None, profile_name: Optional[str] = None, **kwargs) -> "Analysis":
    """
    Factory function to create a new Analysis instance.

    Args:
        sessions: Optional list of sessions to use
        profile_name: Optional profile name to use
        **kwargs: Additional keyword arguments for Analysis

    Returns:
        Analysis instance
    """
    return Analysis(sessions=sessions, profile_name=profile_name, **kwargs)


def analysis_with_profile(profile_name: str) -> "Analysis":
    """
    Factory function to create a new Analysis instance for a specific profile.

    Args:
        profile_name: Name of the profile to use

    Returns:
        New Analysis instance configured with the specified profile
    """
    return Analysis(profile_name=profile_name)
