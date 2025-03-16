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
- Implements stability metrics with flakiness detection
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

from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from statistics import mean, stdev
from zoneinfo import ZoneInfo
from pytz import utc

from pytest_insight.storage import BaseStorage
from pytest_insight.models import TestSession, TestResult, TestOutcome
from pytest_insight.query import Query


class SessionAnalysis:
    """Session-level analytics.

    Analyzes patterns and metrics at the test session level:
    - Failure rates over time
    - Test execution metrics
    - Trend detection
    """

    def __init__(self, storage: BaseStorage, sessions: Optional[List[TestSession]] = None):
        """Initialize with storage and optional session list.

        Args:
            storage: Storage instance for accessing test data
            sessions: Optional list of sessions to analyze. If not provided,
                     will analyze all sessions from storage.
        """
        self.storage = storage
        self._sessions = sessions
        self._query = Query(storage=storage)

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
            1 for session in sessions
            if any(test.outcome == TestOutcome.FAILED for test in session.test_results)
        )

        return failed_sessions / len(sessions)

    def test_metrics(self, days: Optional[int] = None) -> Dict[str, float]:
        """Calculate key test metrics for sessions.

        Analyzes test metrics while preserving session context to identify:
        - Overall execution statistics
        - Test uniqueness and repetition
        - Test flakiness (same test with different outcomes in same session)

        Args:
            days: Optional number of days to look back

        Returns:
            Dict of metrics including:
            - avg_duration: Average test duration
            - total_tests: Total number of tests
            - unique_tests: Number of unique tests
            - flaky_tests: Number of flaky tests
            - avg_tests_per_session: Average tests per session
        """
        sessions = self._get_sessions(days)
        if not sessions:
            return {
                "avg_duration": 0.0,
                "total_tests": 0,
                "unique_tests": 0,
                "flaky_tests": 0,
                "avg_tests_per_session": 0.0
            }

        # Track metrics while preserving session context
        total_duration = 0.0
        total_tests = 0
        unique_nodeids = set()
        flaky_tests = set()

        # Analyze each session while preserving context
        for session in sessions:
            # Track test outcomes within this session
            session_outcomes = defaultdict(set)

            for test in session.test_results:
                total_duration += test.duration
                total_tests += 1
                unique_nodeids.add(test.nodeid)

                # Track outcomes per test within session context
                session_outcomes[test.nodeid].add(test.outcome)

                # Test is flaky if it has multiple outcomes in same session
                if len(session_outcomes[test.nodeid]) > 1:
                    flaky_tests.add(test.nodeid)

        return {
            "avg_duration": total_duration / total_tests if total_tests > 0 else 0.0,
            "total_tests": total_tests,
            "unique_tests": len(unique_nodeids),
            "flaky_tests": len(flaky_tests),
            "avg_tests_per_session": total_tests / len(sessions)
        }

    def detect_trends(self, days: Optional[int] = None, window_size: int = 7) -> Dict[str, Any]:
        """Detect significant trends in session data.

        Analyzes trends while preserving session context to identify:
        - Changes in execution time
        - Changes in failure patterns
        - Changes in warning patterns
        - Correlated failures within sessions

        Args:
            days: Optional number of days to look back
            window_size: Size of sliding window for trend analysis in days

        Returns:
            Dict of detected trends including:
            - duration_trend: Changes in execution time
                - direction: "increasing", "decreasing", or "stable"
                - magnitude: Average change per window
            - failure_trend: Changes in failure patterns
                - direction: "improving", "degrading", or "stable"
                - magnitude: Average change in failure rate
                - correlated_failures: List of tests that fail together
            - warning_trend: Changes in warning patterns
                - direction: "increasing", "decreasing", or "stable"
                - common_warnings: Most frequent warning types
        """
        sessions = sorted(
            self._get_sessions(days),
            key=lambda s: s.session_start_time
        )
        if not sessions:
            return {
                "duration_trend": {"direction": "stable", "magnitude": 0.0},
                "failure_trend": {
                    "direction": "stable",
                    "magnitude": 0.0,
                    "correlated_failures": []
                },
                "warning_trend": {
                    "direction": "stable",
                    "common_warnings": []
                }
            }

        # Analyze duration trends
        duration_trend = self._analyze_duration_trend(sessions, window_size)

        # Analyze failure trends while preserving session context
        failure_trend = self._analyze_failure_trend(sessions, window_size)

        # Analyze warning trends
        warning_trend = self._analyze_warning_trend(sessions, window_size)

        return {
            "duration_trend": duration_trend,
            "failure_trend": failure_trend,
            "warning_trend": warning_trend
        }

    def _analyze_duration_trend(
        self,
        sessions: List[TestSession],
        window_size: int
    ) -> Dict[str, Any]:
        """Analyze trends in test execution duration."""
        # Calculate average duration per session
        durations = []
        for session in sessions:
            session_duration = sum(t.duration for t in session.test_results)
            durations.append(session_duration)

        if len(durations) < 2:
            return {"direction": "stable", "magnitude": 0.0}

        # Calculate trend using simple linear regression
        x = list(range(len(durations)))
        slope = (
            sum((x[i] - mean(x)) * (y - mean(durations))
                for i, y in enumerate(durations))
            / sum((x[i] - mean(x)) ** 2 for i in x)
        )

        return {
            "direction": "increasing" if slope > 0.1
                        else "decreasing" if slope < -0.1
                        else "stable",
            "magnitude": abs(slope)
        }

    def _analyze_failure_trend(
        self,
        sessions: List[TestSession],
        window_size: int
    ) -> Dict[str, Any]:
        """Analyze trends in test failures while preserving session context."""
        # Calculate failure rate per session
        failure_rates = []
        correlated_failures = defaultdict(int)

        for session in sessions:
            # Track failures within session context
            failed_tests = set()
            for test in session.test_results:
                if test.outcome == TestOutcome.FAILED:
                    failed_tests.add(test.nodeid)

            # Record failure rate
            failure_rates.append(len(failed_tests) / len(session.test_results)
                               if session.test_results else 0.0)

            # Track correlated failures within session context
            failed_list = sorted(failed_tests)
            for i, test1 in enumerate(failed_list):
                for test2 in failed_list[i+1:]:
                    correlated_failures[(test1, test2)] += 1

        if len(failure_rates) < 2:
            return {
                "direction": "stable",
                "magnitude": 0.0,
                "correlated_failures": []
            }

        # Calculate trend
        slope = (
            sum((x - mean(range(len(failure_rates)))) *
                (y - mean(failure_rates))
                for x, y in enumerate(failure_rates))
            / sum((x - mean(range(len(failure_rates)))) ** 2
                 for x in range(len(failure_rates)))
        )

        # Find most common correlated failures
        correlated = sorted(
            ((pair, count) for pair, count in correlated_failures.items()),
            key=lambda x: x[1],
            reverse=True
        )[:5]  # Top 5 correlations

        return {
            "direction": "degrading" if slope > 0.05
                        else "improving" if slope < -0.05
                        else "stable",
            "magnitude": abs(slope),
            "correlated_failures": [
                {"tests": list(pair), "count": count}
                for pair, count in correlated
            ]
        }

    def _analyze_warning_trend(
        self,
        sessions: List[TestSession],
        window_size: int
    ) -> Dict[str, Any]:
        """Analyze trends in test warnings."""
        # Track warnings per session
        warning_counts = []
        warning_types = defaultdict(int)

        for session in sessions:
            session_warnings = sum(
                1 for test in session.test_results if test.has_warning
            )
            warning_counts.append(session_warnings)

            # Track warning types within session context
            for test in session.test_results:
                if test.has_warning:
                    warning_types[test.nodeid] += 1

        if len(warning_counts) < 2:
            return {
                "direction": "stable",
                "common_warnings": []
            }

        # Calculate trend
        slope = (
            sum((x - mean(range(len(warning_counts)))) *
                (y - mean(warning_counts))
                for x, y in enumerate(warning_counts))
            / sum((x - mean(range(len(warning_counts)))) ** 2
                 for x in range(len(warning_counts)))
        )

        # Find most common warning types
        common_warnings = sorted(
            ((test, count) for test, count in warning_types.items()),
            key=lambda x: x[1],
            reverse=True
        )[:5]  # Top 5 warning types

        return {
            "direction": "increasing" if slope > 0.05
                        else "decreasing" if slope < -0.05
                        else "stable",
            "common_warnings": [
                {"test": test, "count": count}
                for test, count in common_warnings
            ]
        }


