from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Set

from pytest_insight.models import TestOutcome, TestSession
from pytest_insight.query.query import Query, QueryResult


class ComparisonError(Exception):
    """Exception raised for comparison errors."""

    pass


@dataclass
class ComparisonResult:
    """Results of a comparison between test sessions."""

    base_results: QueryResult
    target_results: QueryResult
    outcome_changes: Dict[str, Dict[str, str]]
    new_failures: Set[str]
    new_passes: Set[str]
    flaky_tests: Set[str]
    slower_tests: Dict[str, Dict[str, float]]
    faster_tests: Dict[str, Dict[str, float]]
    duration_change: float = 0.0  # Make this parameter optional with default

    @property
    def has_changes(self) -> bool:
        """Check if comparison found any differences."""
        return bool(
            self.outcome_changes
            or self.new_failures
            or self.new_passes
            or self.flaky_tests
            or self.slower_tests
            or self.faster_tests
        )


class Comparison:
    """Compare test results between sessions."""

    def __init__(self):
        """Initialize comparison with default settings."""
        self._base_query = Query()
        self._target_query = Query()
        self._base_filter = None
        self._target_filter = None
        self.duration_threshold = 1.0  # Default threshold

    def between_suts(self, base_sut: str, target_sut: str) -> "Comparison":
        """Compare between two SUTs."""
        if not isinstance(base_sut, str) or not isinstance(target_sut, str):
            raise ComparisonError("SUT names must be strings")
        self._base_query.for_sut(base_sut)
        self._target_query.for_sut(target_sut)
        return self

    def with_environment(self, base_env: dict, target_env: dict) -> "Comparison":
        """Compare tests across different environments."""
        for key, value in base_env.items():
            self._base_query.with_tag(key, value)
        for key, value in target_env.items():
            self._target_query.with_tag(key, value)
        return self

    def in_date_window(self, start: datetime, cutoff: datetime) -> "Comparison":
        """Compare sessions before and after a cutoff within a time window."""
        self._base_query.date_range(start, cutoff)
        self._target_query.date_range(cutoff, datetime.now())
        return self

    def with_test_pattern(self, pattern: str) -> "Comparison":
        """Filter both sides to tests matching pattern."""
        if not isinstance(pattern, str) or not pattern.strip():
            raise ComparisonError("Test pattern must be a non-empty string")

        # Store the pattern for direct session filtering
        self._test_pattern = pattern

        # Split the base and target queries to handle them separately
        self._base_query = self._create_pattern_filtered_query(self._base_query, pattern)
        self._target_query = self._create_pattern_filtered_query(self._target_query, pattern)
        return self

    def _create_pattern_filtered_query(self, query: Query, pattern: str) -> Query:
        """Create a new query with test pattern filter applied correctly."""
        # Create a copy to avoid modifying the original
        new_query = Query()

        # Copy existing filters
        for filter_func in query._filters:
            new_query._filters.append(filter_func)

        # Add a filter that keeps only sessions with the matching test
        # AND filters the test results to only include the matching test
        def pattern_filter(s):
            return TestSession(
                sut_name=s.sut_name,
                session_id=s.session_id,
                session_start_time=s.session_start_time,
                session_stop_time=s.session_stop_time,
                session_duration=s.session_duration,
                test_results=[t for t in s.test_results if pattern == t.nodeid or pattern in t.nodeid],
                rerun_test_groups=s.rerun_test_groups,
                session_tags=s.session_tags,
            )

        # Add this as a session transform, not just a filter
        new_query._transforms = getattr(new_query, "_transforms", []) + [pattern_filter]

        # Add a filter that removes sessions with no matching tests
        new_query._filters.append(lambda s: any(pattern == t.nodeid or pattern in t.nodeid for t in s.test_results))

        return new_query

    def with_duration_threshold(self, threshold: float) -> "Comparison":
        """Set threshold for identifying significant duration changes.

        Args:
            threshold: Minimum seconds difference to consider significant

        Returns:
            Self for method chaining
        """
        if not isinstance(threshold, (int, float)) or threshold < 0:
            raise ComparisonError("Duration threshold must be a positive number")
        self.duration_threshold = threshold
        return self

    def exclude_flaky(self) -> "Comparison":
        """Exclude known flaky tests from comparison."""
        self._base_query.with_reruns(False)
        self._target_query.with_reruns(False)
        return self

    def only_failures(self) -> "Comparison":
        """Focus comparison on test failures."""
        self._base_query.with_outcome(TestOutcome.FAILED)
        self._target_query.with_outcome(TestOutcome.FAILED)
        return self

    def execute(self, sessions=None):
        """Execute comparison between base and target results."""
        if sessions is None:
            # No sessions provided directly, check if we have configured queries
            if not self._base_query._filters or not self._target_query._filters:
                raise ComparisonError("No sessions provided and no query filters configured to fetch sessions")

        try:
            # When sessions are directly provided, split them for base and target
            if sessions:
                # Take first session as base, other sessions as target
                base_sessions = [sessions[0]]
                target_sessions = sessions[1:] if len(sessions) > 1 else []

                # Create QueryResults with the sessions
                base_results = QueryResult(
                    sessions=base_sessions,
                    total_count=len(base_sessions),
                    execution_time=0,
                    matched_nodeids={t.nodeid for s in base_sessions for t in s.test_results},
                )

                target_results = QueryResult(
                    sessions=target_sessions,
                    total_count=len(target_sessions),
                    execution_time=0,
                    matched_nodeids={t.nodeid for s in target_sessions for t in s.test_results},
                )

                # If we have a test pattern filter, apply it to both result sets
                if hasattr(self, "_test_pattern") and self._test_pattern:
                    # Filter test results to only include matching tests
                    pattern = self._test_pattern

                    # Apply filter to base sessions
                    for i, session in enumerate(base_results.sessions):
                        filtered_tests = [t for t in session.test_results if pattern == t.nodeid or pattern in t.nodeid]
                        # Replace with filtered version
                        base_results.sessions[i] = TestSession(
                            sut_name=session.sut_name,
                            session_id=session.session_id,
                            session_start_time=session.session_start_time,
                            session_stop_time=session.session_stop_time,
                            session_duration=session.session_duration,
                            test_results=filtered_tests,
                            rerun_test_groups=session.rerun_test_groups,
                            session_tags=session.session_tags,
                        )

                    # Apply filter to target sessions
                    for i, session in enumerate(target_results.sessions):
                        filtered_tests = [t for t in session.test_results if pattern == t.nodeid or pattern in t.nodeid]
                        # Replace with filtered version
                        target_results.sessions[i] = TestSession(
                            sut_name=session.sut_name,
                            session_id=session.session_id,
                            session_start_time=session.session_start_time,
                            session_stop_time=session.session_stop_time,
                            session_duration=session.session_duration,
                            test_results=filtered_tests,
                            rerun_test_groups=session.rerun_test_groups,
                            session_tags=session.session_tags,
                        )
            else:
                # Execute queries to get results
                base_results = self._base_query.execute(None)
                target_results = self._target_query.execute(None)

            # Create dictionaries to store outcomes
            base_outcomes = {}
            target_outcomes = {}

            # Extract outcomes from base sessions
            for session in base_results.sessions:
                for test in session.test_results:
                    outcome = test.outcome.value if hasattr(test.outcome, "value") else str(test.outcome)
                    base_outcomes[test.nodeid] = outcome

            # Extract outcomes from target sessions
            for session in target_results.sessions:
                for test in session.test_results:
                    outcome = test.outcome.value if hasattr(test.outcome, "value") else str(test.outcome)
                    target_outcomes[test.nodeid] = outcome

            # Calculate outcome changes
            outcome_changes = {}
            new_failures = set()
            new_passes = set()
            flaky_tests = set()

            # Find tests in both sets
            common_tests = set(base_outcomes.keys()) & set(target_outcomes.keys())

            # Compare outcomes
            for nodeid in common_tests:
                base_outcome = base_outcomes[nodeid]
                target_outcome = target_outcomes[nodeid]

                # If outcome changed, record it
                if base_outcome != target_outcome:
                    outcome_changes[nodeid] = {"base": base_outcome, "target": target_outcome}

                    # Specifically check for failures
                    if base_outcome == "PASSED" and target_outcome == "FAILED":
                        new_failures.add(nodeid)

                    # Check for fixes
                    if base_outcome == "FAILED" and target_outcome == "PASSED":
                        new_passes.add(nodeid)

                    # All changes are potentially flaky
                    flaky_tests.add(nodeid)

            # Calculate performance changes
            base_durations = {t.nodeid: t.duration for s in base_results.sessions for t in s.test_results}
            target_durations = {t.nodeid: t.duration for s in target_results.sessions for t in s.test_results}

            # Find tests that got slower or faster
            slower_tests = {}
            faster_tests = {}

            for nodeid in common_tests:
                if nodeid in base_durations and nodeid in target_durations:
                    base_duration = base_durations[nodeid]
                    target_duration = target_durations[nodeid]
                    diff = target_duration - base_duration

                    if abs(diff) >= self.duration_threshold:
                        if diff > 0:  # Got slower
                            slower_tests[nodeid] = {
                                "base": base_duration,
                                "target": target_duration,
                                "diff": diff,
                                "percent": (diff / base_duration * 100) if base_duration > 0 else float("inf"),
                            }
                        else:  # Got faster
                            faster_tests[nodeid] = {
                                "base": base_duration,
                                "target": target_duration,
                                "diff": -diff,  # Make positive
                                "percent": (-diff / base_duration * 100) if base_duration > 0 else float("inf"),
                            }

            # Calculate overall duration change
            base_total = sum(t.duration for s in base_results.sessions for t in s.test_results)
            target_total = sum(t.duration for s in target_results.sessions for t in s.test_results)
            duration_change = ((target_total - base_total) / base_total * 100) if base_total > 0 else 0.0

            return ComparisonResult(
                base_results=base_results,
                target_results=target_results,
                outcome_changes=outcome_changes,
                new_failures=new_failures,
                new_passes=new_passes,
                flaky_tests=flaky_tests,
                slower_tests=slower_tests,
                faster_tests=faster_tests,
                duration_change=duration_change,
            )
        except Exception as e:
            if isinstance(e, ComparisonError):
                raise
            raise ComparisonError(f"Comparison execution failed: {str(e)}") from e

    def _get_outcome(self, nodeid, sessions):
        """Get most recent outcome for a test across sessions."""
        for session in sorted(sessions, key=lambda s: s.session_start_time, reverse=True):
            for test in session.test_results:
                if test.nodeid == nodeid:
                    return test.outcome.value if hasattr(test.outcome, "value") else str(test.outcome)
        return None

    def _get_duration(self, nodeid, sessions):
        """Get most recent duration for a test across sessions."""
        for session in sorted(sessions, key=lambda s: s.session_start_time, reverse=True):
            for test in session.test_results:
                if test.nodeid == nodeid:
                    return test.duration
        return None

    def _get_test_outcome(self, nodeid, query_result):
        """Get the outcome for a specific test from query results.

        Returns the outcome as a string or None if test not found.
        """
        for session in query_result.sessions:
            for test in session.test_results:
                if test.nodeid == nodeid:
                    return test.outcome.value if hasattr(test.outcome, "value") else str(test.outcome)
        return None

    def _get_test_duration(self, nodeid, query_result):
        """Get the duration for a specific test from query results.

        Returns the duration as float or None if test not found.
        """
        for session in query_result.sessions:
            for test in session.test_results:
                if test.nodeid == nodeid:
                    return test.duration
        return None

    def _calculate_duration_change(self, base_results: QueryResult, target_results: QueryResult) -> float:
        """Calculate overall duration change percentage."""
        if base_results.empty or target_results.empty:
            return 0.0
        base_duration = sum(t.duration for s in base_results.sessions for t in s.test_results)
        target_duration = sum(t.duration for s in target_results.sessions for t in s.test_results)
        if base_duration == 0:
            return 0.0
        return ((target_duration - base_duration) / base_duration) * 100

    def _calculate_outcome_changes(self, base_results: QueryResult, target_results: QueryResult) -> dict:
        """Calculate outcome changes between base and target."""
        changes = {}

        # Get all unique nodeids
        all_nodeids = set()
        for session in base_results.sessions + target_results.sessions:
            all_nodeids.update(test.nodeid for test in session.test_results)

        # Compare outcomes
        for nodeid in all_nodeids:
            base_outcome = self._get_test_outcome(nodeid, base_results)
            target_outcome = self._get_test_outcome(nodeid, target_results)

            # Only consider tests that appear in both sets
            if base_outcome and target_outcome and base_outcome != target_outcome:
                changes[nodeid] = {"base": base_outcome, "target": target_outcome}

        return changes

    def _analyze_outcome_changes(self, base_results: QueryResult, target_results: QueryResult) -> Dict[str, str]:
        """Find tests with changed outcomes."""
        base_outcomes = {t.nodeid: t.outcome for s in base_results.sessions for t in s.test_results}
        target_outcomes = {t.nodeid: t.outcome for s in target_results.sessions for t in s.test_results}
        changes = {
            nodeid: f"{base_outcomes[nodeid]} -> {target_outcomes[nodeid]}"
            for nodeid in set(base_outcomes) & set(target_outcomes)
            if base_outcomes[nodeid] != target_outcomes[nodeid]
        }
        return changes

    def _find_new_failures(self, base_results: QueryResult, target_results: QueryResult) -> set:
        """Find tests that newly failed."""
        # Get outcome changes
        outcome_changes = self._calculate_outcome_changes(base_results, target_results)

        # Filter for tests that changed from PASSED to FAILED
        return {
            nodeid
            for nodeid, change in outcome_changes.items()
            if change["base"] == "PASSED" and change["target"] == "FAILED"
        }

    def _find_new_passes(self, base_results: QueryResult, target_results: QueryResult) -> Set[str]:
        """Find tests that newly passed."""
        # Get outcome changes
        outcome_changes = self._calculate_outcome_changes(base_results, target_results)

        # Filter for tests that changed from FAILED to PASSED
        return {
            nodeid
            for nodeid, change in outcome_changes.items()
            if change["base"] == "FAILED" and change["target"] == "PASSED"
        }

    def _identify_flaky_tests(self, base_results: QueryResult, target_results: QueryResult) -> Set[str]:
        """Identify tests that show flaky behavior."""
        # Use the outcome_changes method instead of direct object comparison
        outcome_changes = self._calculate_outcome_changes(base_results, target_results)
        return set(outcome_changes.keys())

    def _find_slower_tests(self, base_results: QueryResult, target_results: QueryResult) -> dict:
        """Find tests that got slower."""
        result = {}

        # Get duration maps
        base_durations = {t.nodeid: t.duration for s in base_results.sessions for t in s.test_results}

        target_durations = {t.nodeid: t.duration for s in target_results.sessions for t in s.test_results}

        # Find tests that exist in both sets
        common_tests = set(base_durations.keys()) & set(target_durations.keys())

        # Check for duration increases
        for nodeid in common_tests:
            base_duration = base_durations[nodeid]
            target_duration = target_durations[nodeid]

            if target_duration > base_duration:
                diff = target_duration - base_duration

                # Only include if difference exceeds threshold
                if diff >= self.duration_threshold:
                    result[nodeid] = {
                        "base": base_duration,
                        "target": target_duration,
                        "diff": diff,
                        "percent": (diff / base_duration * 100) if base_duration > 0 else float("inf"),
                    }

        return result

    def _find_faster_tests(self, base_results: QueryResult, target_results: QueryResult) -> Dict[str, float]:
        """Find tests that got faster."""
        base_durations = self._collect_durations(base_results.sessions)
        target_durations = self._collect_durations(target_results.sessions)
        return {
            nodeid: ((target_durations[nodeid] - base_durations[nodeid]) / base_durations[nodeid]) * 100
            for nodeid in set(base_durations) & set(target_durations)
            if target_durations[nodeid] < base_durations[nodeid]
        }

    def _collect_durations(self, sessions: List[TestSession]) -> Dict[str, float]:
        """Collect test durations from sessions."""
        durations = {}
        for session in sessions:
            for test in session.test_results:
                if test.nodeid not in durations:
                    durations[test.nodeid] = test.duration
                else:
                    durations[test.nodeid] = min(durations[test.nodeid], test.duration)
        return durations
