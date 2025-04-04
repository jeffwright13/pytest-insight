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

from pytest_insight.core.analysis import Analysis
from pytest_insight.core.models import TestOutcome
from pytest_insight.core.storage import (
    get_storage_instance,
)


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

        return {
            "total_tests": total_tests,
            "outcomes": outcomes,
            "most_common": outcome_counts.most_common(),
        }

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
                            flaky_tests[nodeid] = {
                                "reruns": 0,
                                "sessions": set(),
                                "pass_rate": 0.0,
                            }
                        flaky_tests[nodeid]["reruns"] += (
                            len(rerun_group.tests) - 1
                        )  # Subtract 1 for the final passing test
                        flaky_tests[nodeid]["sessions"].add(session.session_id)

        # Calculate pass rates
        for nodeid, data in flaky_tests.items():
            total_runs = data["reruns"] + len(
                data["sessions"]
            )  # Total runs = reruns + final passing runs
            data["pass_rate"] = (
                len(data["sessions"]) / total_runs if total_runs > 0 else 0
            )
            data["sessions"] = list(
                data["sessions"]
            )  # Convert set to list for serialization

        # Sort by number of reruns
        most_flaky = sorted(
            [(nodeid, data) for nodeid, data in flaky_tests.items()],
            key=lambda x: x[1]["reruns"],
            reverse=True,
        )

        return {
            "flaky_tests": flaky_tests,
            "total_flaky": len(flaky_tests),
            "most_flaky": most_flaky,
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
        top_tests = sorted(test_run_counts.items(), key=lambda x: x[1], reverse=True)[
            :limit
        ]

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
                        pattern = (
                            f"{error_type}: {error_detail}"
                            if error_detail
                            else error_type
                        )

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

        # Find tests with multiple error patterns (potentially flaky or unstable)
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
        - Flakiness (20% weight)
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

        # Get flaky tests
        flaky_tests_data = self.flaky_tests()
        flaky_tests = flaky_tests_data["flaky_tests"]

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
            "flakiness": (1 - len(flaky_tests) / max(1, total_tests))
            * 20,  # 20% weight to lack of flakiness
            "duration_stability": 15,  # Default value, will be calculated below
            "failure_pattern": 15,  # Default value, will be calculated below
        }

        # Calculate duration stability component (lower variance = higher score)
        if slowest_tests:
            durations = [duration for _, duration in slowest_tests]
            if durations:
                mean_duration = sum(durations) / len(durations)
                variance = sum((d - mean_duration) ** 2 for d in durations) / len(
                    durations
                )
                # Normalize: lower variance = higher score (max 15)
                coefficient = 0.1  # Adjust based on typical variance values
                health_factors["duration_stability"] = 15 * (
                    1 / (1 + coefficient * variance)
                )

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

        insights = Insights(analysis=self.analysis)
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
            + (1 - len(flaky_tests) / max(1, total_tests))
            * 0.3  # 30% weight to lack of flakiness
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
                    var1 = (
                        sum((x - mean1) ** 2 for x in outcomes1[:min_length])
                        / min_length
                    )
                    var2 = (
                        sum((x - mean2) ** 2 for x in outcomes2[:min_length])
                        / min_length
                    )
                    cov = (
                        sum(
                            (outcomes1[i] - mean1) * (outcomes2[i] - mean2)
                            for i in range(min_length)
                        )
                        / min_length
                    )

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
                    # It's an enum
                    is_failed = outcome.value == "FAILED"
                else:
                    # It's a string
                    is_failed = str(outcome).upper() == "FAILED"

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
            return {
                "suts": list(suts),
                "comparisons": {},
                "best_sut": next(iter(suts)) if suts else None,
            }

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
                    sut_health_scores[sut1] = comparison["base_health"]["health_score"][
                        "overall_score"
                    ]
                if sut2 not in sut_health_scores:
                    sut_health_scores[sut2] = comparison["target_health"][
                        "health_score"
                    ]["overall_score"]

                # Store comparison results
                comparisons[comparison_key] = {
                    "base_sut": sut1,
                    "target_sut": sut2,
                    "base_health": comparison["base_health"]["health_score"][
                        "overall_score"
                    ],
                    "target_health": comparison["target_health"]["health_score"][
                        "overall_score"
                    ],
                    "health_difference": comparison["health_difference"],
                    "improved": comparison["improved"],
                }

        # Determine best SUT by health score
        best_sut = (
            max(sut_health_scores.items(), key=lambda x: x[1])[0]
            if sut_health_scores
            else None
        )

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
                session_pass_rate = sum(
                    1 for t in session_results if t.outcome == "passed"
                ) / len(session_results)
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
            env_variance = sum(
                (r - mean_env_pass_rate) ** 2 for r in env_pass_rate_values
            ) / len(env_pass_rate_values)
            # Lower variance = higher consistency
            consistency = 1 / (
                1 + 10 * env_variance
            )  # Scale factor of 10 for better distribution
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
            avg_duration = sum(s.session_duration for s in day_sessions) / len(
                day_sessions
            )
            daily_durations.append((day, avg_duration))

        # Calculate trend
        if len(daily_durations) >= 2:
            first_duration = daily_durations[0][1]
            last_duration = daily_durations[-1][1]
            if first_duration > 0:
                trend_percentage = (
                    (last_duration - first_duration) / first_duration
                ) * 100
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
                improving = (
                    trend_percentage < 0
                )  # Decreasing failure rate is an improvement
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
        comparison = self.analysis.compare_health(
            base_sessions=early_sessions, target_sessions=late_sessions
        )

        # Calculate additional metrics
        early_test_count = sum(len(s.test_results) for s in early_sessions)
        late_test_count = sum(len(s.test_results) for s in late_sessions)

        early_avg_duration = sum(s.session_duration for s in early_sessions) / len(
            early_sessions
        )
        late_avg_duration = sum(s.session_duration for s in late_sessions) / len(
            late_sessions
        )

        duration_change = (
            ((late_avg_duration - early_avg_duration) / early_avg_duration) * 100
            if early_avg_duration > 0
            else 0
        )

        return {
            "early_period": {
                "date_range": (early_start, early_end),
                "sessions": len(early_sessions),
                "tests": early_test_count,
                "avg_duration": early_avg_duration,
                "health_score": comparison["base_health"]["health_score"][
                    "overall_score"
                ],
            },
            "late_period": {
                "date_range": (late_start, late_end),
                "sessions": len(late_sessions),
                "tests": late_test_count,
                "avg_duration": late_avg_duration,
                "health_score": comparison["target_health"]["health_score"][
                    "overall_score"
                ],
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
            "trends": insights.trends.duration_trends()
        }
    """

    def __init__(
        self, analysis: Optional[Analysis] = None, profile_name: Optional[str] = None
    ):
        """Initialize insight components.

        Args:
            analysis: Optional Analysis instance to use. If None, creates a new one.
            profile_name: Optional profile name to use for storage configuration.
                         Takes precedence over analysis parameter if both are provided.
        """
        # Store the profile name
        self._profile_name = profile_name

        # Create or use the analysis instance
        if analysis is None:
            # Create a new Analysis instance
            if profile_name is not None:
                storage = get_storage_instance(profile_name=profile_name)
                self.analysis = Analysis(storage=storage)
            else:
                self.analysis = Analysis()
        else:
            self.analysis = analysis

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
        self.analysis = Analysis(storage=storage)

        # Reinitialize insight components with the updated analysis
        self.tests = TestInsights(self.analysis)
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
        """Generate a summary of insights for console display.

        Returns:
            Dict containing the most important metrics and insights
            formatted for easy display in a terminal.
        """
        # Get health score from metrics
        health_report = self.analysis.health_report()
        health_score = health_report.get("health_score", {}).get("overall_score", 0)

        # Get test outcome distribution
        outcome_dist = self.tests.outcome_distribution()
        outcomes = []
        for outcome, data in outcome_dist.get("outcomes", {}).items():
            outcomes.append((outcome, data.get("count", 0)))
        total_tests = outcome_dist.get("total_tests", 0)

        # Get flaky tests
        flaky_tests = self.tests.flaky_tests()
        flaky_test_count = flaky_tests.get("total_flaky", 0)
        most_flaky = flaky_tests.get("most_flaky", [])

        # Get slowest tests
        slow_tests = self.tests.slowest_tests(limit=3)
        slowest_tests = slow_tests.get("slowest_tests", [])

        # Get failure trends if we have multiple sessions
        failure_trend = {"change": 0, "improving": False}
        if self.analysis._sessions and len(self.analysis._sessions) > 1:
            trends = self.trends.failure_trends()
            failure_trend = {
                "change": trends.get("trend_percentage", 0),
                "improving": trends.get("improving", False),
            }

        # Get health report for more detailed metrics
        stability_score = health_report.get("health_score", {}).get(
            "stability_score", 0
        )
        performance_score = health_report.get("health_score", {}).get(
            "performance_score", 0
        )
        warning_score = health_report.get("health_score", {}).get("warning_score", 0)

        # Get recommendations if available
        recommendations = health_report.get("recommendations", [])

        # Get session metrics
        session_metrics = self.sessions.session_metrics()
        avg_duration = session_metrics.get("avg_duration", 0)
        failure_rate = session_metrics.get("failure_rate", 0) * 100
        warning_rate = session_metrics.get("warning_rate", 0) * 100

        # Get session info
        sut_name = "Unknown"
        session_id = "Unknown"
        storage_path = None
        if self.analysis._sessions and len(self.analysis._sessions) > 0:
            session = self.analysis._sessions[0]
            sut_name = session.sut_name
            session_id = session.session_id

        return {
            "sut_name": sut_name,
            "session_id": session_id,
            "storage_path": storage_path,
            "health_score": health_score,
            "stability_score": stability_score,
            "performance_score": performance_score,
            "warning_score": warning_score,
            "failure_rate": failure_rate,
            "warning_rate": warning_rate,
            "avg_duration": avg_duration,
            "outcome_distribution": outcomes,
            "total_tests": total_tests,
            "flaky_test_count": flaky_test_count,
            "most_flaky": most_flaky,
            "slowest_tests": slowest_tests,
            "failure_trend": failure_trend,
            "recommendations": (
                recommendations[:3] if recommendations else []
            ),  # Show top 3 recommendations
        }

    def format_console_output(
        self, session_id: str, sut_name: str, storage_path: str = None
    ) -> str:
        """Format insights data into a string suitable for console output.

        This method formats the insights from the current session into a
        human-readable string with ANSI color codes for terminal display.

        Args:
            session_id: The ID of the current session
            sut_name: The name of the system under test
            storage_path: Optional path to the storage file

        Returns:
            A formatted string with ANSI color codes ready for terminal display
        """
        # Get summary data
        summary = self.console_summary()

        # ANSI color codes
        RESET = "\033[0m"
        YELLOW = "\033[33m"
        GREEN = "\033[32m"
        RED = "\033[31m"
        CYAN = "\033[36m"

        # Helper function to colorize text
        def colorize(text, color_code):
            return f"{color_code}{text}{RESET}"

        # Helper function to create section headers
        def section_header(text):
            return colorize(f"\n--- {text} ---", YELLOW)

        # Format output
        output = []

        # Add note about single-session insights
        output.append(
            "Note: This summary shows insights for the current test session only."
        )
        output.append(
            "For multi-session analysis, use the 'insights' script or the Insights API."
        )
        output.append(
            "More advanced users may use the Q-C-A (Query-Compare-Analyze) Python API."
        )

        # Session Info Section
        output.append(section_header("Test Session Info"))
        output.append(f"    SUT Name: {sut_name}")
        output.append(f"    Session ID: {session_id}")
        if storage_path:
            output.append(f"    Storage Path: {storage_path}")

        # Health Score Section
        output.append(section_header("Test Health"))
        health_score = summary["health_score"]
        health_color = (
            GREEN if health_score >= 80 else (YELLOW if health_score >= 60 else RED)
        )
        health_text = f"{health_score:.2f}/100"
        output.append(f"    Health Score: {colorize(health_text, health_color)}")

        # Add detailed health score components
        if "stability_score" in summary:
            stability_color = (
                GREEN
                if summary["stability_score"] >= 80
                else (YELLOW if summary["stability_score"] >= 60 else RED)
            )
            stability_text = f"{summary['stability_score']:.2f}/100"
            output.append(
                f"    Stability Score: {colorize(stability_text, stability_color)}"
            )

        if "performance_score" in summary:
            perf_color = (
                GREEN
                if summary["performance_score"] >= 80
                else (YELLOW if summary["performance_score"] >= 60 else RED)
            )
            perf_text = f"{summary['performance_score']:.2f}/100"
            output.append(f"    Performance Score: {colorize(perf_text, perf_color)}")

        if "warning_score" in summary:
            warn_color = (
                GREEN
                if summary["warning_score"] >= 80
                else (YELLOW if summary["warning_score"] >= 60 else RED)
            )
            warn_text = f"{summary['warning_score']:.2f}/100"
            output.append(f"    Warning Score: {colorize(warn_text, warn_color)}")

        # Add failure rate
        if "failure_rate" in summary:
            fail_color = (
                GREEN
                if summary["failure_rate"] < 10
                else (YELLOW if summary["failure_rate"] < 20 else RED)
            )
            fail_text = f"{summary['failure_rate']:.1f}%"
            output.append(f"    Failure Rate: {colorize(fail_text, fail_color)}")

        # Add warning rate
        if "warning_rate" in summary:
            warn_rate_color = (
                GREEN
                if summary["warning_rate"] < 5
                else (YELLOW if summary["warning_rate"] < 15 else RED)
            )
            warn_rate_text = f"{summary['warning_rate']:.1f}%"
            output.append(
                f"    Warning Rate: {colorize(warn_rate_text, warn_rate_color)}"
            )

        # Add average duration
        if "avg_duration" in summary:
            avg_duration_color = (
                GREEN
                if summary["avg_duration"] < 60
                else (YELLOW if summary["avg_duration"] < 120 else RED)
            )
            avg_duration_text = f"{summary['avg_duration']:.2f}s"
            output.append(
                f"    Average Duration: {colorize(avg_duration_text, avg_duration_color)}"
            )

        # Test Execution Summary
        output.append(section_header("Test Execution Summary"))
        output.append(
            f"    Total Tests: {colorize(str(summary['total_tests']), GREEN)}"
        )

        # Calculate total duration from sessions
        total_duration = (
            sum(session.session_duration for session in self.analysis._sessions)
            if self.analysis._sessions
            else 0
        )
        duration_text = f"{total_duration:.2f}s"
        output.append(f"    Total Duration: {colorize(duration_text, GREEN)}")

        # Add session start/stop times if available
        if self.analysis._sessions and len(self.analysis._sessions) > 0:
            session = self.analysis._sessions[
                0
            ]  # Use the first session for start/stop times
            output.append(f"    Start Time: {session.session_start_time.isoformat()}")
            output.append(f"    Stop Time: {session.session_stop_time.isoformat()}")

        # Outcome Distribution
        output.append(section_header("Outcome Distribution"))
        if isinstance(summary["outcome_distribution"], dict):
            # Handle dictionary format (from console_summary)
            for outcome, data in summary["outcome_distribution"].items():
                count = data.get("count", 0)
                percentage = data.get("percentage", 0)
                value = f"{count} ({percentage:.1f}%)"
                outcome_str = (
                    outcome
                    if isinstance(outcome, str)
                    else (
                        outcome.to_str() if hasattr(outcome, "to_str") else str(outcome)
                    )
                )

                # Choose color based on outcome
                color = GREEN
                if outcome_str.lower() in ["failed", "error"]:
                    color = RED
                elif outcome_str.lower() in ["skipped", "xfailed", "xpassed"]:
                    color = YELLOW
                elif outcome_str.lower() == "rerun":
                    color = CYAN

                output.append(
                    f"    {outcome_str.capitalize()}: {colorize(value, color)}"
                )
        else:
            # Handle list of tuples format (original format)
            for outcome, count in summary["outcome_distribution"]:
                # Get the percentage from the count and total tests
                percentage = (
                    (count / summary["total_tests"]) * 100
                    if summary["total_tests"]
                    else 0
                )
                value = f"{count} ({percentage:.1f}%)"
                outcome_str = (
                    outcome.to_str() if hasattr(outcome, "to_str") else str(outcome)
                )

                # Choose color based on outcome
                color = GREEN
                if outcome_str.lower() in ["failed", "error"]:
                    color = RED
                elif outcome_str.lower() in ["skipped", "xfailed", "xpassed"]:
                    color = YELLOW
                elif outcome_str.lower() == "rerun":
                    color = CYAN

                output.append(
                    f"    {outcome_str.capitalize()}: {colorize(value, color)}"
                )

        # Flaky Tests
        if "flaky_test_count" in summary and summary["flaky_test_count"] > 0:
            output.append(section_header("Flaky Tests"))
            output.append(
                f"    Tests Requiring Reruns: {colorize(str(summary['flaky_test_count']), CYAN)}"
            )

            # Display most flaky tests
            if summary["most_flaky"]:
                output.append(section_header("Most Flaky Tests"))
                for nodeid, data in summary["most_flaky"][:3]:  # Show top 3
                    reruns = data.get("reruns", 0)
                    pass_rate = data.get("pass_rate", 0) * 100
                    pass_rate_text = f"{pass_rate:.1f}%"
                    output.append(
                        f"    {nodeid}: {colorize(str(reruns), CYAN)} reruns (Pass rate: {colorize(pass_rate_text, YELLOW)})"  # noqa: E501
                    )

        # Slowest Tests
        if summary["slowest_tests"]:
            output.append(section_header("Longest Running Tests"))
            for nodeid, duration in summary["slowest_tests"]:
                # Find test outcome for coloring if possible
                color = GREEN
                outcome = "Unknown"

                # Try to find the test in sessions to get its outcome
                for session in self.analysis._sessions:
                    for test in session.test_results:
                        if test.nodeid == nodeid:
                            outcome = (
                                test.outcome.to_str()
                                if hasattr(test.outcome, "to_str")
                                else str(test.outcome)
                            )
                            if outcome.lower() in ["failed", "error"]:
                                color = RED
                            elif outcome.lower() in ["skipped", "xfailed", "xpassed"]:
                                color = YELLOW
                            break

                duration_text = f"{duration:.2f}s"
                output.append(
                    f"    {nodeid}: {colorize(duration_text, color)} ({outcome.capitalize()})"
                )

        # Failure Trend (only if we have multiple sessions)
        if summary["failure_trend"]["change"] != 0:
            output.append(section_header("Trend Analysis"))
            trend_text = f"{abs(summary['failure_trend']['change']):.1f}% "
            if summary["failure_trend"]["improving"]:
                trend_text += "decrease in failures"
                output.append(f"    Failure Trend: {colorize(trend_text, GREEN)}")
            else:
                trend_text += "increase in failures"
                output.append(f"    Failure Trend: {colorize(trend_text, RED)}")

        # Add recommendations if available
        if summary.get("recommendations"):
            output.append(section_header("Recommendations"))
            for i, recommendation in enumerate(summary["recommendations"]):
                output.append(f"    {i+1}. {recommendation}")

        # Join all lines and return
        return "\n".join(output)


def insights(
    analysis: Optional[Analysis] = None, profile_name: Optional[str] = None
) -> Insights:
    """Create a new Insights instance.

    Args:
        analysis: Optional Analysis instance to use
        profile_name: Optional profile name to use for storage configuration

    Returns:
        Insights instance

    Example:
        insights(profile_name="production").summary_report()
    """
    return Insights(analysis=analysis, profile_name=profile_name)


def insights_with_profile(profile_name: str) -> Insights:
    """Create a new Insights instance with a specific profile.

    Args:
        profile_name: Name of the profile to use

    Returns:
        Insights instance

    Example:
        insights_with_profile("production").summary_report()
    """
    return Insights(profile_name=profile_name)
