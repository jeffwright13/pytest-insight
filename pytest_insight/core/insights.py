"""
Insights module for pytest-insight.

This module provides classes for generating insights from test data.
It includes functionality for analyzing test outcomes, identifying patterns,
and generating recommendations.

The API follows a fluent interface design pattern,
allowing for intuitive method chaining while preserving session context.
"""

from collections import Counter, defaultdict
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from pytest_insight.core.analysis import Analysis
else:
    # This allows tests to mock Analysis directly
    Analysis = None  # type: ignore

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
        # Remove the Analysis dependency
        # self.analysis = analysis
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
            data["sessions"] = list(data["sessions"])

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
            for test_result in session.test_results:
                nodeid = getattr(test_result, "nodeid", None)
                outcome = getattr(test_result, "outcome", None)

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

    def __init__(self, analysis):
        """Initialize with an Analysis instance.

        Args:
            analysis: Analysis instance to use for insights
        """
        self.analysis = analysis
        self._sessions = analysis._sessions

    def session_metrics(self, days: Optional[int] = None) -> Dict[str, Any]:
        """Calculate key session metrics.

        Args:
            days: Optional number of days to look back

        Returns:
            Dict containing:
            - total_sessions: Total number of sessions
            - pass_rate: Overall pass rate
            - avg_tests_per_session: Average number of tests per session
        """
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
                    "total_sessions": len(self.analysis._sessions) if self.analysis._sessions else 0,
                    "pass_rate": 0.0,
                    "avg_tests_per_session": 0.0,
                    "failure_rate": 0.0,
                    "warning_rate": 0.0,
                    "avg_duration": 0.0,
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

        return metrics

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
            profile_name: Optional profile name to use for storage configuration
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
            New Insights instance with the specified profile
        """
        from pytest_insight.core.analysis import Analysis

        storage = get_storage_instance(profile_name=profile_name)
        self.analysis = Analysis(storage=storage)

        # Reinitialize insight components with the updated analysis
        self.tests = TestInsights(self.analysis._sessions)
        self.sessions = SessionInsights(self.analysis)
        self.trends = TrendInsights(self.analysis)

        return self

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
            from colorama import Fore, Style
            # Initialize colorama
            import colorama
            colorama.init()
            
            # Define color constants
            GREEN = Fore.GREEN
            RED = Fore.RED
            YELLOW = Fore.YELLOW
            CYAN = Fore.CYAN
            BLUE = Fore.BLUE
            MAGENTA = Fore.MAGENTA
            BRIGHT = Style.BRIGHT
            RESET = Style.RESET_ALL
            
            # Flag that colors are available
            has_colors = True
        except ImportError:
            # Define empty color constants if colorama is not available
            GREEN = RED = YELLOW = CYAN = BLUE = MAGENTA = BRIGHT = RESET = ""
            has_colors = False
        
        # Get health score from metrics
        health_report = self.analysis.health_report()
        health_score = health_report.get("health_score", {}).get("overall_score", 0)

        # Get test outcome distribution
        outcome_dist = self.tests.outcome_distribution()
        outcomes = []
        
        # Direct calculation from session data as a fallback
        if not outcome_dist.get("outcomes") and self.analysis._sessions:
            # Calculate outcomes directly from the current session's test results
            session = self.analysis._sessions[0]
            if hasattr(session, "test_results") and session.test_results:
                # Count outcomes
                outcome_counts = {}
                total = 0
                
                for test in session.test_results:
                    outcome_name = test.outcome.value.lower() if hasattr(test.outcome, "value") else str(test.outcome).lower()
                    outcome_counts[outcome_name] = outcome_counts.get(outcome_name, 0) + 1
                    total += 1
                
                # Create outcome distribution in the expected format
                outcomes = [(outcome, count) for outcome, count in outcome_counts.items()]
                total_tests = total
            else:
                # Use the values from outcome_dist
                for outcome, data in outcome_dist.get("outcomes", {}).items():
                    outcomes.append((outcome, data.get("count", 0)))
                total_tests = outcome_dist.get("total_tests", 0)
        else:
            # Use the values from outcome_dist
            for outcome, data in outcome_dist.get("outcomes", {}).items():
                outcomes.append((outcome, data.get("count", 0)))
            total_tests = outcome_dist.get("total_tests", 0)

        # Get unreliable tests
        unreliable_tests = self.tests.unreliable_tests()
        unreliable_test_count = unreliable_tests.get("total_unreliable", 0)
        most_unreliable = unreliable_tests.get("most_unreliable", [])

        # Get slowest tests
        slow_tests = self.tests.slowest_tests(limit=3)
        slowest_tests = slow_tests.get("slowest_tests", [])

        # Get top failing tests (new)
        try:
            top_failing = self.analysis.sessions.top_failing_tests(limit=3)
            top_failing_tests = top_failing.get("top_failing", [])
        except (AttributeError, Exception):
            # Fallback to empty list if the method is not available
            top_failing_tests = []

        # Get regression rate (new)
        try:
            regression_data = self.analysis.sessions.regression_rate()
            regression_rate = regression_data.get("regression_rate", 0)
            regressed_tests = regression_data.get("regressed_tests", [])[:3]  # Top 3 regressed tests
        except (AttributeError, Exception):
            regression_rate = 0
            regressed_tests = []

        # Get longest running tests (new)
        try:
            longest_tests_data = self.analysis.sessions.longest_running_tests(limit=3)
            longest_tests = longest_tests_data.get("longest_tests", [])
        except (AttributeError, Exception):
            longest_tests = []

        # Get duration trend (new)
        try:
            duration_trend_data = self.analysis.sessions.test_suite_duration_trend()
            duration_trend = duration_trend_data.get("trend", {}).get("direction", "stable")
        except (AttributeError, Exception):
            duration_trend = "stable"

        # Get rerun test groups
        rerun_groups = []
        rerun_count = 0
        recovered_count = 0
        if self.analysis._sessions and len(self.analysis._sessions) > 0:
            session = self.analysis._sessions[0]
            if hasattr(session, "rerun_test_groups"):
                rerun_count = len(session.rerun_test_groups)
                for group in session.rerun_test_groups:
                    if hasattr(group, "final_outcome") and group.final_outcome == "passed":
                        recovered_count += 1

        # Get stability score
        stability_score = health_report.get("stability_score", {}).get("overall_score", 0)
        
        # Get performance score
        performance_score = health_report.get("performance_score", {}).get("overall_score", 0)
        
        # Get failure trend
        failure_trend = "stable"
        if "trends" in health_report and "failure_rate" in health_report["trends"]:
            trend_direction = health_report["trends"]["failure_rate"].get("direction", "stable")
            failure_trend = trend_direction
        
        # Get warning score
        warning_score = health_report.get("warning_score", {}).get("overall_score", 0)
        
        # Get recommendations
        recommendations = health_report.get("recommendations", [])
        
        # Get session metrics
        session_metrics = self.sessions.session_metrics() if hasattr(self, "sessions") else {}
        avg_duration = session_metrics.get("avg_duration", 0)
        failure_rate = session_metrics.get("failure_rate", 0) * 100
        warning_rate = session_metrics.get("warning_rate", 0) * 100

        # Get session info
        sut_name = "Unknown"
        session_id = "Unknown"
        session_date = "Unknown"
        profile_name = getattr(self, "_profile_name", "default")
        if profile_name is None:
            profile_name = "default"
        
        if self.analysis._sessions and len(self.analysis._sessions) > 0:
            session = self.analysis._sessions[0]  # Use the first session for start/stop times
            sut_name = session.sut_name
            session_id = session.session_id
            if hasattr(session, "start_time") and session.start_time:
                from datetime import datetime
                try:
                    # Try to parse the timestamp and format it nicely
                    if isinstance(session.start_time, str):
                        session_date = datetime.fromisoformat(session.start_time.replace('Z', '+00:00')).strftime("%Y-%m-%d %H:%M")
                    else:
                        session_date = datetime.fromtimestamp(session.start_time).strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError, AttributeError):
                    # Fall back to string representation if parsing fails
                    session_date = str(session.start_time)

        # Determine health grade based on health score
        health_grade = "F"
        health_desc = "Critical issues"
        if health_score >= 90:
            health_grade = "A"
            health_desc = "Excellent"
        elif health_score >= 80:
            health_grade = "B+"
            health_desc = "Very good"
        elif health_score >= 70:
            health_grade = "B"
            health_desc = "Stable, minor flakiness"
        elif health_score >= 60:
            health_grade = "C+"
            health_desc = "Moderate issues"
        elif health_score >= 50:
            health_grade = "C"
            health_desc = "Needs attention"
        elif health_score >= 40:
            health_grade = "D"
            health_desc = "Significant issues"

        # Format the summary as a string
        lines = []
        
        # Last Session section
        lines.append(f"{BRIGHT}Last Session: {CYAN}{session_date}{RESET} | {BRIGHT}SUT: {CYAN}{sut_name}{RESET} | {BRIGHT}Profile: {CYAN}{profile_name}{RESET} | {BRIGHT}{total_tests} tests{RESET}")
        
        # Outcomes line
        outcome_parts = []
        # Sort outcomes by count (descending) and take top 4
        sorted_outcomes = sorted(outcomes, key=lambda x: x[1], reverse=True)
        main_outcomes = sorted_outcomes[:4]  # Show top 4 outcomes
        other_count = sum(count for _, count in sorted_outcomes[4:]) if len(sorted_outcomes) > 4 else 0
        
        for outcome_name, count in main_outcomes:
            # Clean up outcome name (remove TestOutcome. prefix if present)
            clean_name = str(outcome_name)
            if "TestOutcome." in clean_name:
                clean_name = clean_name.replace("TestOutcome.", "").lower()
            
            percentage = (count/total_tests*100) if total_tests > 0 else 0
            
            # Color code by outcome type
            outcome_color = RESET
            if clean_name in ["passed", "xpassed"]:
                outcome_color = GREEN
            elif clean_name in ["failed", "error"]:
                outcome_color = RED
            elif clean_name in ["skipped", "xfailed"]:
                outcome_color = YELLOW
            elif clean_name in ["rerun"]:
                outcome_color = MAGENTA
                
            outcome_parts.append(f"{outcome_color}{count} {clean_name} ({percentage:.1f}%){RESET}")
            
        # Add "other" category if needed
        if other_count > 0:
            other_percentage = (other_count/total_tests*100) if total_tests > 0 else 0
            outcome_parts.append(f"{BLUE}{other_count} other ({other_percentage:.1f}%){RESET}")
            
        lines.append(f"  {BRIGHT}Outcomes:{RESET}  {' | '.join(outcome_parts)}")
        
        # Reruns line
        lines.append(f"  {BRIGHT}Reruns:{RESET}    {MAGENTA}{rerun_count} tests rerun{RESET} | {GREEN if recovered_count > 0 else RESET}{recovered_count} succeeded after rerun{RESET}")
        
        # Health line
        lines.append(f"  {BRIGHT}Health:{RESET}    {GREEN if health_score >= 80 else YELLOW if health_score >= 50 else RED}{health_grade} ({health_desc}){RESET}")
        
        # Actionable items
        lines.append(f"  {BRIGHT}Actionable:{RESET} ")
        actionable_items = []
        
        # Add top failing tests
        for test in top_failing_tests[:2]:
            if isinstance(test, dict):
                nodeid = test.get('nodeid', '')
                if nodeid:
                    actionable_items.append(f"    - {RED}Investigate persistent failure: {nodeid.split('::')[-1]}{RESET}")
        
        # Add unreliable tests
        if unreliable_test_count > 0 and most_unreliable:
            test = most_unreliable[0]
            if isinstance(test, dict):
                nodeid = test.get('nodeid', '')
                if nodeid:
                    actionable_items.append(f"    - {YELLOW}{unreliable_test_count} flaky test(s) detected: {nodeid.split('::')[-1]}{RESET}")
        
        # Add regressed tests
        if regressed_tests:
            test = regressed_tests[0]
            if isinstance(test, dict):
                nodeid = test.get('nodeid', '')
                if nodeid:
                    actionable_items.append(f"    - {RED}New regression detected: {nodeid.split('::')[-1]}{RESET}")
        
        # If no actionable items, add a placeholder
        if not actionable_items:
            if recommendations:
                actionable_items.append(f"    - {recommendations[0]}")
            else:
                actionable_items.append("    - No actionable insights available")
        
        lines.extend(actionable_items)
        
        # Separator
        lines.append("")
        lines.append("------------------------------------------------------------")
        lines.append("")
        
        # All Sessions section (if available)
        session_count = len(self.analysis._sessions) if self.analysis._sessions else 0
        lines.append(f"{BRIGHT}All Sessions (last 30 days):{RESET} {session_count} sessions | {BRIGHT}SUT: {CYAN}{sut_name}{RESET}")
        
        # Overall outcome stats (simplified for now)
        lines.append(f"  {BRIGHT}Outcomes:{RESET}  {total_tests} total tests | {failure_rate:.1f}% failure rate")
        lines.append(f"  {BRIGHT}Reruns:{RESET}    {MAGENTA}{rerun_count} tests rerun{RESET} | {GREEN if recovered_count > 0 else RESET}{recovered_count} succeeded after rerun{RESET}")
        lines.append(f"  {BRIGHT}Health:{RESET}    {GREEN if health_score >= 80 else YELLOW if health_score >= 50 else RED}{health_grade} ({health_desc}){RESET}")
        
        # Trends
        failure_trend_arrow = "↓" if failure_trend == "decreasing" else ("↑" if failure_trend == "increasing" else "↔")
        flakiness_arrow = "↓" if unreliable_test_count == 0 else ("↑" if unreliable_test_count > 2 else "↔")
        duration_arrow = "↓" if duration_trend == "decreasing" else ("↑" if duration_trend == "increasing" else "↔")
        
        lines.append(f"  {BRIGHT}Trends:{RESET}    Failures {GREEN if failure_trend == 'decreasing' else RED if failure_trend == 'increasing' else YELLOW}{failure_trend_arrow}{RESET} | Flakiness {GREEN if unreliable_test_count == 0 else RED if unreliable_test_count > 2 else YELLOW}{flakiness_arrow}{RESET} | Duration {GREEN if duration_trend == 'decreasing' else YELLOW if duration_trend == 'increasing' else RESET}{duration_arrow}{RESET}")
        lines.append("")
        
        # Actionable insights for all sessions
        lines.append(f"  {BRIGHT}Actionable:{RESET} ")
        all_actionable = []
        
        # Add failing tests across sessions
        if top_failing_tests:
            test = top_failing_tests[0]
            if isinstance(test, dict):
                nodeid = test.get('nodeid', '')
                failure_count = test.get('failure_count', 0)
                if nodeid and failure_count > 0:
                    all_actionable.append(f"    - {nodeid.split('::')[-1]} has failed in {failure_count} sessions")
        
        # Add regression info
        if regression_rate > 0:
            all_actionable.append(f"    - {len(regressed_tests)} new regressions detected this week")
        
        # If no actionable items, add a placeholder
        if not all_actionable:
            if recommendations and len(recommendations) > 1:
                all_actionable.append(f"    - {recommendations[1]}")
            else:
                all_actionable.append("    - No actionable insights available for all sessions")
        
        lines.extend(all_actionable)
        
        return "\n".join(lines)


def get_insights() -> "Insights":
    """
    Factory function to create a new Insights instance with the default or active profile.

    Returns:
        Insights instance
    """
    return Insights()


def insights() -> "Insights":
    """
    Factory function to create a new Insights instance with the default or active profile.

    Returns:
        Insights instance
    """
    return Insights()


def insights_with_profile(profile_name: str) -> "Insights":
    """
    Factory function to create a new Insights instance for a specific profile.

    Args:
        profile_name: Name of the profile to use

    Returns:
        Insights instance configured with the specified profile
    """
    return Insights(profile_name=profile_name)
