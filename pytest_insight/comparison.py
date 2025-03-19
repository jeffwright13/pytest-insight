from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from pytest_insight.models import TestOutcome, TestSession
from pytest_insight.query import Query, QueryResult
from pytest_insight.storage import JSONStorage


class ComparisonError(Exception):
    """Base exception for Comparison-related errors."""

    pass


@dataclass
class ComparisonResult:
    """Results of comparing test sessions.

    Properties:
        base_results: QueryResult for base sessions
        target_results: QueryResult for target sessions
        base_session: Selected base session for comparison
        target_session: Selected target session for comparison
        new_failures: Test nodeids that failed in target but passed in base
        fixed_tests: Test nodeids that passed in target but failed in base
        flaky_tests: Test nodeids that changed outcome between sessions
        slower_tests: Test nodeids that took longer in target
        faster_tests: Test nodeids that ran faster in target
        missing_tests: Test nodeids present in base but missing in target
        new_tests: Test nodeids present in target but missing in base
        outcome_changes: All outcome changes with (base_outcome, target_outcome)
        new_passes: Alias for fixed_tests (nodeids that passed in target but failed in base)

    Note:
        Categories are NOT mutually exclusive. A test can belong to multiple categories:
        1. New failure + Flaky test (failed in target but not base)
        2. Performance regression + Warning (slow test with resource warning)
        3. Fixed test + Rerun (passed after multiple attempts)

        The Query system preserves full session context to make it easy to:
        1. Track all test outcomes, not just failures
        2. See relationships between test results
        3. Analyze patterns across categories
        4. Identify correlated issues
    """

    base_results: "QueryResult"
    target_results: "QueryResult"
    base_session: TestSession
    target_session: TestSession
    new_failures: List[str]  # Test nodeids that failed in target but passed in base
    fixed_tests: List[str]  # Test nodeids that passed in target but failed in base
    flaky_tests: List[str]  # Test nodeids that changed outcome between sessions
    slower_tests: List[str]  # Test nodeids that took longer in target
    faster_tests: List[str]  # Test nodeids that ran faster in target
    missing_tests: List[str]  # Test nodeids present in base but missing in target
    new_tests: List[str]  # Test nodeids present in target but missing in base
    outcome_changes: Dict[str, Tuple[TestOutcome, TestOutcome]]  # All outcome changes

    @property
    def has_changes(self) -> bool:
        """Check if any differences were found between sessions."""
        return bool(
            self.new_failures
            or self.fixed_tests
            or self.flaky_tests
            or self.slower_tests
            or self.faster_tests
            or self.missing_tests
            or self.new_tests
        )

    @property
    def new_passes(self) -> List[str]:
        """Alias for fixed_tests (nodeids that passed in target but failed in base)."""
        return self.fixed_tests


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

    def in_date_window(self, start_date: datetime, end_date: datetime) -> "Comparison":
        """Filter sessions within a specific date window.

        This is a session-level filter that operates on session_start_time.
        It preserves full session context while filtering by date range.

        Args:
            start_date: Start of date window (inclusive)
            end_date: End of date window (inclusive)

        Returns:
            Comparison instance for chaining.

        Raises:
            ComparisonError: If start_date is after end_date.
        """
        if start_date > end_date:
            raise ComparisonError("Start date must be before end date")

        # Apply date window to both base and target queries
        self._base_query._session_filters.append(
            lambda s: start_date <= s.session_start_time <= end_date
        )
        self._target_query._session_filters.append(
            lambda s: start_date <= s.session_start_time <= end_date
        )
        return self

    def with_test_pattern(self, pattern: str, *, field_name: str) -> "Comparison":
        """Filter tests by pattern match.

        This is a test-level filter that:
        1. Uses simple substring matching on the specified field
        2. Returns sessions containing ANY matching test
        3. Preserves ALL tests in matching sessions
        4. Maintains session context (metadata, relationships)

        Args:
            pattern: Pattern to match against test field
            field_name: Name of the test field to match against (e.g. 'nodeid', 'caplog')

        Returns:
            Comparison instance for chaining.
        """
        self._base_query.filter_by_test().with_pattern(
            pattern, field_name=field_name
        ).apply()
        self._target_query.filter_by_test().with_pattern(
            pattern, field_name=field_name
        ).apply()
        return self

    def with_duration_threshold(self, min_secs: float) -> "Comparison":
        """Filter tests by minimum duration.

        Args:
            min_secs: Minimum duration in seconds.

        Returns:
            Comparison instance for chaining.
        """
        self._base_query.filter_by_test().with_duration_between(
            min_secs, float("inf")
        ).apply()
        self._target_query.filter_by_test().with_duration_between(
            min_secs, float("inf")
        ).apply()
        return self

    def only_failures(self) -> "Comparison":
        """Filter to show only failed tests.

        Returns:
            Comparison instance for chaining.
        """
        self._base_query.filter_by_test().with_outcome(TestOutcome.FAILED).apply()
        self._target_query.filter_by_test().with_outcome(TestOutcome.FAILED).apply()
        return self

    def exclude_flaky(self) -> "Comparison":
        """Filter out flaky tests (tests with reruns).

        Returns:
            Comparison instance for chaining.
        """
        self._base_query.with_reruns(False)
        self._target_query.with_reruns(False)
        return self

    def with_environment(
        self, base_env: Dict[str, str], target_env: Dict[str, str]
    ) -> "Comparison":
        """Filter sessions by environment tags.

        Args:
            base_env: Environment tags to match in base sessions.
            target_env: Environment tags to match in target sessions.

        Returns:
            Comparison instance for chaining.
        """
        for key, value in base_env.items():
            self._base_query.with_session_tag(key, value)
        for key, value in target_env.items():
            self._target_query.with_session_tag(key, value)
        return self

    def execute(self, sessions: Optional[List[TestSession]] = None) -> ComparisonResult:
        """Execute comparison between base and target sessions.

        Args:
            sessions: Optional list of exactly two sessions to compare directly.
                     If provided, ignores any previously configured filters.

        Returns:
            ComparisonResult containing categorized test differences.
            Tests can belong to multiple categories (e.g., both flaky and new failure).

        Raises:
            ComparisonError: If no sessions match or if validation fails.

        Example:
            # Using queries (recommended):
            comparison = Comparison()
            result = comparison.between_suts("service-v1", "service-v2").execute()

            # Direct comparison:
            result = comparison.execute([base_session, target_session])
        """
        if not sessions and not (
            self._base_query._session_filters or self._target_query._session_filters
        ):
            raise ComparisonError("No sessions provided and no filters configured")

        if sessions:
            if len(sessions) != 2:
                raise ComparisonError("Must provide exactly 2 sessions to compare")
            base_session, target_session = sessions

            # Validate session ID patterns
            if not base_session.session_id.startswith("base-"):
                raise ComparisonError(
                    f"Base session ID must start with 'base-', got: {base_session.session_id}"
                )
            if not target_session.session_id.startswith("target-"):
                raise ComparisonError(
                    f"Target session ID must start with 'target-', got: {target_session.session_id}"
                )

            # Create QueryResults for direct session comparison
            base_results = Query().execute([base_session])
            target_results = Query().execute([target_session])
        else:
            # Use queries to find sessions
            base_results = self._base_query.execute()
            target_results = self._target_query.execute()

            if not base_results.sessions or not target_results.sessions:
                raise ComparisonError("No matching base and target sessions found")

            # Use most recent sessions if multiple matches
            base_session = max(
                base_results.sessions, key=lambda s: s.session_start_time
            )
            target_session = max(
                target_results.sessions, key=lambda s: s.session_start_time
            )

        # Build nodeid maps for efficient lookup
        base_tests = {t.nodeid: t for t in base_session.test_results}
        target_tests = {t.nodeid: t for t in target_session.test_results}

        # Find all test changes
        new_failures = []
        fixed_tests = []
        flaky_tests = []
        slower_tests = []
        faster_tests = []
        outcome_changes = {}

        # Track missing and new tests
        missing_tests = list(set(base_tests.keys()) - set(target_tests.keys()))
        new_tests = list(set(target_tests.keys()) - set(base_tests.keys()))

        # Compare common tests
        common_tests = set(base_tests.keys()) & set(target_tests.keys())
        for nodeid in common_tests:
            base_test = base_tests[nodeid]
            target_test = target_tests[nodeid]

            # Track all outcome changes
            if base_test.outcome != target_test.outcome:
                outcome_changes[nodeid] = (base_test.outcome, target_test.outcome)

                # A test can be both flaky and a new failure/fixed test
                flaky_tests.append(nodeid)

                if (
                    base_test.outcome == TestOutcome.PASSED
                    and target_test.outcome == TestOutcome.FAILED
                ):
                    new_failures.append(nodeid)
                elif (
                    base_test.outcome == TestOutcome.FAILED
                    and target_test.outcome == TestOutcome.PASSED
                ):
                    fixed_tests.append(nodeid)

            # Track performance changes (independent of outcome changes)
            if target_test.duration > base_test.duration * 1.2:  # 20% slower
                slower_tests.append(nodeid)
            elif target_test.duration < base_test.duration * 0.8:  # 20% faster
                faster_tests.append(nodeid)

        return ComparisonResult(
            base_results=base_results,
            target_results=target_results,
            base_session=base_session,
            target_session=target_session,
            new_failures=new_failures,
            fixed_tests=fixed_tests,
            flaky_tests=flaky_tests,
            slower_tests=slower_tests,
            faster_tests=faster_tests,
            missing_tests=missing_tests,
            new_tests=new_tests,
            outcome_changes=outcome_changes,
        )
