"""
Insights module for pytest-insight.

This module provides classes for generating insights from test data.
It includes functionality for analyzing test outcomes, identifying patterns,
and generating recommendations.

The API follows a fluent interface design pattern,
allowing for intuitive method chaining while preserving session context.
"""

from collections import Counter, defaultdict
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

import colorama
from colorama import Fore, Style

if TYPE_CHECKING:
    from pytest_insight.core.analysis import Analysis  # type: ignore
else:
    # This allows tests to mock Analysis directly
    Analysis = None

from pytest_insight.core.models import TestOutcome
from pytest_insight.core.storage import get_storage_instance


class TestInsights:
    """Test-level insights and analytics.

    Extracts patterns and trends from individual tests while preserving session context.
    """

    def __init__(self, sessions):
        """Initialize with a list of test sessions.

        Args:
            sessions: List of test sessions to analyze
        """
        self._sessions = sessions

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

        return {
            "total_tests": total_tests,
            "outcomes": outcomes,
            "most_common": outcome_counts.most_common(),
        }

    def unreliable_tests(self) -> Dict[str, Any]:
        """Identify unreliable tests across all sessions.

        An unreliable test is one that has been rerun and eventually passed.

        Returns:
            Dict containing:
            - unreliable_tests: Dict mapping nodeids to reliability data
            - total_unreliable: Total number of unreliable tests
            - most_unreliable: List of most unreliable tests by rerun count
        """
        unreliable_tests = {}

        for session in self._sessions:
            if hasattr(session, "rerun_test_groups") and session.rerun_test_groups:
                for rerun_group in session.rerun_test_groups:
                    if rerun_group.final_outcome == TestOutcome.PASSED:
                        nodeid = rerun_group.nodeid
                        if nodeid not in unreliable_tests:
                            unreliable_tests[nodeid] = {
                                "reruns": 0,
                                "sessions": set(),
                                "pass_rate": 0.0,
                            }
                        unreliable_tests[nodeid]["reruns"] += (
                            len(rerun_group.tests) - 1
                        )  # Subtract 1 for the final passing test
                        unreliable_tests[nodeid]["sessions"].add(session.session_id)

        # Calculate pass rates
        for nodeid, data in unreliable_tests.items():
            total_runs = data["reruns"] + len(data["sessions"])  # Total runs = reruns + final passing runs
            data["pass_rate"] = len(data["sessions"]) / total_runs if total_runs > 0 else 0
            data["sessions"] = list(data["sessions"])  # Convert set to list for serialization

        # Sort by number of reruns
        most_unreliable = sorted(
            [(nodeid, data) for nodeid, data in unreliable_tests.items()],
            key=lambda x: x[1]["reruns"],
            reverse=True,
        )

        return {
            "unreliable_tests": unreliable_tests,
            "total_unreliable": len(unreliable_tests),
            "most_unreliable": most_unreliable,
        }

    def test_reliability_metrics(self) -> Dict[str, Any]:
        """Calculate test reliability metrics across all sessions.

        Returns:
            Dict containing:
            - reliability_index: Percentage of tests with consistent outcomes (higher is better)
            - unstable_tests: Dict mapping nodeids to tests requiring reruns
            - rerun_recovery_rate: Percentage of rerun tests that eventually passed
            - total_unstable: Total number of tests requiring reruns
            - health_score_penalty: Penalty to apply to health score based on test instability
        """
        unstable_tests = {}
        recovered_tests = 0
        total_reruns = 0

        for session in self._sessions:
            if hasattr(session, "rerun_test_groups") and session.rerun_test_groups:
                for rerun_group in session.rerun_test_groups:
                    total_reruns += 1
                    nodeid = rerun_group.nodeid

                    if rerun_group.final_outcome == TestOutcome.PASSED:
                        recovered_tests += 1

                    if nodeid not in unstable_tests:
                        unstable_tests[nodeid] = {
                            "reruns": 0,
                            "sessions": set(),
                            "final_outcomes": {},
                        }

                    unstable_tests[nodeid]["reruns"] += len(rerun_group.tests) - 1
                    unstable_tests[nodeid]["sessions"].add(session.session_id)

                    # Track final outcomes
                    outcome = rerun_group.final_outcome.value
                    unstable_tests[nodeid]["final_outcomes"][outcome] = (
                        unstable_tests[nodeid]["final_outcomes"].get(outcome, 0) + 1
                    )

        # Calculate total tests
        total_tests = 0
        for session in self._sessions:
            if hasattr(session, "test_results"):
                total_tests += len(session.test_results)

        # Calculate recovery rate
        rerun_recovery_rate = (recovered_tests / total_reruns * 100) if total_reruns > 0 else 100

        # Calculate reliability index (100% minus percentage of unstable tests)
        reliability_index = 100 - (len(unstable_tests) / total_tests * 100) if total_tests > 0 else 100

        # Calculate health score penalty (1 point for each percent of tests that required reruns)
        health_score_penalty = (len(unstable_tests) / total_tests * 100) if total_tests > 0 else 0

        # Convert sets to lists for serialization
        for nodeid, data in unstable_tests.items():
            data["sessions"] = list(data["sessions"])  # Convert set to list for serialization

        # Sort by number of reruns
        most_unstable = sorted(
            [(nodeid, data) for nodeid, data in unstable_tests.items()],
            key=lambda x: x[1]["reruns"],
            reverse=True,
        )

        return {
            "reliability_index": reliability_index,
            "unstable_tests": unstable_tests,
            "rerun_recovery_rate": rerun_recovery_rate,
            "total_unstable": len(unstable_tests),
            "health_score_penalty": health_score_penalty,
            "most_unstable": most_unstable,
        }

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

    def stability_timeline(self, days: int = 7, limit: int = 10) -> Dict[str, Any]:
        """Generate test stability timeline data for the given sessions.

        Tracks the stability of tests over time, showing how consistently tests produce
        the same results day by day. Stability is measured as the percentage of runs
        on a given day that produced the same outcome.

        Args:
            days: Number of most recent days to include in the timeline
            limit: Maximum number of tests to include in the timeline

        Returns:
            Dict containing:
            - timeline: Dict mapping test nodeids to date-based stability metrics
            - dates: List of dates in chronological order
            - trends: Dict mapping test nodeids to trend data
        """
        sessions = self._sessions
        if not sessions or len(sessions) <= 1:
            return {
                "timeline": {},
                "dates": [],
                "trends": {},
                "error": "Insufficient data for timeline analysis. Need data from multiple sessions.",
            }

        # Group sessions by date
        date_sessions = {}
        for session in sessions:
            session_date = session.session_start_time.date()
            if session_date not in date_sessions:
                date_sessions[session_date] = []
            date_sessions[session_date].append(session)

        # Sort dates chronologically
        all_dates = sorted(date_sessions.keys())

        # Limit to most recent days if specified
        if days and days > 0:
            sorted_dates = all_dates[-days:] if len(all_dates) > days else all_dates
        else:
            sorted_dates = all_dates

        if len(sorted_dates) <= 1:
            return {
                "timeline": {},
                "dates": sorted_dates,
                "trends": {},
                "error": "Insufficient data for timeline analysis. Need data from multiple dates.",
            }

        # Track stability metrics over time for the most frequently run tests
        test_run_counts = {}
        for session in sessions:
            for test_result in session.test_results:
                nodeid = getattr(test_result, "nodeid", None)
                if nodeid:
                    if nodeid not in test_run_counts:
                        test_run_counts[nodeid] = 0
                    test_run_counts[nodeid] += 1

        # Get the top N most frequently run tests
        top_tests = sorted(test_run_counts.items(), key=lambda x: x[1], reverse=True)[:limit]

        # Calculate stability for each test on each date
        test_stability_timeline = {}
        for nodeid, _ in top_tests:
            test_stability_timeline[nodeid] = {}
            for date in sorted_dates:
                # Get all results for this test on this date
                date_results = []
                for session in date_sessions[date]:
                    for test_result in session.test_results:
                        if getattr(test_result, "nodeid", None) == nodeid:
                            outcome = getattr(test_result, "outcome", None)
                            # Handle both string and enum outcomes
                            if hasattr(outcome, "value"):
                                # It's an enum
                                result = outcome.value
                            else:
                                # It's a string
                                result = str(outcome).upper()
                            date_results.append(result)

                # Calculate stability metrics if we have results
                if date_results:
                    # Count outcomes
                    outcome_counts = {}
                    for result in date_results:
                        if result not in outcome_counts:
                            outcome_counts[result] = 0
                        outcome_counts[result] += 1

                    # Calculate stability score (percentage of consistent results)
                    if date_results:
                        most_common_count = max(outcome_counts.values())
                        stability_score = most_common_count / len(date_results)

                        # Store metrics
                        test_stability_timeline[nodeid][date] = {
                            "total_runs": len(date_results),
                            "outcome_counts": outcome_counts,
                            "stability_score": stability_score,
                        }

        # Calculate trends for each test
        trends = {}
        for nodeid, date_data in test_stability_timeline.items():
            # Track stability scores for trend calculation
            stability_scores = []

            # Add stability score for each date
            for date in sorted_dates:
                if date in date_data:
                    stability_scores.append(date_data[date]["stability_score"])
                else:
                    stability_scores.append(None)

            # Calculate trend
            valid_scores = [s for s in stability_scores if s is not None]
            if len(valid_scores) >= 2:
                # Simple trend: compare first and last valid scores
                first_score = valid_scores[0]
                last_score = valid_scores[-1]

                if last_score > first_score + 0.1:
                    trend_direction = "improving"
                    trend_value = last_score - first_score
                elif last_score < first_score - 0.1:
                    trend_direction = "declining"
                    trend_value = first_score - last_score
                else:
                    trend_direction = "stable"
                    trend_value = 0

                trends[nodeid] = {
                    "direction": trend_direction,
                    "value": trend_value,
                    "first_score": first_score,
                    "last_score": last_score,
                }
            else:
                trends[nodeid] = {"direction": "insufficient_data", "value": 0}

        return {
            "timeline": test_stability_timeline,
            "dates": sorted_dates,
            "trends": trends,
            "error": None,
        }

    def error_patterns(self) -> Dict[str, Any]:
        """Analyze common error patterns across test failures.

        Identifies recurring error patterns in test failures and maps them to affected tests.
        This helps identify common failure modes and potentially unstable tests that
        fail with multiple different error patterns.

        Returns:
            Dict containing:
            - patterns: List of dicts with pattern, count, and affected_tests
            - multi_error_tests: List of tests with multiple error patterns
            - failure_details: Detailed information about each test failure
        """
        sessions = self._sessions
        if not sessions:
            return {"patterns": [], "multi_error_tests": [], "failure_details": []}

        # Track error patterns and their occurrences
        error_patterns = {}  # Maps patterns to lists of affected tests
        error_counts = {}  # Maps patterns to occurrence counts
        test_to_error_map = {}  # Maps tests to their error patterns
        failure_details = []  # Detailed information about each failure

        # Common Python exceptions to look for
        exception_types = [
            "AssertionError",
            "ValueError",
            "TypeError",
            "KeyError",
            "IndexError",
            "AttributeError",
            "ImportError",
            "RuntimeError",
            "NameError",
            "SyntaxError",
            "FileNotFoundError",
            "ZeroDivisionError",
            "PermissionError",
            "OSError",
            "IOError",
        ]

        # Analyze each session for test failures
        for session in sessions:
            for test_result in session.test_results:
                nodeid = getattr(test_result, "nodeid", None)
                outcome = getattr(test_result, "outcome", None)

                # Check if the test failed
                is_failed = False
                if hasattr(outcome, "value"):
                    is_failed = outcome.value in ["failed", "error", "FAILED", "ERROR"]
                else:
                    is_failed = str(outcome).upper() in ["FAILED", "ERROR"]

                if is_failed and nodeid:
                    # Get the error message
                    error_msg = getattr(test_result, "longreprtext", "")

                    # Store failure details for debugging
                    failure_details.append(
                        {
                            "nodeid": nodeid,
                            "error_msg": error_msg,
                            "session_id": getattr(session, "session_id", "unknown"),
                        }
                    )

                    if error_msg:
                        # Extract meaningful error patterns from the error message
                        # First, identify the error type
                        error_type = "Unknown Error"
                        error_detail = ""

                        # Find the exception type in the error message
                        for exc_type in exception_types:
                            if exc_type in error_msg:
                                error_type = exc_type
                                # Try to extract the specific error detail
                                lines = error_msg.split("\n")
                                for line in lines:
                                    if exc_type in line:
                                        # Extract the part after the exception type
                                        parts = line.split(exc_type + ":", 1)
                                        if len(parts) > 1:
                                            error_detail = parts[1].strip()
                                            break
                                break

                        # If we couldn't extract a specific detail, use the first non-empty line
                        if not error_detail and error_msg:
                            for line in error_msg.split("\n"):
                                if line.strip() and not line.startswith('  File "'):
                                    error_detail = line.strip()
                                    break

                        # Create a meaningful pattern that combines error type and detail
                        pattern = f"{error_type}: {error_detail}" if error_detail else error_type

                        # Truncate very long patterns
                        if len(pattern) > 100:
                            pattern = pattern[:97] + "..."

                        # Count occurrences of each error pattern
                        if pattern not in error_patterns:
                            error_patterns[pattern] = []
                            error_counts[pattern] = 0

                        error_patterns[pattern].append(nodeid)
                        error_counts[pattern] += 1

                        # Map tests to their error patterns
                        if nodeid not in test_to_error_map:
                            test_to_error_map[nodeid] = []

                        if pattern not in test_to_error_map[nodeid]:
                            test_to_error_map[nodeid].append(pattern)

        # Sort error patterns by frequency
        sorted_patterns = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)

        # Format the results
        patterns_result = [
            {
                "pattern": pattern,
                "count": count,
                "affected_tests": list(set(error_patterns[pattern])),
            }
            for pattern, count in sorted_patterns
        ]

        # Find tests with multiple error patterns (potentially unreliable or unstable)
        multi_error_tests = [
            {"test": test, "patterns": patterns, "pattern_count": len(patterns)}
            for test, patterns in test_to_error_map.items()
            if len(patterns) > 1
        ]

        # Sort by number of patterns (most patterns first)
        multi_error_tests.sort(key=lambda x: x["pattern_count"], reverse=True)

        return {
            "patterns": patterns_result,
            "multi_error_tests": multi_error_tests,
            "failure_details": failure_details,
        }

    def dependency_graph(self) -> Dict[str, Any]:
        """Analyze which tests tend to fail together to identify potential dependencies.

        This method identifies tests that frequently fail together and determines
        potential dependency relationships between them. It can help uncover hidden
        dependencies in the test suite that might not be obvious from the code.

        Returns:
            Dict containing:
            - dependencies: List of dicts with test pairs and their dependency metrics
            - test_failures: Dict mapping test nodeids to their failure data
        """
        sessions = self._sessions
        if not sessions:
            return {"dependencies": [], "test_failures": {}}

        # Create a matrix of test co-failures
        test_failures = {}
        for session in sessions:
            # Get all failed tests in this session
            session_failures = []
            for test in session.test_results:
                nodeid = getattr(test, "nodeid", None)
                outcome = getattr(test, "outcome", None)

                # Check if the test failed
                is_failed = False
                if hasattr(outcome, "value"):
                    # It's an enum
                    is_failed = outcome.value == "FAILED"
                else:
                    # It's a string
                    is_failed = str(outcome).upper() == "FAILED"

                if is_failed and nodeid:
                    session_failures.append(nodeid)

                    # Track individual test failure counts
                    if nodeid not in test_failures:
                        test_failures[nodeid] = {"count": 0, "co_failures": {}}
                    test_failures[nodeid]["count"] += 1

            # Record co-failures for each pair of failed tests
            for i, test1 in enumerate(session_failures):
                for test2 in session_failures[i + 1 :]:
                    if test1 != test2:
                        # Update co-failure count for test1
                        if test2 not in test_failures[test1]["co_failures"]:
                            test_failures[test1]["co_failures"][test2] = 0
                        test_failures[test1]["co_failures"][test2] += 1

                        # Update co-failure count for test2
                        if test1 not in test_failures[test2]["co_failures"]:
                            test_failures[test2]["co_failures"][test1] = 0
                        test_failures[test2]["co_failures"][test1] += 1

        # Identify significant dependencies
        dependencies = []
        for test_id, data in test_failures.items():
            total_failures = data["count"]
            if total_failures < 3:  # Ignore tests with too few failures
                continue

            # Find tests that fail together with this test more than 70% of the time
            for co_test, co_count in data["co_failures"].items():
                co_test_total = test_failures.get(co_test, {}).get("count", 0)
                if co_test_total < 3:  # Ignore tests with too few failures
                    continue

                # Calculate dependency metrics
                pct_a_with_b = co_count / total_failures
                pct_b_with_a = co_count / co_test_total

                # Only consider strong dependencies
                if pct_a_with_b > 0.7 or pct_b_with_a > 0.7:
                    # Determine dependency direction
                    if pct_a_with_b > pct_b_with_a + 0.2:
                        # test_id likely depends on co_test
                        direction = f"{test_id} → {co_test}"
                        strength = pct_a_with_b
                        interpretation = f"{test_id.split('::')[-1]} fails when {co_test.split('::')[-1]} fails"
                    elif pct_b_with_a > pct_a_with_b + 0.2:
                        # co_test likely depends on test_id
                        direction = f"{co_test} → {test_id}"
                        strength = pct_b_with_a
                        interpretation = f"{co_test.split('::')[-1]} fails when {test_id.split('::')[-1]} fails"
                    else:
                        # Bidirectional dependency
                        direction = f"{test_id} ↔ {co_test}"
                        strength = (pct_a_with_b + pct_b_with_a) / 2
                        interpretation = f"{test_id.split('::')[-1]} and {co_test.split('::')[-1]} fail together"

                    dependencies.append(
                        {
                            "test1": test_id,
                            "test2": co_test,
                            "direction": direction,
                            "strength": strength,
                            "interpretation": interpretation,
                            "co_failure_count": co_count,
                        }
                    )

        # Sort dependencies by strength
        dependencies.sort(key=lambda x: x["strength"], reverse=True)

        return {"dependencies": dependencies, "test_failures": test_failures}

    def test_health_score(self) -> Dict[str, Any]:
        """Calculate a composite health score for tests.

        The health score is a composite metric from 0-100 that takes into account:
        - Pass rate (50% weight)
        - Reliability (20% weight)
        - Duration stability (15% weight)
        - Failure pattern (15% weight)

        Returns:
            Dict containing:
            - health_score: Overall health score (0-100)
            - health_factors: Dict of individual component scores
            - reliability_index: Reliability index (0-100)
            - consistently_failing: List of consistently failing tests
        """
        sessions = self._sessions
        if not sessions:
            return {
                "health_score": 0,
                "health_factors": {},
                "reliability_index": 0,
                "consistently_failing": [],
            }

        # Calculate pass rate
        total_tests = 0
        passed_tests = 0
        for session in sessions:
            for test_result in session.test_results:
                total_tests += 1
                if test_result.outcome == "passed":
                    passed_tests += 1

        pass_rate = passed_tests / total_tests if total_tests > 0 else 0

        # Get unreliable tests
        unreliable_tests_data = self.unreliable_tests()
        unreliable_tests = unreliable_tests_data["unreliable_tests"]

        # Get slowest tests for duration stability calculation
        slowest_tests_data = self.slowest_tests()
        slowest_tests = slowest_tests_data["slowest_tests"]

        # Find consistently failing tests
        test_results_by_nodeid = {}
        for session in sessions:
            for test_result in session.test_results:
                nodeid = getattr(test_result, "nodeid", None)
                if not nodeid:
                    continue
                if nodeid not in test_results_by_nodeid:
                    test_results_by_nodeid[nodeid] = []
                test_results_by_nodeid[nodeid].append(test_result)

        consistently_failing = []
        for nodeid, results in test_results_by_nodeid.items():
            if len(results) >= 3:  # Only consider tests with at least 3 runs
                failure_count = sum(1 for r in results if r.outcome != "passed")
                failure_rate = failure_count / len(results)
                if failure_rate > 0.9:  # More than 90% failure rate
                    consistently_failing.append(nodeid)

        # Calculate health factors
        health_factors = {
            "pass_rate": pass_rate * 50,  # 50% weight to pass rate
            "reliability": (1 - len(unreliable_tests) / max(1, total_tests)) * 20,  # 20% weight to reliability
            "duration_stability": 15,  # Default value, will be calculated below
            "failure_pattern": 15,  # Default value, will be calculated below
        }

        # Calculate duration stability component (lower variance = higher score)
        if slowest_tests:
            durations = [duration for _, duration in slowest_tests]
            if durations:
                mean_duration = sum(durations) / len(durations)
                variance = sum((d - mean_duration) ** 2 for d in durations) / len(durations)
                # Normalize: lower variance = higher score (max 15)
                coefficient = 0.1  # Adjust based on typical variance values
                health_factors["duration_stability"] = 15 * (1 / (1 + coefficient * variance))

        # Calculate failure pattern component
        if total_tests > 0:
            # Lower ratio of consistently failing tests = better score
            consistent_failure_ratio = len(consistently_failing) / max(1, total_tests)
            health_factors["failure_pattern"] = 15 * (1 - consistent_failure_ratio)

        # Calculate overall health score
        health_score = sum(health_factors.values())
        health_score = min(100, max(0, health_score))  # Clamp between 0-100

        # Calculate reliability index
        environment_consistency = 0.8  # Default value if we can't calculate from data
        test_consistency = 0.8  # Default value if we can't calculate from data

        # Get environment consistency from SessionInsights
        from pytest_insight.core.insights import Insights

        insights = Insights()
        env_impact = insights.sessions.environment_impact()
        environment_consistency = env_impact["consistency"]

        # Calculate test result consistency (how consistently individual tests pass/fail)
        if test_results_by_nodeid:
            consistency_scores = []
            for nodeid, results in test_results_by_nodeid.items():
                if results:  # Ensure we have outcomes to analyze
                    # Calculate the proportion of the dominant outcome
                    outcomes = [getattr(r, "outcome", "unknown") for r in results]
                    outcome_counts = {}
                    for outcome in outcomes:
                        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1

                    if outcome_counts:  # Make sure we have outcomes
                        dominant_outcome_count = max(outcome_counts.values())
                        consistency = dominant_outcome_count / len(outcomes)
                        consistency_scores.append(consistency)

            if consistency_scores:
                test_consistency = sum(consistency_scores) / len(consistency_scores)

        # Combine factors for reliability index (0-100)
        reliability_index = (
            pass_rate * 0.4  # 40% weight to pass rate
            + (1 - len(unreliable_tests) / max(1, total_tests)) * 0.3  # 30% weight to reliability
            + environment_consistency * 0.15  # 15% weight to environment consistency
            + test_consistency * 0.15  # 15% weight to test result consistency
        ) * 100
        reliability_index = min(100, max(0, reliability_index))

        return {
            "health_score": health_score,
            "health_factors": health_factors,
            "reliability_index": reliability_index,
            "consistently_failing": consistently_failing,
        }

    def correlation_analysis(self) -> Dict[str, Any]:
        """Analyze correlations between test outcomes.

        This method identifies tests that tend to have correlated outcomes,
        which can help identify hidden dependencies or shared resources.

        Returns:
            Dict containing:
            - correlations: List of dicts with test pairs and their correlation coefficients
            - test_matrix: Dict mapping test nodeids to their outcome vectors
        """
        sessions = self._sessions
        if not sessions:
            return {"correlations": [], "test_matrix": {}}

        # Create a matrix of test outcomes across sessions
        test_matrix = {}
        session_ids = []

        # First pass: identify all tests and sessions
        for i, session in enumerate(sessions):
            session_ids.append(session.session_id)
            for test_result in session.test_results:
                nodeid = getattr(test_result, "nodeid", None)
                if nodeid and nodeid not in test_matrix:
                    test_matrix[nodeid] = {"outcomes": [None] * len(sessions)}

        # Second pass: fill in the outcome matrix
        for i, session in enumerate(sessions):
            for test_result in session.test_results:
                nodeid = getattr(test_result, "nodeid", None)
                if nodeid:
                    # Convert outcome to a numeric value for correlation calculation
                    outcome = getattr(test_result, "outcome", None)
                    outcome_value = 1 if outcome == "passed" else 0
                    test_matrix[nodeid]["outcomes"][i] = outcome_value

        # Only include tests that appear in at least 3 sessions
        valid_tests = {}
        for nodeid, data in test_matrix.items():
            outcomes = data["outcomes"]
            valid_outcomes = [o for o in outcomes if o is not None]
            if len(valid_outcomes) >= 3:
                valid_tests[nodeid] = valid_outcomes

        # Calculate correlation coefficients between test pairs
        correlations = []
        test_ids = list(valid_tests.keys())
        for i, test1 in enumerate(test_ids):
            for test2 in test_ids[i + 1 :]:
                # Get outcome vectors for both tests
                outcomes1 = valid_tests[test1]
                outcomes2 = valid_tests[test2]

                # We need to align the vectors to only include sessions where both tests ran
                # For simplicity, we'll just use sessions where both tests have outcomes
                min_length = min(len(outcomes1), len(outcomes2))
                if min_length < 3:
                    continue  # Skip if we don't have enough common sessions

                # Calculate correlation coefficient
                try:
                    # Calculate means
                    mean1 = sum(outcomes1[:min_length]) / min_length
                    mean2 = sum(outcomes2[:min_length]) / min_length

                    # Calculate variances and covariance
                    var1 = sum((x - mean1) ** 2 for x in outcomes1[:min_length]) / min_length
                    var2 = sum((x - mean2) ** 2 for x in outcomes2[:min_length]) / min_length
                    cov = sum((outcomes1[i] - mean1) * (outcomes2[i] - mean2) for i in range(min_length)) / min_length

                    # Calculate correlation coefficient
                    if var1 > 0 and var2 > 0:
                        corr = cov / (var1**0.5 * var2**0.5)
                    else:
                        corr = 0  # No variance in at least one test
                except Exception:
                    corr = 0  # Error in calculation

                # Only include significant correlations
                if abs(corr) > 0.5:
                    # Get short test names for display
                    test1_short = test1.split("::")[-1] if "::" in test1 else test1
                    test2_short = test2.split("::")[-1] if "::" in test2 else test2

                    correlations.append(
                        {
                            "test1": test1,
                            "test2": test2,
                            "test1_short": test1_short,
                            "test2_short": test2_short,
                            "correlation": corr,
                            "relationship": "positive" if corr > 0 else "negative",
                            "strength": abs(corr),
                        }
                    )

        # Sort by correlation strength
        correlations.sort(key=lambda x: abs(x["correlation"]), reverse=True)

        return {"correlations": correlations, "test_matrix": test_matrix}

    def seasonal_patterns(self) -> Dict[str, Any]:
        """Analyze seasonal patterns in test failures.

        This method identifies tests that tend to fail at specific times of day
        or days of the week, which can help identify time-dependent issues.

        Returns:
            Dict containing:
            - patterns: List of dicts with test nodeids and their seasonal patterns
            - day_names: List of day names for reference
        """
        sessions = self._sessions
        if not sessions:
            return {
                "patterns": [],
                "day_names": [
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                ],
            }

        # Track timestamps of test failures
        test_timestamps = defaultdict(list)
        for session in sessions:
            for test_result in session.test_results:
                nodeid = getattr(test_result, "nodeid", None)
                if not nodeid:
                    continue

                # Check if the test failed
                outcome = getattr(test_result, "outcome", None)
                is_failed = False
                if hasattr(outcome, "value"):
                    is_failed = outcome.value in ["failed", "error", "FAILED", "ERROR"]
                else:
                    is_failed = str(outcome).upper() in ["FAILED", "ERROR"]

                if is_failed:
                    # Store the timestamp of this failure
                    start_time = getattr(test_result, "start_time", None)
                    if start_time:
                        test_timestamps[nodeid].append(start_time)

        # Analyze patterns for tests with sufficient data
        seasonal_patterns = []
        for test_id, timestamps in test_timestamps.items():
            if len(timestamps) < 3:
                continue

            # Sort timestamps chronologically
            timestamps.sort()

            # Check for time-of-day patterns
            hour_distribution = [0] * 24
            for timestamp in timestamps:
                hour = timestamp.hour
                hour_distribution[hour] += 1

            total_failures = len(timestamps)

            # Calculate hourly distribution as percentages
            [count / total_failures for count in hour_distribution]

            # Check for peaks (hours with significantly more failures)
            avg_failures_per_hour = total_failures / 24
            peak_hours = []
            for hour, count in enumerate(hour_distribution):
                if (
                    count > 2 * avg_failures_per_hour and count >= 2
                ):  # At least twice the average and at least 2 occurrences
                    peak_hours.append((hour, count, count / total_failures))

            # Check for day-of-week patterns
            day_distribution = [0] * 7  # Monday to Sunday
            for timestamp in timestamps:
                day = timestamp.weekday()
                day_distribution[day] += 1

            # Calculate day distribution as percentages
            [count / total_failures for count in day_distribution]

            # Check for peak days
            avg_failures_per_day = total_failures / 7
            peak_days = []
            for day, count in enumerate(day_distribution):
                if (
                    count > 1.5 * avg_failures_per_day and count >= 2
                ):  # At least 1.5x the average and at least 2 occurrences
                    peak_days.append((day, count, count / total_failures))

            # Only include tests with significant patterns
            if peak_hours or peak_days:
                test_short = test_id.split("::")[-1] if "::" in test_id else test_id

                seasonal_patterns.append(
                    {
                        "test_id": test_id,
                        "test_short": test_short,
                        "total_failures": total_failures,
                        "peak_hours": peak_hours,
                        "peak_days": peak_days,
                        "hour_distribution": hour_distribution,
                        "day_distribution": day_distribution,
                    }
                )

        # Sort by total failures
        seasonal_patterns.sort(key=lambda x: x["total_failures"], reverse=True)

        # Map day numbers to names for reference
        day_names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

        return {"patterns": seasonal_patterns, "day_names": day_names}


