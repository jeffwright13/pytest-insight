"""High-level insights for pytest-insight.

This module provides advanced insights and analytics that build upon the core Analysis class:

1. TestInsights - Extracts patterns and trends from test data
2. SessionInsights - Analyzes session-level metrics and health
3. TrendInsights - Identifies trends over time
4. PatternInsights - Detects test patterns and correlations

These insights follow the fluent interface pattern established in the pytest-insight API,
allowing for intuitive method chaining while preserving session context.
"""

from collections import Counter, defaultdict
from typing import Any, Dict, Optional

from pytest_insight.analysis import Analysis
from pytest_insight.models import TestOutcome


class TestInsights:
    """Test-level insights and analytics.

    Extracts patterns and trends from individual tests while preserving session context.
    """

    def __init__(self, analysis: Analysis):
        """Initialize with an Analysis instance.

        Args:
            analysis: Analysis instance to use for insights
        """
        self.analysis = analysis
        self._sessions = analysis._sessions

    def outcome_distribution(self) -> Dict[str, Any]:
        """Analyze test outcome distribution across all sessions.

        Returns:
            Dict containing:
            - total_tests: Total number of tests
            - outcomes: Dict mapping outcomes to counts and percentages
            - most_common: List of most common outcomes
        """
        outcome_counts = Counter()
        total_tests = 0

        for session in self._sessions:
            for test in session.test_results:
                outcome_counts[test.outcome] += 1
                total_tests += 1

        # Calculate percentages
        outcomes = {}
        for outcome, count in outcome_counts.items():
            percentage = (count / total_tests) * 100 if total_tests > 0 else 0
            outcomes[outcome] = {"count": count, "percentage": percentage}

        return {"total_tests": total_tests, "outcomes": outcomes, "most_common": outcome_counts.most_common()}

    def flaky_tests(self) -> Dict[str, Any]:
        """Identify flaky tests across all sessions.

        A flaky test is one that has been rerun and eventually passed.

        Returns:
            Dict containing:
            - flaky_tests: Dict mapping nodeids to flakiness data
            - total_flaky: Total number of flaky tests
            - most_flaky: List of most flaky tests by rerun count
        """
        flaky_tests = {}

        for session in self._sessions:
            if hasattr(session, "rerun_test_groups") and session.rerun_test_groups:
                for rerun_group in session.rerun_test_groups:
                    if rerun_group.final_outcome == TestOutcome.PASSED:
                        nodeid = rerun_group.nodeid
                        if nodeid not in flaky_tests:
                            flaky_tests[nodeid] = {"reruns": 0, "sessions": set(), "pass_rate": 0.0}
                        flaky_tests[nodeid]["reruns"] += (
                            len(rerun_group.tests) - 1
                        )  # Subtract 1 for the final passing test
                        flaky_tests[nodeid]["sessions"].add(session.session_id)

        # Calculate pass rates
        for nodeid, data in flaky_tests.items():
            total_runs = data["reruns"] + len(data["sessions"])  # Total runs = reruns + final passing runs
            data["pass_rate"] = len(data["sessions"]) / total_runs if total_runs > 0 else 0
            data["sessions"] = list(data["sessions"])  # Convert set to list for serialization

        # Sort by number of reruns
        most_flaky = sorted(
            [(nodeid, data) for nodeid, data in flaky_tests.items()], key=lambda x: x[1]["reruns"], reverse=True
        )

        return {"flaky_tests": flaky_tests, "total_flaky": len(flaky_tests), "most_flaky": most_flaky}

    def slowest_tests(self, limit: int = 10) -> Dict[str, Any]:
        """Identify the slowest tests across all sessions.

        Args:
            limit: Maximum number of slow tests to return

        Returns:
            Dict containing:
            - slowest_tests: List of (nodeid, duration) tuples
            - avg_duration: Average test duration
            - total_duration: Total test duration
        """
        test_durations = []
        total_duration = 0
        test_count = 0

        for session in self._sessions:
            for test in session.test_results:
                test_durations.append((test.nodeid, test.duration))
                total_duration += test.duration
                test_count += 1

        # Sort by duration
        sorted_durations = sorted(test_durations, key=lambda x: x[1], reverse=True)
        avg_duration = total_duration / test_count if test_count > 0 else 0

        return {
            "slowest_tests": sorted_durations[:limit],
            "avg_duration": avg_duration,
            "total_duration": total_duration,
        }

    def test_patterns(self) -> Dict[str, Any]:
        """Analyze test name patterns to identify common testing approaches.

        Returns:
            Dict containing:
            - modules: Counter of test modules
            - prefixes: Counter of test name prefixes
            - top_modules: List of most common modules
            - top_prefixes: List of most common prefixes
        """
        modules = Counter()
        test_prefixes = Counter()

        for session in self._sessions:
            for test in session.test_results:
                # Extract module from nodeid (format: path/to/module.py::test_name)
                parts = test.nodeid.split("::")
                if len(parts) > 0:
                    module = parts[0]
                    modules[module] += 1

                # Extract test name and prefix
                if len(parts) > 1:
                    test_name = parts[1]
                    words = test_name.split("_")
                    if len(words) > 2:
                        prefix = "_".join(words[:2]) + "_"
                        test_prefixes[prefix] += 1

        return {
            "modules": dict(modules),
            "prefixes": dict(test_prefixes),
            "top_modules": modules.most_common(5),
            "top_prefixes": test_prefixes.most_common(5),
        }


