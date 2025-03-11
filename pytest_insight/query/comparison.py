from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from pytest_insight.models import TestOutcome, TestResult, TestSession
from pytest_insight.query.query import Query
from pytest_insight.storage import JSONStorage


class ComparisonError(Exception):
    """Base exception for Comparison-related errors."""
    pass


@dataclass
class ComparisonResult:
    """Results of comparing test sessions."""
    base_session: TestSession
    target_session: TestSession
    new_failures: List[TestResult]  # Tests that failed in target but passed in base
    fixed_tests: List[TestResult]   # Tests that passed in target but failed in base
    flaky_tests: List[TestResult]   # Tests that changed outcome between sessions
    slower_tests: List[TestResult]  # Tests that took longer in target
    missing_tests: List[str]        # Tests present in base but missing in target
    new_tests: List[str]           # Tests present in target but missing in base
    outcome_changes: Dict[str, Tuple[TestOutcome, TestOutcome]]  # All outcome changes


class Comparison:
    """Builder for test comparison operations."""

    def __init__(self, sessions: Optional[List[TestSession]] = None):
        """Initialize comparison with optional test sessions.

        Args:
            sessions: Optional list of test sessions to search through.
                     If not provided, loads sessions from default storage.
        """
        if sessions is None:
            storage = JSONStorage()
            sessions = storage.load_sessions()

        self._base_query = Query(sessions)
        self._target_query = Query(sessions)

    def between_suts(self, base_sut: str, target_sut: str) -> "Comparison":
        """Compare between two SUTs.

        This automatically applies proper base/target session patterns
        to ensure consistent test categorization.

        Args:
            base_sut: Name of the base SUT
            target_sut: Name of the target SUT

        Example:
            comparison = Comparison()
            result = comparison.between_suts("service-v1", "service-v2").execute()
        """
        self._base_query.for_sut(base_sut).with_session_id_pattern("base-*")
        self._target_query.for_sut(target_sut).with_session_id_pattern("target-*")
        return self

    def in_last_days(self, days: int) -> "Comparison":
        """Filter both base and target sessions from last N days."""
        self._base_query.in_last_days(days)
        self._target_query.in_last_days(days)
        return self

    def execute(self, sessions: Optional[List[TestSession]] = None) -> ComparisonResult:
        """Execute comparison between base and target sessions.

        Args:
            sessions: Optional list of exactly two sessions to compare directly.
                     If provided, ignores any previously configured filters.

        Returns:
            ComparisonResult containing categorized test differences.
            Tests can belong to multiple categories (e.g., both flaky and new failure).

        Example:
            # Using queries (recommended):
            comparison = Comparison()
            result = comparison.between_suts("service-v1", "service-v2").execute()

            # Direct comparison:
            result = comparison.execute([base_session, target_session])
        """
        if sessions:
            if len(sessions) != 2:
                raise ComparisonError("Must provide exactly 2 sessions to compare")
            base_session, target_session = sessions

            # Validate session ID patterns
            if not base_session.session_id.startswith("base-"):
                raise ComparisonError(f"Base session ID must start with 'base-', got: {base_session.session_id}")
            if not target_session.session_id.startswith("target-"):
                raise ComparisonError(f"Target session ID must start with 'target-', got: {target_session.session_id}")
        else:
            # Use queries to find sessions
            base_results = self._base_query.execute()
            target_results = self._target_query.execute()

            if not base_results.sessions or not target_results.sessions:
                raise ComparisonError("No matching base and target sessions found")

            # Use most recent sessions if multiple matches
            base_session = max(base_results.sessions, key=lambda s: s.session_start_time)
            target_session = max(target_results.sessions, key=lambda s: s.session_start_time)

        # Build nodeid maps for efficient lookup
        base_results = {t.nodeid: t for t in base_session.test_results}
        target_results = {t.nodeid: t for t in target_session.test_results}

        # Find all test changes
        new_failures = []
        fixed_tests = []
        flaky_tests = []
        slower_tests = []
        outcome_changes = {}

        # Track missing and new tests
        missing_tests = []
        new_tests = []

        # Compare common tests
        common_tests = set(base_results.keys()) & set(target_results.keys())
        for nodeid in common_tests:
            base_test = base_results[nodeid]
            target_test = target_results[nodeid]

            # Track all outcome changes
            if base_test.outcome != target_test.outcome:
                outcome_changes[nodeid] = (base_test.outcome, target_test.outcome)

                # A test can be both flaky and a new failure/fixed test
                flaky_tests.append(target_test)

                if base_test.outcome == TestOutcome.PASSED and target_test.outcome == TestOutcome.FAILED:
                    new_failures.append(target_test)
                elif base_test.outcome == TestOutcome.FAILED and target_test.outcome == TestOutcome.PASSED:
                    fixed_tests.append(target_test)

            # Track performance changes (independent of outcome changes)
            if target_test.duration > base_test.duration * 1.2:  # 20% slower
                slower_tests.append(target_test)

        # Find missing and new tests
        missing_tests = list(set(base_results.keys()) - set(target_results.keys()))
        new_tests = list(set(target_results.keys()) - set(base_results.keys()))

        return ComparisonResult(
            base_session=base_session,
            target_session=target_session,
            new_failures=new_failures,
            fixed_tests=fixed_tests,
            flaky_tests=flaky_tests,
            slower_tests=slower_tests,
            missing_tests=missing_tests,
            new_tests=new_tests,
            outcome_changes=outcome_changes
        )