class SessionInsights:
    """Session-level insights and analytics.

    Analyzes metrics and health at the session level.
    """

    def __init__(self, analysis_or_sessions):
        """Initialize with an Analysis instance or a list of TestSession objects.

        Args:
            analysis_or_sessions: Analysis instance OR list of TestSession objects
        """
        from pytest_insight.core.analysis import Analysis

        # Defensive: allow for mocks in tests
        analysis_type = Analysis
        if not isinstance(analysis_type, type):
            # If Analysis is mocked (MagicMock), isinstance() will fail; fallback to name check
            if hasattr(analysis_or_sessions, "__class__") and analysis_or_sessions.__class__.__name__ == "MagicMock":
                self.analysis = analysis_or_sessions
                self._sessions = getattr(analysis_or_sessions, "_sessions", [])
                return
            else:
                raise TypeError("SessionInsights expects an Analysis instance or a list of TestSession objects.")

        if isinstance(analysis_or_sessions, analysis_type):
            self.analysis = analysis_or_sessions
            self._sessions = analysis_or_sessions._sessions
        elif isinstance(analysis_or_sessions, list) and all(hasattr(s, "test_results") for s in analysis_or_sessions):
            self.analysis = None
            self._sessions = analysis_or_sessions
        else:
            raise TypeError("SessionInsights expects an Analysis instance or a list of TestSession objects.")

    def _get_sessions(self, days: Optional[int] = None):
        """Delegate to analysis.sessions._get_sessions for compatibility, or operate on direct session list."""
        if self.analysis is not None:
            return self.analysis.sessions._get_sessions(days)
        # Fallback: just return all sessions (optionally filter by days)
        if days is None:
            return self._sessions
        # Filter by date if possible (assumes sessions have .start_time)
        from datetime import datetime, timedelta

        cutoff = datetime.now() - timedelta(days=days)
        return [s for s in self._sessions if getattr(s, "start_time", None) and s.start_time >= cutoff]

    def session_metrics(self, days: Optional[int] = None) -> Dict[str, Any]:
        """Calculate key session metrics (robust for both Analysis and direct list modes)."""
        if self.analysis is not None:
            try:
                # Try the new sessions attribute first
                return self.analysis.sessions.test_metrics(days=days)
            except AttributeError:
                # Fall back to the old session_analysis attribute for backward compatibility
                try:
                    return self.analysis.session_analysis.test_metrics(days=days)
                except AttributeError:
                    # If neither works, return a default structure
                    return {
                        "total_sessions": (len(self.analysis._sessions) if self.analysis._sessions else 0),
                        "pass_rate": 0.0,
                        "avg_tests_per_session": 0.0,
                        "failure_rate": 0.0,
                        "warning_rate": 0.0,
                        "avg_duration": 0.0,
                    }
        # Direct calculation from self._sessions
        sessions = self._get_sessions(days)
        total_sessions = len(sessions)
        if not total_sessions:
            return {
                "total_sessions": 0,
                "pass_rate": 0.0,
                "avg_tests_per_session": 0.0,
                "failure_rate": 0.0,
                "warning_rate": 0.0,
                "avg_duration": 0.0,
            }
        total_tests = sum(len(getattr(s, "test_results", [])) for s in sessions)
        passed = sum(
            sum(
                1
                for t in getattr(s, "test_results", [])
                if getattr(t, "outcome", None) and getattr(t, "outcome").name == "PASSED"
            )
            for s in sessions
        )
        failed = sum(
            sum(
                1
                for t in getattr(s, "test_results", [])
                if getattr(t, "outcome", None) and getattr(t, "outcome").name == "FAILED"
            )
            for s in sessions
        )
        warned = sum(
            sum(
                1
                for t in getattr(s, "test_results", [])
                if getattr(t, "outcome", None) and getattr(t, "outcome").name == "WARNING"
            )
            for s in sessions
        )
        avg_tests_per_session = total_tests / total_sessions if total_sessions else 0.0
        pass_rate = passed / total_tests if total_tests else 0.0
        failure_rate = failed / total_tests if total_tests else 0.0
        warning_rate = warned / total_tests if total_tests else 0.0
        avg_duration = sum(getattr(s, "duration", 0.0) for s in sessions) / total_sessions if total_sessions else 0.0
        return {
            "total_sessions": total_sessions,
            "pass_rate": pass_rate,
            "avg_tests_per_session": avg_tests_per_session,
            "failure_rate": failure_rate,
            "warning_rate": warning_rate,
            "avg_duration": avg_duration,
        }

    def health_metrics(self, days: Optional[int] = None) -> Dict[str, Any]:
        """Calculate comprehensive test health metrics.

        Provides a holistic view of test suite health by combining multiple metrics:
        - Top failing tests (failure clustering)
        - Regression rate
        - Longest running tests
        - Test suite duration trends

        Args:
            days: Optional number of days to look back

        Returns:
            Dict containing all health metrics
        """
        # Get base metrics
        metrics = self.session_metrics(days=days)

        if self.analysis is not None and hasattr(self.analysis, "session_analysis"):
            # Add top failing tests
            top_failing = self.analysis.session_analysis.top_failing_tests(days=days)
            metrics["top_failing_tests"] = top_failing

            # Add regression rate
            regression = self.analysis.session_analysis.regression_rate(days=days)
            metrics["regression"] = regression

            # Add longest running tests
            longest_tests = self.analysis.session_analysis.longest_running_tests(days=days)
            metrics["longest_tests"] = longest_tests

            # Add test suite duration trend
            duration_trend = self.analysis.session_analysis.test_suite_duration_trend(days=days)
            metrics["duration_trend"] = duration_trend
        else:
            # Fallback: compute what we can from self._sessions
            # Top failing tests
            try:
                from pytest_insight.core.health_metrics import (
                    top_failing_tests as health_top_failing_tests,
                )

                metrics["top_failing_tests"] = health_top_failing_tests(self, days=days, limit=10)
            except ImportError:
                metrics["top_failing_tests"] = {"top_failing": [], "total_failures": 0}
            # Regression rate, longest tests, duration trend: leave empty or implement as needed
            metrics["regression"] = None
            metrics["longest_tests"] = None
            metrics["duration_trend"] = None

        return metrics

    def top_failing_tests(self, days=None, limit=10):
        """Delegate to the underlying session_analysis or health metrics implementation."""
        if (
            self.analysis is not None
            and hasattr(self.analysis, "session_analysis")
            and hasattr(self.analysis.session_analysis, "top_failing_tests")
        ):
            return self.analysis.session_analysis.top_failing_tests(days=days, limit=limit)
        # Fallback: if health_metrics module is available, use it
        try:
            from pytest_insight.core.health_metrics import (
                top_failing_tests as health_top_failing_tests,
            )

            return health_top_failing_tests(self, days=days, limit=limit)
        except ImportError:
            return {"top_failing": [], "total_failures": 0}

    def environment_impact(self) -> Dict[str, Any]:
        """Analyze how different environments affect test results.

        This method examines how test pass rates vary across different environments,
        which can help identify environment-specific issues.

        Returns:
            Dict containing:
            - environments: Dict mapping environment names to their metrics
            - pass_rates: Dict mapping environment names to their average pass rates
            - consistency: Overall environment consistency score (0-1)
        """
        sessions = self._sessions
        if not sessions:
            return {"environments": {}, "pass_rates": {}, "consistency": 0}

        # Collect environment information from session tags
        environments = {}
        for session in sessions:
            env = session.session_tags.get("environment", "unknown")
            if env not in environments:
                environments[env] = {"pass_rates": [], "sessions": []}

            # Add session to the environment
            environments[env]["sessions"].append(session.session_id)

            # Calculate pass rate for this session
            session_results = session.test_results
            if session_results:
                session_pass_rate = sum(1 for t in session_results if t.outcome == "passed") / len(session_results)
                environments[env]["pass_rates"].append(session_pass_rate)

        # Calculate average pass rate for each environment
        env_pass_rates = {}
        for env, data in environments.items():
            if data["pass_rates"]:
                env_pass_rates[env] = sum(data["pass_rates"]) / len(data["pass_rates"])
                # Add the average pass rate to the environment data
                environments[env]["avg_pass_rate"] = env_pass_rates[env]
            else:
                environments[env]["avg_pass_rate"] = 0

        # Calculate environment consistency (how consistent results are across environments)
        consistency = 0
        if len(env_pass_rates) > 1:
            env_pass_rate_values = list(env_pass_rates.values())
            mean_env_pass_rate = sum(env_pass_rate_values) / len(env_pass_rate_values)
            env_variance = sum((r - mean_env_pass_rate) ** 2 for r in env_pass_rate_values) / len(env_pass_rate_values)
            # Lower variance = higher consistency
            consistency = 1 / (1 + 10 * env_variance)  # Scale factor of 10 for better distribution
            consistency = min(1, max(0, consistency))  # Clamp between 0 and 1

        return {
            "environments": environments,
            "pass_rates": env_pass_rates,
            "consistency": consistency,
        }

    def test_health_score(self) -> Dict[str, Any]:
        """Calculate a composite health score for tests.

        The health score is a composite metric from 0-100 that takes into account:
        - Pass rate (50% weight)
        - Reliability (20% weight)
        - Duration stability (15% weight)
        - Failure pattern (15% weight)

        Returns:
            Dict containing:
            - health_score: Overall health score (0-100)
            - health_factors: Dict of individual component scores
            - reliability_index: Reliability index (0-100)
            - consistently_failing: List of consistently failing tests
        """
        # Delegate to TestInsights
        return self.tests.test_health_score()