class SessionInsights:
    """Session-level insights and analytics.

    Analyzes metrics and health at the session level.
    """

    def __init__(self, analysis: Analysis):
        """Initialize with an Analysis instance.

        Args:
            analysis: Analysis instance to use for insights
        """
        self.analysis = analysis
        self._sessions = analysis._sessions if analysis._sessions is not None else []

    def sut_comparison(self) -> Dict[str, Any]:
        """Compare metrics between different SUTs.

        Returns:
            Dict containing:
            - suts: List of available SUTs
            - comparisons: Dict mapping SUT pairs to comparison results
            - best_sut: SUT with highest health score
        """
        # Get available SUTs
        suts = set(session.sut_name for session in self._sessions)
        if len(suts) < 2:
            return {"suts": list(suts), "comparisons": {}, "best_sut": next(iter(suts)) if suts else None}

        # Group sessions by SUT
        sut_sessions = defaultdict(list)
        for session in self._sessions:
            sut_sessions[session.sut_name].append(session)

        # Compare each pair of SUTs
        comparisons = {}
        sut_health_scores = {}

        for sut1 in suts:
            for sut2 in suts:
                if sut1 >= sut2:  # Skip self-comparisons and duplicates
                    continue

                comparison_key = f"{sut1}_vs_{sut2}"
                comparison = self.analysis.compare_health(
                    base_sessions=sut_sessions[sut1], target_sessions=sut_sessions[sut2]
                )

                # Store health scores for determining best SUT
                if sut1 not in sut_health_scores:
                    sut_health_scores[sut1] = comparison["base_health"]["health_score"]["overall_score"]
                if sut2 not in sut_health_scores:
                    sut_health_scores[sut2] = comparison["target_health"]["health_score"]["overall_score"]

                # Store comparison results
                comparisons[comparison_key] = {
                    "base_sut": sut1,
                    "target_sut": sut2,
                    "base_health": comparison["base_health"]["health_score"]["overall_score"],
                    "target_health": comparison["target_health"]["health_score"]["overall_score"],
                    "health_difference": comparison["health_difference"],
                    "improved": comparison["improved"],
                }

        # Determine best SUT by health score
        best_sut = max(sut_health_scores.items(), key=lambda x: x[1])[0] if sut_health_scores else None

        return {"suts": list(suts), "comparisons": comparisons, "best_sut": best_sut}

    def session_metrics(self) -> Dict[str, Any]:
        """Calculate comprehensive session metrics.

        Returns:
            Dict containing:
            - total_sessions: Total number of sessions
            - avg_duration: Average session duration
            - avg_tests_per_session: Average number of tests per session
            - failure_rate: Overall failure rate
            - warning_rate: Overall warning rate
        """
        total_sessions = len(self._sessions)
        total_duration = 0
        total_tests = 0
        total_failures = 0
        total_warnings = 0

        for session in self._sessions:
            total_duration += session.session_duration
            session_tests = len(session.test_results)
            total_tests += session_tests

            # Count failures and warnings
            for test in session.test_results:
                if test.outcome == TestOutcome.FAILED:
                    total_failures += 1
                if test.has_warning:
                    total_warnings += 1

        # Calculate averages and rates
        avg_duration = total_duration / total_sessions if total_sessions > 0 else 0
        avg_tests = total_tests / total_sessions if total_sessions > 0 else 0
        failure_rate = total_failures / total_tests if total_tests > 0 else 0
        warning_rate = total_warnings / total_tests if total_tests > 0 else 0

        return {
            "total_sessions": total_sessions,
            "avg_duration": avg_duration,
            "avg_tests_per_session": avg_tests,
            "failure_rate": failure_rate,
            "warning_rate": warning_rate,
        }


