from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Callable

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
        new_passes: Test nodeids that passed in target but failed in base
        flaky_tests: Test nodeids that changed outcome between sessions
        slower_tests: Test nodeids that took longer in target
        faster_tests: Test nodeids that ran faster in target
        missing_tests: Test nodeids present in base but missing in target
        new_tests: Test nodeids present in target but missing in base
        outcome_changes: All outcome changes with (base_outcome, target_outcome)

    Note:
        Categories are NOT mutually exclusive. A test can belong to multiple categories:
        1. New failure + Flaky test (failed in target but not base)
        2. Performance regression + Warning (slow test with resource warning)
        3. New pass + Rerun (passed after multiple attempts)

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
    new_passes: List[str]  # Test nodeids that passed in target but failed in base
    flaky_tests: List[str]  # Test nodeids that changed outcome between sessions
    slower_tests: List[str]  # Test nodeids that took longer in target
    faster_tests: List[str]  # Test nodeids that ran faster in target
    missing_tests: List[str]  # Test nodeids present in base but missing in target
    new_tests: List[str]  # Test nodeids present in target but missing in base
    outcome_changes: Dict[str, Tuple[TestOutcome, TestOutcome]]  # All outcome changes

    def has_changes(self) -> bool:
        """Check if any differences were found between sessions."""
        return bool(
            self.new_failures
            or self.new_passes
            or self.flaky_tests
            or self.slower_tests
            or self.faster_tests
            or self.missing_tests
            or self.new_tests
        )


class Comparison:
    """Builder for test comparison operations.

    This class provides a fluent interface for comparing test sessions using the Query system.
    It exposes two Query objects (base_query and target_query) that can be configured
    independently, along with convenience methods that apply filters to both queries.

    Example usage:
        # Configure queries separately
        comparison = Comparison()
        comparison.base_query.for_sut("service-v1").in_last_days(7)
        comparison.target_query.for_sut("service-v2").in_last_days(7)
        result = comparison.execute()

        # Use convenience methods
        comparison = Comparison()
        result = comparison.between_suts("service-v1", "service-v2").execute()

        # Apply filters to both queries
        comparison = Comparison()
        comparison.apply_to_both(lambda q: q.in_last_days(7))
        result = comparison.execute()
    """

    def __init__(self, sessions: Optional[List[TestSession]] = None):
        """Initialize comparison with optional test sessions.

        Args:
            sessions: Optional list of test sessions to search through.
                     If not provided, loads sessions from default storage.
        """
        if sessions is None:
            storage = JSONStorage()
            sessions = storage.load_sessions()

        self.base_query = Query(sessions)
        self.target_query = Query(sessions)

        # Store sessions for later use in execute()
        self._sessions = sessions

        # Default performance thresholds
        self._slower_threshold = 1.2  # 20% slower
        self._faster_threshold = 0.8  # 20% faster

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
        self.base_query.for_sut(base_sut).with_session_id_pattern("base-*")
        self.target_query.for_sut(target_sut).with_session_id_pattern("target-*")
        return self

    def with_performance_thresholds(self, slower_percent: float = 20, faster_percent: float = 20) -> "Comparison":
        """Set custom performance thresholds for detecting slower and faster tests.

        Args:
            slower_percent: Percentage increase in duration to consider a test slower (default: 20%)
            faster_percent: Percentage decrease in duration to consider a test faster (default: 20%)

        Returns:
            Comparison instance for chaining.
        """
        if slower_percent <= 0:
            raise ComparisonError("Slower threshold percentage must be positive")
        if faster_percent <= 0 or faster_percent >= 100:
            raise ComparisonError("Faster threshold percentage must be between 0 and 100")

        self._slower_threshold = 1 + (slower_percent / 100)
        self._faster_threshold = 1 - (faster_percent / 100)
        return self

    def apply_to_both(self, query_modifier: Callable[[Query], Query]) -> "Comparison":
        """Apply the same filter function to both base and target queries.

        This is a flexible way to apply any Query method to both queries at once.

        Args:
            query_modifier: A function that takes a Query and returns a Query

        Example:
            # Apply in_last_days to both queries
            comparison.apply_to_both(lambda q: q.in_last_days(7))

            # Apply complex filters to both queries
            comparison.apply_to_both(lambda q: q.filter_by_test()
                                              .with_duration_between(1.0, 10.0)
                                              .apply())

        Returns:
            Comparison instance for chaining.
        """
        query_modifier(self.base_query)
        query_modifier(self.target_query)
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
            self.base_query.with_session_tag(key, value)
        for key, value in target_env.items():
            self.target_query.with_session_tag(key, value)
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
            self.base_query._session_filters or self.target_query._session_filters
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
            # Use the stored sessions from initialization
            sessions_to_query = self._sessions

            # Use queries to find sessions
            base_results = self.base_query.execute(sessions_to_query)
            target_results = self.target_query.execute(sessions_to_query)

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
        new_passes = []
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

                # A test can be both flaky and a new failure/new pass
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
                    new_passes.append(nodeid)

            # Track performance changes (independent of outcome changes)
            # Use configurable thresholds
            if target_test.duration > base_test.duration * self._slower_threshold:
                slower_tests.append(nodeid)
            elif target_test.duration < base_test.duration * self._faster_threshold:
                faster_tests.append(nodeid)

        return ComparisonResult(
            base_results=base_results,
            target_results=target_results,
            base_session=base_session,
            target_session=target_session,
            new_failures=new_failures,
            new_passes=new_passes,
            flaky_tests=flaky_tests,
            slower_tests=slower_tests,
            faster_tests=faster_tests,
            missing_tests=missing_tests,
            new_tests=new_tests,
            outcome_changes=outcome_changes,
        )