class TrendInsights:
    """Trend insights and analytics.

    Identifies trends and patterns over time.
    """

    def __init__(self, analysis):
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

        return {
            "daily_durations": daily_durations,
            "trend_percentage": trend_percentage,
            "increasing": increasing,
        }

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
            return {
                "daily_failure_rates": [],
                "trend_percentage": 0.0,
                "improving": False,
            }

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
            return {
                "early_period": {},
                "late_period": {},
                "health_difference": 0.0,
                "improving": False,
            }

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
        unreliable_report = insights.tests.unreliable_tests()

        # With filtering
        filtered_insights = insights.with_query(lambda q: q.in_last_days(30))
        trend_report = filtered_insights.trends.duration_trends()

        # Combining with Analysis
        analysis = Analysis()
        insights = Insights(analysis=analysis)
        combined_report = {
            "health": insights.summary_report(),
            "trends": insights.trends.duration_trends()
        }
    """

    def __init__(self, analysis: Optional["Analysis"] = None, profile_name: Optional[str] = None):
        """Initialize insight components.

        Args:
            analysis: Optional Analysis instance to use. If None, creates a new one.
            profile_name: Optional profile name to use

        Returns:
            Insights instance
        """
        # Store the profile name for later use
        self._profile_name = profile_name

        # Import Analysis here to avoid circular imports
        if analysis is None:
            from pytest_insight.core.analysis import Analysis

            storage = get_storage_instance(profile_name=profile_name)
            self.analysis = Analysis(storage=storage)
        else:
            self.analysis = analysis

        # Initialize insight components
        self.tests = TestInsights(self.analysis._sessions)
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
        return Insights(analysis=filtered_analysis, profile_name=self._profile_name)

    def with_profile(self, profile_name: str) -> "Insights":
        """Set the storage profile for insights.

        Args:
            profile_name: Name of the profile to use

        Returns:
            Insights instance for chaining

        Example:
            insights.with_profile("production").summary_report()
        """
        # Store the new profile name
        self._profile_name = profile_name

        # Create a new storage with the profile
        storage = get_storage_instance(profile_name=profile_name)

        # Update the analysis with the new storage
        # Import Analysis here to avoid circular imports
        from pytest_insight.core.analysis import Analysis

        self.analysis = Analysis(storage=storage)

        # Reinitialize insight components with the updated analysis
        self.tests = TestInsights(self.analysis._sessions)
        self.sessions = SessionInsights(self.analysis)
        self.trends = TrendInsights(self.analysis)

        return self

    def for_profile(self, profile_name: str) -> "Insights":
        """Create a new Insights instance for a specific profile.

        Args:
            profile_name: Name of the profile to use

        Returns:
            New Insights instance configured with the specified profile
        """
        from pytest_insight.core.analysis import Analysis

        storage = get_storage_instance(profile_name=profile_name)
        self.analysis = Analysis(storage=storage)

        # Reinitialize insight components with the updated analysis
        self.tests = TestInsights(self.analysis._sessions)
        self.sessions = SessionInsights(self.analysis)
        self.trends = TrendInsights(self.analysis)

        return self

    def get_pass_rate_trend(self, last_n: int = 7) -> list:
        """
        Return the pass rate (%) for the last N sessions (most recent last).
        """
        # Get sessions sorted by session_start_time (oldest to newest)
        sessions = sorted(self.analysis._sessions, key=lambda s: getattr(s, "session_start_time", None))
        if not sessions:
            return []

        # Take the last N sessions
        recent_sessions = sessions[-last_n:]
        pass_rates = []
        for session in recent_sessions:
            test_results = getattr(session, "test_results", [])
            total = len(test_results)
            passed = sum(
                1 for t in test_results if getattr(t, "outcome", None) and getattr(t, "outcome").name == "PASSED"
            )
            rate = (passed / total * 100) if total else 0.0
            pass_rates.append(round(rate, 2))

        return pass_rates

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
            "unreliable_tests": self.tests.unreliable_tests(),
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

    def console_summary(self) -> str:
        """Generate a summary of insights for console display.

        Returns:
            String containing the most important metrics and insights
            formatted for easy display in a terminal.
        """
        # Import colorama for terminal colors
        try:
            colorama.init()

            # Define color constants
            GREEN = Fore.GREEN
            RED = Fore.RED
            YELLOW = Fore.YELLOW
            CYAN = Fore.CYAN
            MAGENTA = Style.BRIGHT
            BRIGHT = Style.BRIGHT
            RESET = Style.RESET_ALL

        except ImportError:
            # Define empty color constants if colorama is not available
            GREEN = RED = YELLOW = CYAN = MAGENTA = BRIGHT = RESET = ""

        # METADATA HEADER
        meta_lines = []
        profile_name = getattr(self, "_profile_name", None) or getattr(
            getattr(self, "analysis", None), "_profile_name", None
        )
        meta_lines.append(f"{BRIGHT}{CYAN}Pytest Insight Summary{RESET}")
        if profile_name:
            meta_lines.append(f"{BRIGHT}Profile:{RESET} {profile_name}")
        current_session = self.analysis._sessions[-1] if self.analysis._sessions else None
        sut = getattr(current_session, "sut", None) or getattr(self.analysis, "sut", None)
        if sut:
            meta_lines.append(f"{BRIGHT}SUT Name:{RESET} {sut}")
        system_name = getattr(current_session, "testing_system_name", None) or getattr(
            self.analysis, "testing_system_name", None
        )
        if system_name:
            meta_lines.append(f"{BRIGHT}Test System Name:{RESET} {system_name}")
        # Add session start/end/duration if available
        start_time = getattr(current_session, "session_start_time", None)
        end_time = getattr(current_session, "session_stop_time", None)
        session_parts = []
        try:
            start_dt = datetime.fromisoformat(start_time) if isinstance(start_time, str) else start_time
            session_parts.append(f"{BRIGHT}Session Start:{RESET} {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception:
            if start_time:
                session_parts.append(f"{BRIGHT}Session Start:{RESET} {start_time}")
        try:
            end_dt = datetime.fromisoformat(end_time) if isinstance(end_time, str) else end_time
            session_parts.append(f"{BRIGHT}Session End:{RESET} {end_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception:
            if end_time:
                session_parts.append(f"{BRIGHT}Session End:{RESET} {end_time}")
        try:
            if start_dt and end_dt:
                duration = (end_dt - start_dt).total_seconds()
                session_parts.append(f"{BRIGHT}Session Duration:{RESET} {duration:.1f} seconds")
        except Exception:
            pass
        if session_parts:
            meta_lines.append(" | ".join(session_parts))

        # if start_time:
        #     try:
        #         from datetime import datetime
        #         if isinstance(start_time, str):
        #             start_dt = datetime.fromisoformat(start_time)
        #         else:
        #             start_dt = start_time
        #         meta_lines.append(f"{BRIGHT}Session Start:{RESET} {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        #     except Exception:
        #         meta_lines.append(f"{BRIGHT}Session Start:{RESET} {start_time}")
        # if end_time:
        #     try:
        #         from datetime import datetime
        #         if isinstance(end_time, str):
        #             end_dt = datetime.fromisoformat(end_time)
        #         else:
        #             end_dt = end_time
        #         meta_lines.append(f"{BRIGHT}Session End:{RESET} {end_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        #     except Exception:
        #         meta_lines.append(f"{BRIGHT}Session End:{RESET} {end_time}")
        # # Duration
        # if start_time and end_time:
        #     try:
        #         from datetime import datetime
        #         if isinstance(start_time, str):
        #             start_dt = datetime.fromisoformat(start_time)
        #         else:
        #             start_dt = start_time
        #         if isinstance(end_time, str):
        #             end_dt = datetime.fromisoformat(end_time)
        #         else:
        #             end_dt = end_time
        #         duration = (end_dt - start_dt).total_seconds()
        #         meta_lines.append(f"{BRIGHT}Session Duration:{RESET} {duration:.1f} seconds")
        #     except Exception:
        #         pass
        environment = getattr(current_session, "environment", None)
        if environment:
            meta_lines.append(f"{BRIGHT}Environment:{RESET} {environment}")
        meta_lines.append("")

        # Compose summary lines
        lines = meta_lines

        # SECTION 1: Just This Run (current session)
        lines.append(f"{BRIGHT}{CYAN}Test Insights: This Run{RESET}")
        if current_session:
            # Outcome distribution for this run
            outcomes = {}
            for test in getattr(current_session, "test_results", []):
                name = getattr(test.outcome, "name", str(test.outcome))
                outcomes[name] = outcomes.get(name, 0) + 1
            total = sum(outcomes.values())
            if total:
                lines.append(f"{BRIGHT}Test Outcome Distribution:{RESET}")
                for name, count in outcomes.items():
                    color = GREEN if name in ["PASSED", "XFAILED"] else RED if name in ["FAILED", "ERROR"] else YELLOW
                    pct = 100 * count / total
                    lines.append(f"  {color}{name.capitalize():<8}: {count:>3} ({pct:5.1f}%){RESET}")
            # Slowest tests for this run (sorted by duration)
            test_results = getattr(current_session, "test_results", [])
            slowest = sorted(
                [t for t in test_results if hasattr(t, "duration") and getattr(t, "duration", None) is not None],
                key=lambda t: getattr(t, "duration", 0),
                reverse=True,
            )[:5]
            if slowest:
                lines.append(f"{BRIGHT}{MAGENTA}Slowest Tests (This Run):{RESET}")
                for test in slowest:
                    nodeid = getattr(test, "nodeid", None)
                    dur = getattr(test, "duration", None)
                    if nodeid and dur is not None:
                        lines.append(f"  {MAGENTA}{nodeid}: {float(dur):.2f} seconds{RESET}")

            # Rerun groups for this run (top 5, final outcome FAIL)
            rerun_groups = getattr(current_session, "rerun_test_groups", None)
            if rerun_groups:
                # Filter for groups with reruns and final outcome FAILED
                failed_rerun_groups = [
                    group
                    for group in rerun_groups
                    if len(getattr(group, "tests", [])) > 1
                    and getattr(group, "final_outcome", None)
                    and getattr(group, "final_outcome", None).name == "FAILED"
                ]
                # Sort by rerun count descending, then nodeid
                failed_rerun_groups = sorted(
                    failed_rerun_groups,
                    key=lambda g: (len(getattr(g, "tests", [])) - 1),
                    reverse=True,
                )
                if failed_rerun_groups:
                    lines.append(f"{BRIGHT}{YELLOW}Rerun Test Groups (This Run, Top 5 FAIL):{RESET}")
                    for group in failed_rerun_groups[:5]:
                        nodeid = getattr(group, "nodeid", None)
                        reruns = len(getattr(group, "tests", [])) - 1
                        final_outcome = getattr(group, "final_outcome", None)
                        lines.append(f"  {YELLOW}{nodeid}: {reruns} reruns, final outcome: {str(final_outcome)}{RESET}")
            # Top failing rerun tests for this run
            rerun_failing = {}
            for test in test_results:
                nodeid = getattr(test, "nodeid", None)
                rerun = getattr(test, "rerun", False) or getattr(test, "rerun_count", 0) > 0
                failed = getattr(test, "outcome", None) and getattr(test, "outcome").name == "FAILED"
                if nodeid and rerun and failed:
                    rerun_failing[nodeid] = rerun_failing.get(nodeid, 0) + 1
            if rerun_failing:
                lines.append(f"{BRIGHT}{RED}Top Failing Rerun Tests (This Run):{RESET}")
                for nodeid, count in sorted(rerun_failing.items(), key=lambda x: x[1], reverse=True)[:5]:
                    lines.append(f"  {RED}{nodeid}: {count} rerun failure(s){RESET}")
            # Session Health Score
            try:
                from pytest_insight.core.health_metrics import session_health_score

                session_score = session_health_score(current_session)
                if session_score is not None:
                    lines.append(f"{BRIGHT}{GREEN}Session Health Score:{RESET} {session_score:.2f}/100")
            except ImportError:
                pass

        # SECTION 2: All Runs (historical)
        lines.append(f"\n{BRIGHT}{CYAN}Test Insights: All Runs{RESET}")
        # Use ALL sessions from storage for aggregate stats
        all_sessions = self.analysis.storage.load_sessions() if hasattr(self.analysis, "storage") else []
        all_sessions_insights = SessionInsights(all_sessions)
        # Health Score
        health_report = self.analysis.health_report()
        health_score_data = health_report.get("health_score", {})
        component_scores = health_score_data.get("component_scores", {})
        health_score = health_score_data.get("overall_score", 0)
        recommendations = health_score_data.get("recommendations", [])
        # Trend direction for health score
        trend_direction = None
        trend_pct = None
        if hasattr(self.trends, "health_score_trend"):
            trend_data = self.trends.health_score_trend()
            if isinstance(trend_data, dict):
                trend_direction = trend_data.get("direction")
                trend_pct = trend_data.get("trend_percentage", 0)
        lines.append(
            f"{BRIGHT}Health Score:{RESET} {GREEN if health_score >= 80 else YELLOW if health_score >= 50 else RED}{health_score:.2f}/100{RESET}"
            + (
                f"  {GREEN if trend_direction == 'Improving' else RED if trend_direction == 'Declining' else YELLOW}({trend_direction or 'No trend'}{f' {trend_pct:+.1f}%' if trend_direction else ''}){RESET}"
                if trend_direction
                else ""
            )
        )
        if recommendations:
            lines.append(f"{BRIGHT}Recommendations:{RESET}")
            for rec in recommendations:
                cat = rec.get("category", "").capitalize()
                msg = rec.get("message", "")
                priority = rec.get("priority", "").capitalize()
                color = RED if priority == "High" else YELLOW if priority == "Medium" else GREEN
                # Extract test nodeids from message for bulleting
                if ":" in msg and "," in msg:
                    prefix, tests = msg.split(":", 1)
                    test_list = [t.strip() for t in tests.split(",")]
                    lines.append(f"  {color}• [{cat}] {prefix.strip()} ({priority}){RESET}")
                    for t in test_list[:5]:
                        lines.append(f"    {color}- {t}{RESET}")
                else:
                    lines.append(f"  {color}• [{cat}] {msg} ({priority}){RESET}")
        # Component Scores
        lines.append(f"{BRIGHT}Component Scores:{RESET}")
        lines.append(f"  {GREEN}Stability:   {component_scores.get('stability', 0):.2f}/100{RESET}")
        perf = component_scores.get("performance", 0)
        perf_str = f"{perf:.2f}/100" if perf > 0 else "N/A"
        lines.append(f"  {CYAN}Performance: {perf_str}{RESET}")
        lines.append(f"  {YELLOW}Warnings:    {component_scores.get('warnings', 0):.2f}/100{RESET}")
        lines.append(f"  {RED}Failure Rate:{component_scores.get('failure_rate', 0):.1f}%{RESET}")
        lines.append(f"  {YELLOW}Warning Rate:{component_scores.get('warning_rate', 0):.1f}%{RESET}")
        # Top Failing Tests (historical, top 5)
        top_failing = []
        if hasattr(all_sessions_insights, "top_failing_tests"):
            tf = all_sessions_insights.top_failing_tests()
            if isinstance(tf, dict) and "top_failing" in tf:
                tf_list = tf["top_failing"]
                if isinstance(tf_list, dict):
                    top_failing = list(tf_list.values())
                else:
                    top_failing = list(tf_list) if isinstance(tf_list, (list, tuple)) else []
        elif hasattr(all_sessions_insights, "health_metrics"):
            tf = all_sessions_insights.health_metrics()
            if isinstance(tf, dict):
                tf_list = tf.get("top_failing_tests", [])
                if isinstance(tf_list, dict):
                    top_failing = list(tf_list.values())
                else:
                    top_failing = list(tf_list) if isinstance(tf_list, (list, tuple)) else []
        if top_failing:
            lines.append(f"{BRIGHT}{RED}Top Failing Tests:{RESET}")
            for test in top_failing[:5]:
                if isinstance(test, dict):
                    nodeid = test.get("nodeid")
                    rate = test.get("failure_rate")
                    if nodeid and isinstance(rate, (int, float)):
                        lines.append(f"  {RED}{nodeid}: {float(rate)*100 if rate <= 1 else float(rate):.1f}%{RESET}")
        # Top Failing Rerun Tests (historical, top 5 FAIL, last 10 days)
        try:
            # Limit sessions to last 10 days
            recent_sessions = all_sessions_insights._get_sessions(days=10)
            # Gather all rerun groups with final outcome FAILED
            failed_rerun_groups = []
            for session in recent_sessions:
                rerun_groups = getattr(session, "rerun_test_groups", [])
                for group in rerun_groups:
                    reruns = len(getattr(group, "tests", [])) - 1
                    final_outcome = getattr(group, "final_outcome", None)
                    if reruns > 0 and final_outcome and getattr(final_outcome, "name", str(final_outcome)) == "FAILED":
                        failed_rerun_groups.append((group, reruns, session))
            # Sort by rerun count descending
            failed_rerun_groups = sorted(failed_rerun_groups, key=lambda x: x[1], reverse=True)
            if failed_rerun_groups:
                lines.append(f"{BRIGHT}{YELLOW}Rerun Test Groups (All Sessions, Top 5 FAIL, Last 10 Days):{RESET}")
                for group, reruns, session in failed_rerun_groups[:5]:
                    nodeid = getattr(group, "nodeid", None)
                    final_outcome = getattr(group, "final_outcome", None)
                    session_id = getattr(session, "session_id", "?")
                    lines.append(
                        f"  {YELLOW}{nodeid}: {reruns} reruns, final outcome: {str(final_outcome)}, session: {session_id}{RESET}"
                    )
        except Exception:
            pass
        # Test Outcome Distribution (historical)
        outcome_dist = None
        try:
            outcome_dist = all_sessions_insights.tests.outcome_distribution()
        except Exception:
            pass
        if isinstance(outcome_dist, dict) and "outcomes" in outcome_dist:
            lines.append(f"{BRIGHT}Test Outcome Distribution:{RESET}")
            for outcome, stats in outcome_dist["outcomes"].items():
                name = getattr(outcome, "name", str(outcome))
                pct = stats.get("percentage", 0)
                count = stats.get("count", 0)
                color = GREEN if name in ["PASSED", "XFAILED"] else RED if name in ["FAILED", "ERROR"] else YELLOW
                lines.append(f"  {color}{name.capitalize():<8}: {count:>3} ({pct:5.1f}%){RESET}")

        # Slowest Tests (historical, top 5)
        try:
            slowest_tests = all_sessions_insights.tests.slowest_tests(limit=5)
            slowest_list = slowest_tests.get("slowest_tests")
            if slowest_list:
                if isinstance(slowest_list, dict):
                    slowest_list = list(slowest_list.values())
                else:
                    slowest_list = list(slowest_list) if isinstance(slowest_list, (list, tuple)) else []
                lines.append(f"{BRIGHT}{MAGENTA}Slowest Tests:{RESET}")
                for test in slowest_list[:5]:
                    nodeid, dur = test
                    if isinstance(dur, (int, float)):
                        lines.append(f"  {MAGENTA}{nodeid}: {float(dur):.2f} seconds{RESET}")
        except Exception:
            pass
        # Display Pass Rate Trend (Last 7 runs)
        pass_rates = self.get_pass_rate_trend(7)
        if len(pass_rates) > 1:
            trend_str = " \u2192 ".join(f"{r:g}%" for r in pass_rates)
            lines.append(f"Pass Rate Trend (Last 7 runs):  {trend_str}")
        elif pass_rates:
            lines.append(f"Pass Rate Trend (Last 7 runs):  {pass_rates[0]:g}%  (only one session available)")
        else:
            lines.append("Pass Rate Trend (Last 7 runs):  (no data)")

        return "\n".join(lines)


# Factory function to create a new Insights instance.
def insights(analysis=None, profile_name=None):
    """
    Factory function to create a new Insights instance.

    Args:
        analysis: Optional Analysis instance to use
        profile_name: Optional profile name to use

    Returns:
        Insights instance
    """
    return Insights(analysis=analysis, profile_name=profile_name)


# Factory function to create a new Insights instance for a specific profile.
def insights_with_profile(profile_name):
    """
    Factory function to create a new Insights instance for a specific profile.

    Args:
        profile_name: Name of the profile to use

    Returns:
        New Insights instance configured with the specified profile
    """
    return Insights(profile_name=profile_name)
