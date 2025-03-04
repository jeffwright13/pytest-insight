from dataclasses import dataclass
from typing import List, Dict, Optional, Set
from datetime import datetime

from pytest_insight.models import TestSession
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

class SessionComparator:
    """Compare test sessions with detailed analysis."""

    def __init__(self, base_query: Query, target_query: Query):
        """Initialize comparator with two queries."""
        self.base_query = base_query
        self.target_query = target_query

    def compare(self, sessions: Optional[List[TestSession]] = None) -> ComparisonResult:
        """Execute comparison between query results."""
        base_results = self.base_query.execute(sessions)
        target_results = self.target_query.execute(sessions)

        return ComparisonResult(
            base_results=base_results,
            target_results=target_results,
            duration_change=self._calculate_duration_change(base_results, target_results),
            outcome_changes=self._analyze_outcome_changes(base_results, target_results),
            new_failures=self._find_new_failures(base_results, target_results),
            new_passes=self._find_new_passes(base_results, target_results),
            flaky_tests=self._identify_flaky_tests(base_results, target_results),
            slower_tests=self._find_slower_tests(base_results, target_results),
            faster_tests=self._find_faster_tests(base_results, target_results)
        )

    def _calculate_duration_change(
        self, base_results: QueryResult, target_results: QueryResult
    ) -> float:
        """Calculate percentage change in total duration."""
        base_duration = sum(s.session_duration for s in base_results.sessions)
        target_duration = sum(s.session_duration for s in target_results.sessions)
        if base_duration == 0:
            return float('inf') if target_duration > 0 else 0.0
        return ((target_duration - base_duration) / base_duration) * 100

    def _analyze_outcome_changes(
        self, base_results: QueryResult, target_results: QueryResult
    ) -> Dict[str, str]:
        """Track outcome changes for each test."""
        changes = {}
        base_outcomes = self._collect_outcomes(base_results.sessions)
        target_outcomes = self._collect_outcomes(target_results.sessions)

        all_nodeids = base_results.matched_nodeids | target_results.matched_nodeids
        for nodeid in all_nodeids:
            base = base_outcomes.get(nodeid, "NOT_RUN")
            target = target_outcomes.get(nodeid, "NOT_RUN")
            if base != target:
                changes[nodeid] = f"{base}->{target}"
        return changes

    def _find_new_failures(
        self, base_results: QueryResult, target_results: QueryResult
    ) -> Set[str]:
        """Find tests that newly failed."""
        base_failures = {
            t.nodeid for s in base_results.sessions
            for t in s.test_results if t.outcome == "FAILED"
        }
        target_failures = {
            t.nodeid for s in target_results.sessions
            for t in s.test_results if t.outcome == "FAILED"
        }
        return target_failures - base_failures

    def _find_new_passes(
        self, base_results: QueryResult, target_results: QueryResult
    ) -> Set[str]:
        """Find tests that newly passed."""
        base_passes = {
            t.nodeid for s in base_results.sessions
            for t in s.test_results if t.outcome == "PASSED"
        }
        target_passes = {
            t.nodeid for s in target_results.sessions
            for t in s.test_results if t.outcome == "PASSED"
        }
        return target_passes - base_passes

    @staticmethod
    def _collect_outcomes(sessions: list[TestSession]) -> Dict[str, str]:
        """Collect final outcomes for all tests."""
        outcomes = {}
        for session in sessions:
            for result in session.test_results:
                outcomes[result.nodeid] = result.outcome
        return outcomes

    def _identify_flaky_tests(
        self, base_results: QueryResult, target_results: QueryResult
    ) -> Set[str]:
        """Identify tests with inconsistent results across sessions.

        A test is considered flaky if:
        1. It has different outcomes in the same session
        2. It has different outcomes between base and target sessions
        """
        flaky_tests = set()

        # Check for different outcomes in same session
        for session in base_results.sessions + target_results.sessions:
            outcomes = {}
            for result in session.test_results:
                if result.nodeid in outcomes and outcomes[result.nodeid] != result.outcome:
                    flaky_tests.add(result.nodeid)
                outcomes[result.nodeid] = result.outcome

        # Check for different outcomes between sessions
        base_outcomes = self._collect_outcomes(base_results.sessions)
        target_outcomes = self._collect_outcomes(target_results.sessions)

        for nodeid in base_results.matched_nodeids | target_results.matched_nodeids:
            base = base_outcomes.get(nodeid)
            target = target_outcomes.get(nodeid)
            if base and target and base != target:
                flaky_tests.add(nodeid)

        return flaky_tests

    def _find_slower_tests(
        self, base_results: QueryResult, target_results: QueryResult
    ) -> Dict[str, float]:
        """Find tests that got slower and their percentage slowdown.

        Returns:
            Dict mapping test nodeid to percentage slowdown (positive values)
        """
        return {
            nodeid: change
            for nodeid, change in self._analyze_speed_changes(base_results, target_results).items()
            if change > 0
        }

    def _find_faster_tests(
        self, base_results: QueryResult, target_results: QueryResult
    ) -> Dict[str, float]:
        """Find tests that got faster and their percentage speedup.

        Returns:
            Dict mapping test nodeid to percentage speedup (negative values)
        """
        return {
            nodeid: change
            for nodeid, change in self._analyze_speed_changes(base_results, target_results).items()
            if change < 0
        }

    def _analyze_speed_changes(
        self, base_results: QueryResult, target_results: QueryResult
    ) -> Dict[str, float]:
        """Calculate percentage speed changes for all tests.

        Returns:
            Dict mapping test nodeid to percentage change:
            - Positive values indicate slowdown
            - Negative values indicate speedup
        """
        base_durations = self._collect_durations(base_results.sessions)
        target_durations = self._collect_durations(target_results.sessions)

        changes = {}
        for nodeid in base_results.matched_nodeids | target_results.matched_nodeids:
            base_time = base_durations.get(nodeid, 0)
            target_time = target_durations.get(nodeid, 0)

            if base_time > 0:  # Avoid division by zero
                change = ((target_time - base_time) / base_time) * 100
                changes[nodeid] = change
            elif target_time > 0:
                changes[nodeid] = float('inf')  # New test that wasn't in base

        return changes

    @staticmethod
    def _collect_durations(sessions: List[TestSession]) -> Dict[str, float]:
        """Collect test durations from sessions.

        Returns:
            Dict mapping test nodeid to duration in seconds
        """
        durations = {}
        for session in sessions:
            for result in session.test_results:
                durations[result.nodeid] = result.duration
        return durations
