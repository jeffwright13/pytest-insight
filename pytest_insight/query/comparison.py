from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Set

from pytest_insight.models import TestOutcome, TestSession
from pytest_insight.query.query import Query, QueryResult


class ComparisonError(Exception):
    """Base exception for comparison-related errors."""

    pass


@dataclass
class ComparisonResult:
    """Results of comparing two sets of test sessions."""

    base_results: QueryResult
    target_results: QueryResult
    duration_change: float
    outcome_changes: Dict[str, str]
    new_failures: Set[str]
    new_passes: Set[str]
    flaky_tests: Set[str]
    slower_tests: Dict[str, float]
    faster_tests: Dict[str, float]

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
    """Builder for test comparison operations."""

    def __init__(self):
        self._base_query = Query()
        self._target_query = Query()

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
        """Filter tests matching pattern in both queries."""
        self._base_query.test_contains(pattern)
        self._target_query.test_contains(pattern)
        return self

    def with_duration_threshold(self, threshold: float) -> "Comparison":
        """Only compare tests exceeding duration threshold."""
        self._base_query.duration_between(threshold, float("inf"))
        self._target_query.duration_between(threshold, float("inf"))
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

    def execute(self, sessions: Optional[List[TestSession]] = None) -> ComparisonResult:
        """Execute comparison and return results."""
        if not self._base_query or not self._target_query:
            raise ComparisonError("Both base and target queries must be configured")

        base_results = self._base_query.execute(sessions)
        target_results = self._target_query.execute(sessions)

        return ComparisonResult(
            base_results=base_results,
            target_results=target_results,
            duration_change=self._calculate_duration_change(base_results, target_results),
            outcome_changes=self._analyze_outcome_changes(base_results, target_results),
            new_failures=self._find_new_failures(base_results, target_results),
            new_passes=self._find_new_passes(base_results, target_results),
            flaky_tests=self._identify_flaky_tests(base_results, target_results),
            slower_tests=self._find_slower_tests(base_results, target_results),
            faster_tests=self._find_faster_tests(base_results, target_results),
        )

    def _calculate_duration_change(self, base_results: QueryResult, target_results: QueryResult) -> float:
        """Calculate overall duration change percentage."""
        if base_results.empty or target_results.empty:
            return 0.0
        base_duration = sum(t.duration for s in base_results.sessions for t in s.test_results)
        target_duration = sum(t.duration for s in target_results.sessions for t in s.test_results)
        if base_duration == 0:
            return 0.0
        return ((target_duration - base_duration) / base_duration) * 100

    def _analyze_outcome_changes(self, base_results: QueryResult, target_results: QueryResult) -> Dict[str, str]:
        """Find tests with changed outcomes."""
        changes = {}
        base_outcomes = {t.nodeid: t.outcome for s in base_results.sessions for t in s.test_results}
        target_outcomes = {t.nodeid: t.outcome for s in target_results.sessions for t in s.test_results}
        for nodeid in set(base_outcomes) & set(target_outcomes):
            if base_outcomes[nodeid] != target_outcomes[nodeid]:
                changes[nodeid] = f"{base_outcomes[nodeid]} -> {target_outcomes[nodeid]}"
        return changes

    def _find_new_failures(self, base_results: QueryResult, target_results: QueryResult) -> Set[str]:
        """Find tests that newly failed."""
        base_failures = {
            t.nodeid for s in base_results.sessions for t in s.test_results if t.outcome == TestOutcome.FAILED
        }
        target_failures = {
            t.nodeid for s in target_results.sessions for t in s.test_results if t.outcome == TestOutcome.FAILED
        }
        return target_failures - base_failures

    def _find_new_passes(self, base_results: QueryResult, target_results: QueryResult) -> Set[str]:
        """Find tests that newly passed."""
        base_passes = {
            t.nodeid for s in base_results.sessions for t in s.test_results if t.outcome == TestOutcome.PASSED
        }
        target_passes = {
            t.nodeid for s in target_results.sessions for t in s.test_results if t.outcome == TestOutcome.PASSED
        }
        return target_passes - base_passes

    def _identify_flaky_tests(self, base_results: QueryResult, target_results: QueryResult) -> Set[str]:
        """Identify tests that show flaky behavior."""
        all_sessions = base_results.sessions + target_results.sessions
        test_outcomes = {}
        for session in all_sessions:
            for test in session.test_results:
                if test.nodeid not in test_outcomes:
                    test_outcomes[test.nodeid] = set()
                test_outcomes[test.nodeid].add(test.outcome)
        return {nodeid for nodeid, outcomes in test_outcomes.items() if len(outcomes) > 1}

    def _find_slower_tests(self, base_results: QueryResult, target_results: QueryResult) -> Dict[str, float]:
        """Find tests that got slower."""
        base_durations = self._collect_durations(base_results.sessions)
        target_durations = self._collect_durations(target_results.sessions)
        return {
            nodeid: ((target_durations[nodeid] - base_durations[nodeid]) / base_durations[nodeid]) * 100
            for nodeid in set(base_durations) & set(target_durations)
            if target_durations[nodeid] > base_durations[nodeid]
        }

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