class TrendInsights:
    """Trend insights and analytics.

    Identifies trends and patterns over time.
    """

    def __init__(self, analysis: Analysis):
        """Initialize with an Analysis instance.

        Args:
            analysis: Analysis instance to use for insights
        """
        self.analysis = analysis
        self._sessions = analysis._sessions

    def duration_trends(self) -> Dict[str, Any]:
        """Analyze session duration trends over time.

        Returns:
            Dict containing:
            - daily_durations: List of (day, duration) tuples
            - trend_percentage: Percentage change in duration
            - increasing: Boolean indicating if trend is increasing
        """
        # Sort sessions by start time
        sorted_sessions = sorted(self._sessions, key=lambda s: s.session_start_time)

        if len(sorted_sessions) < 2:
            return {"daily_durations": [], "trend_percentage": 0.0, "increasing": False}

        # Group sessions by day
        sessions_by_day = {}
        for session in sorted_sessions:
            day = session.session_start_time.date()
            if day not in sessions_by_day:
                sessions_by_day[day] = []
            sessions_by_day[day].append(session)

        # Calculate average duration per day
        daily_durations = []
        for day, day_sessions in sorted(sessions_by_day.items()):
            avg_duration = sum(s.session_duration for s in day_sessions) / len(day_sessions)
            daily_durations.append((day, avg_duration))

        # Calculate trend
        if len(daily_durations) >= 2:
            first_duration = daily_durations[0][1]
            last_duration = daily_durations[-1][1]
            if first_duration > 0:
                trend_percentage = ((last_duration - first_duration) / first_duration) * 100
                increasing = trend_percentage > 0
            else:
                trend_percentage = 0.0
                increasing = False
        else:
            trend_percentage = 0.0
            increasing = False

        return {"daily_durations": daily_durations, "trend_percentage": trend_percentage, "increasing": increasing}

    def failure_trends(self) -> Dict[str, Any]:
        """Analyze test failure trends over time.

        Returns:
            Dict containing:
            - daily_failure_rates: List of (day, rate) tuples
            - trend_percentage: Percentage change in failure rate
            - improving: Boolean indicating if trend is improving (decreasing)
        """
        # Sort sessions by start time
        sorted_sessions = sorted(self._sessions, key=lambda s: s.session_start_time)

        if len(sorted_sessions) < 2:
            return {"daily_failure_rates": [], "trend_percentage": 0.0, "improving": False}

        # Group sessions by day
        sessions_by_day = {}
        for session in sorted_sessions:
            day = session.session_start_time.date()
            if day not in sessions_by_day:
                sessions_by_day[day] = []
            sessions_by_day[day].append(session)

        # Calculate failure rate per day
        daily_failure_rates = []
        for day, day_sessions in sorted(sessions_by_day.items()):
            total_tests = 0
            failed_tests = 0
            for session in day_sessions:
                for test in session.test_results:
                    total_tests += 1
                    if test.outcome == TestOutcome.FAILED:
                        failed_tests += 1

            if total_tests > 0:
                failure_rate = failed_tests / total_tests
                daily_failure_rates.append((day, failure_rate))

        # Calculate trend
        if len(daily_failure_rates) >= 2:
            first_rate = daily_failure_rates[0][1]
            last_rate = daily_failure_rates[-1][1]
            if first_rate > 0:
                trend_percentage = ((last_rate - first_rate) / first_rate) * 100
                improving = trend_percentage < 0  # Decreasing failure rate is an improvement
            else:
                trend_percentage = last_rate * 100
                improving = trend_percentage <= 0
        else:
            trend_percentage = 0.0
            improving = False

        return {
            "daily_failure_rates": daily_failure_rates,
            "trend_percentage": trend_percentage,
            "improving": improving,
        }

    def time_comparison(self) -> Dict[str, Any]:
        """Compare test metrics between different time periods.

        Automatically splits sessions into two time periods for comparison.

        Returns:
            Dict containing:
            - early_period: Dict with early period metrics
            - late_period: Dict with late period metrics
            - health_difference: Difference in health scores
            - improving: Boolean indicating if health is improving
        """
        # Sort sessions by start time
        sorted_sessions = sorted(self._sessions, key=lambda s: s.session_start_time)

        if len(sorted_sessions) < 2:
            return {"early_period": {}, "late_period": {}, "health_difference": 0.0, "improving": False}

        # Split into two halves
        midpoint = len(sorted_sessions) // 2
        early_sessions = sorted_sessions[:midpoint]
        late_sessions = sorted_sessions[midpoint:]

        # Get date ranges for each period
        early_start = min(s.session_start_time for s in early_sessions).date()
        early_end = max(s.session_start_time for s in early_sessions).date()
        late_start = min(s.session_start_time for s in late_sessions).date()
        late_end = max(s.session_start_time for s in late_sessions).date()

        # Compare health
        comparison = self.analysis.compare_health(base_sessions=early_sessions, target_sessions=late_sessions)

        # Calculate additional metrics
        early_test_count = sum(len(s.test_results) for s in early_sessions)
        late_test_count = sum(len(s.test_results) for s in late_sessions)

        early_avg_duration = sum(s.session_duration for s in early_sessions) / len(early_sessions)
        late_avg_duration = sum(s.session_duration for s in late_sessions) / len(late_sessions)

        duration_change = (
            ((late_avg_duration - early_avg_duration) / early_avg_duration) * 100 if early_avg_duration > 0 else 0
        )

        return {
            "early_period": {
                "date_range": (early_start, early_end),
                "sessions": len(early_sessions),
                "tests": early_test_count,
                "avg_duration": early_avg_duration,
                "health_score": comparison["base_health"]["health_score"]["overall_score"],
            },
            "late_period": {
                "date_range": (late_start, late_end),
                "sessions": len(late_sessions),
                "tests": late_test_count,
                "avg_duration": late_avg_duration,
                "health_score": comparison["target_health"]["health_score"]["overall_score"],
            },
            "health_difference": comparison["health_difference"],
            "improving": comparison["improved"],
            "duration_change": duration_change,
        }