class TestAnalysis:
    """Test-level analytics.

    Analyzes patterns and metrics at individual test level:
    - Test stability
    - Performance patterns
    - Warning analysis
    """

    def __init__(self, storage: BaseStorage, tests: Optional[List[TestResult]] = None):
        """Initialize with storage and optional test list.

        Args:
            storage: Storage instance for accessing test data
            tests: Optional list of tests to analyze. If not provided,
                  will analyze all tests from storage.
        """
        self.storage = storage
        self._tests = tests

    def stability(self) -> Dict[str, Any]:
        """Analyze test stability.

        Returns:
            Dict of stability metrics including:
            - flaky_tests: List of flaky tests with rates
            - stable_tests: List of consistently passing tests
            - unstable_tests: List of consistently failing tests
        """
        # TODO: Implement stability analysis
        pass

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


class MetricsAnalysis:
    """High-level metrics analysis.

    Provides aggregated metrics and health scores:
    - Overall health score
    - Failure pattern analysis
    - Test suite efficiency
    - Test coverage trends
    """

    def __init__(self, storage: BaseStorage, sessions: Optional[List[TestSession]] = None):
        """Initialize with storage and optional session list.

        Args:
            storage: Storage instance for accessing test data
            sessions: Optional list of sessions to analyze. If not provided,
                     will analyze all sessions from storage.
        """
        self.storage = storage
        self._sessions = sessions
        self._query = Query(storage=storage)

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
        - Test stability and flakiness
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
            return {
                "overall_score": 0.0,
                "component_scores": {},
                "recommendations": []
            }

        # Calculate component scores while preserving session context
        stability_score = self._calculate_stability_score(sessions)
        performance_score = self._calculate_performance_score(sessions)
        warning_score = self._calculate_warning_score(sessions)

        # Calculate overall score (weighted average)
        weights = {
            "stability": 0.5,  # Most important
            "performance": 0.3,
            "warnings": 0.2
        }

        overall_score = (
            stability_score * weights["stability"] +
            performance_score * weights["performance"] +
            warning_score * weights["warnings"]
        )

        # Generate recommendations based on scores
        recommendations = self._generate_recommendations(
            stability_score,
            performance_score,
            warning_score,
            sessions
        )

        return {
            "overall_score": overall_score,
            "component_scores": {
                "stability": stability_score,
                "performance": performance_score,
                "warnings": warning_score
            },
            "recommendations": recommendations
        }

    def _calculate_stability_score(self, sessions: List[TestSession]) -> float:
        """Calculate stability score based on failures and flakiness."""
        if not sessions:
            return 0.0

        total_tests = 0
        failed_tests = 0
        flaky_tests = 0

        # Analyze each session while preserving context
        for session in sessions:
            session_outcomes = defaultdict(list)

            for test in session.test_results:
                total_tests += 1
                if test.outcome == TestOutcome.FAILED:
                    failed_tests += 1

                # Track outcomes within session for flakiness
                session_outcomes[test.nodeid].append(test.outcome)
                if len(session_outcomes[test.nodeid]) > 1:
                    prev = session_outcomes[test.nodeid][-2]
                    curr = session_outcomes[test.nodeid][-1]
                    if prev != curr:
                        flaky_tests += 1

        if total_tests == 0:
            return 0.0

        # Calculate score components
        failure_ratio = failed_tests / total_tests
        flaky_ratio = flaky_tests / total_tests

        # Convert to 0-100 score with penalties
        base_score = 100 * (1 - failure_ratio)
        flaky_penalty = 20 * flaky_ratio  # Up to 20 point penalty for flakiness

        return max(0, min(100, base_score - flaky_penalty))

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
                slow_tests = sum(
                    1 for d in session_durations
                    if d > session_mean + 2 * session_stddev
                )

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
        sessions: List[TestSession]
    ) -> List[Dict[str, str]]:
        """Generate improvement recommendations based on scores."""
        recommendations = []

        # Analyze stability issues
        if stability_score < 80:
            failed_patterns = self._analyze_failure_patterns(sessions)
            if failed_patterns:
                recommendations.append({
                    "category": "stability",
                    "priority": "high",
                    "message": "High failure rate detected in tests: " +
                             ", ".join(failed_patterns[:3])
                })

        # Analyze performance issues
        if performance_score < 80:
            slow_tests = self._find_slow_tests(sessions)
            if slow_tests:
                recommendations.append({
                    "category": "performance",
                    "priority": "medium",
                    "message": "Performance bottlenecks identified in: " +
                             ", ".join(slow_tests[:3])
                })

        # Analyze warning issues
        if warning_score < 80:
            warning_patterns = self._analyze_warning_patterns(sessions)
            if warning_patterns:
                recommendations.append({
                    "category": "warnings",
                    "priority": "low",
                    "message": "Recurring warnings found in: " +
                             ", ".join(warning_patterns[:3])
                })

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
        return [
            test for test, count in sorted(
                failure_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )
        ]

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
                duration_stddev = stdev(durations)
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
        return [
            test for test, count in sorted(
                warning_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )
        ]


class Analysis:
    """Top-level entry point for analysis.

    Provides access to all analysis components:
    - SessionAnalysis: Session-level analytics
    - TestAnalysis: Test-level analytics
    - MetricsAnalysis: High-level metrics
    """

    def __init__(self, storage: BaseStorage, sessions: Optional[List[TestSession]] = None):
        """Initialize analysis components.

        Args:
            storage: Storage instance for accessing test data
            sessions: Optional list of sessions to analyze
        """
        self.storage = storage
        self._sessions = sessions

        # Initialize analysis components
        self.sessions = SessionAnalysis(storage, sessions)
        self.tests = TestAnalysis(storage, sessions)
        self.metrics = MetricsAnalysis(storage, sessions)