class Insights:
    """Top-level insights for pytest-insight.

    Provides access to all insight components:
    - TestInsights: Test-level insights
    - SessionInsights: Session-level insights
    - TrendInsights: Trend analysis insights

    This class follows the fluent interface pattern used throughout pytest-insight,
    allowing for intuitive method chaining while preserving session context.

    Example usage:
        # Basic insights
        insights = Insights()
        flaky_report = insights.tests.flaky_tests()

        # With filtering
        filtered_insights = insights.with_query(lambda q: q.in_last_days(30))
        trend_report = filtered_insights.trends.duration_trends()

        # Combining with Analysis
        analysis = Analysis()
        insights = Insights(analysis=analysis)
        combined_report = {
            "health": insights.summary_report(),
            "trends": insights.trends.failure_trends()
        }
    """

    def __init__(self, analysis: Optional[Analysis] = None):
        """Initialize insight components.

        Args:
            analysis: Optional Analysis instance to use. If None, creates a new one.
        """
        self.analysis = analysis or Analysis()

        # Initialize insight components
        self.tests = TestInsights(self.analysis)
        self.sessions = SessionInsights(self.analysis)
        self.trends = TrendInsights(self.analysis)

    def with_query(self, query_func):
        """Apply a query function to filter sessions.

        This method allows using the full power of the Query class
        without duplicating its functionality in Insights.

        Args:
            query_func: A function that takes a Query instance and returns a modified Query

        Returns:
            Insights instance with filtered sessions

        Example:
            insights.with_query(lambda q: q.in_last_days(7).for_sut("service"))
        """
        filtered_analysis = self.analysis.with_query(query_func)
        return Insights(analysis=filtered_analysis)

    def summary_report(self) -> Dict[str, Any]:
        """Generate a comprehensive summary report.

        Combines insights from all components to provide a complete picture.

        Returns:
            Dict containing:
            - health: Health report from Analysis
            - test_insights: Key test insights
            - session_insights: Key session insights
            - trend_insights: Key trend insights
        """
        # Get health report from Analysis
        health_report = self.analysis.health_report()

        # Get key insights from each component
        test_insights = {
            "outcome_distribution": self.tests.outcome_distribution(),
            "flaky_tests": self.tests.flaky_tests(),
            "slowest_tests": self.tests.slowest_tests(limit=5),
        }

        session_insights = {"metrics": self.sessions.session_metrics()}

        trend_insights = {
            "duration_trends": self.trends.duration_trends(),
            "failure_trends": self.trends.failure_trends(),
        }

        return {
            "health": health_report,
            "test_insights": test_insights,
            "session_insights": session_insights,
            "trend_insights": trend_insights,
        }

    def console_summary(self) -> Dict[str, Any]:
        """Generate a concise summary suitable for console output.

        Returns:
            Dict containing the most important metrics and insights
            formatted for easy display in a terminal.
        """
        # Get health score
        health_report = self.analysis.health_report()
        health_score = health_report["health_score"]["overall_score"]

        # Get session metrics
        session_metrics = self.sessions.session_metrics()

        # Get outcome distribution
        outcome_dist = self.tests.outcome_distribution()

        # Get flaky tests
        flaky = self.tests.flaky_tests()

        # Get slowest tests (limited to 3)
        slow_tests = self.tests.slowest_tests(limit=3)

        # Get failure trends
        failure_trends = self.trends.failure_trends()

        return {
            "health_score": health_score,
            "session_count": session_metrics["total_sessions"],
            "failure_rate": session_metrics["failure_rate"] * 100,  # Convert to percentage
            "outcome_distribution": outcome_dist["most_common"],
            "flaky_test_count": flaky["total_flaky"],
            "most_flaky": flaky["most_flaky"][:3] if flaky["most_flaky"] else [],
            "slowest_tests": slow_tests["slowest_tests"],
            "failure_trend": {"improving": failure_trends["improving"], "change": failure_trends["trend_percentage"]},
        }
