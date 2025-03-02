"""Dimensional comparison of test sessions."""

from typing import Dict, List

from pytest_insight.dimensions import ComparisonDimension
from pytest_insight.models import TestOutcome, TestSession


class DimensionalComparator:
    """Compare test sessions using flexible dimensions."""

    def __init__(self, dimension: ComparisonDimension):
        self.dimension = dimension

    def compare(self, sessions: List[TestSession], base_key: str, target_key: str) -> Dict:
        """Compare sessions between two dimension keys.

        Args:
            sessions: List of test sessions to compare
            base_key: Base key in the dimension (e.g. SUT name or time window)
            target_key: Target key to compare against base

        Returns:
            Dictionary containing comparison results:
            {
                'base': {
                    'total_tests': int,
                    'passed': int,
                    'failed': int,
                    'skipped': int,
                    'duration': float,
                },
                'target': { same as base },
                'differences': {
                    'new_tests': List[str],  # Tests in target but not base
                    'removed_tests': List[str],  # Tests in base but not target
                    'status_changes': List[Dict],  # Tests that changed status
                    'duration_changes': List[Dict],  # Tests with significant duration changes
                }
            }
        """
        grouped = self.dimension.group_sessions(sessions)
        base_sessions = grouped.get(base_key, [])
        target_sessions = grouped.get(target_key, [])

        if not base_sessions or not target_sessions:
            return {"error": f"No sessions found for {'base' if not base_sessions else 'target'}"}

        return self._analyze_differences(base_sessions, target_sessions)

    def _analyze_differences(self, base_sessions: List[TestSession], target_sessions: List[TestSession]) -> Dict:
        """Analyze differences between base and target sessions."""
        # Collect all test results from each group
        base_tests = {}
        for session in base_sessions:
            for result in session.test_results:
                base_tests[result.nodeid] = result

        target_tests = {}
        for session in target_sessions:
            for result in session.test_results:
                target_tests[result.nodeid] = result

        # Find differences
        new_tests = [nodeid for nodeid in target_tests if nodeid not in base_tests]
        removed_tests = [nodeid for nodeid in base_tests if nodeid not in target_tests]

        # Find status changes
        status_changes = []
        for nodeid in set(base_tests) & set(target_tests):
            base_result = base_tests[nodeid]
            target_result = target_tests[nodeid]
            if base_result.outcome != target_result.outcome:
                status_changes.append(
                    {
                        "nodeid": nodeid,
                        "base_status": base_result.outcome.value,
                        "target_status": target_result.outcome.value,
                    }
                )

        # Find significant duration changes (>20% difference)
        duration_changes = []
        for nodeid in set(base_tests) & set(target_tests):
            base_result = base_tests[nodeid]
            target_result = target_tests[nodeid]
            if not (base_result.duration and target_result.duration):
                continue

            diff_pct = abs(base_result.duration - target_result.duration) / base_result.duration * 100
            if diff_pct > 20:
                duration_changes.append(
                    {
                        "nodeid": nodeid,
                        "base_duration": base_result.duration,
                        "target_duration": target_result.duration,
                        "percent_change": diff_pct,
                    }
                )

        # Collect summary stats for all sessions in each group
        def group_stats(sessions: List[TestSession]) -> Dict:
            # First, collect all results by nodeid within this group
            results_by_nodeid = {}
            for session in sessions:
                for result in session.test_results:
                    # Keep the most recent result for each nodeid within this group
                    if (
                        result.nodeid not in results_by_nodeid
                        or result.start_time > results_by_nodeid[result.nodeid].start_time
                    ):
                        results_by_nodeid[result.nodeid] = result

            # Now calculate stats using the unique results from this session group
            total_tests = len(results_by_nodeid)
            passed = sum(1 for r in results_by_nodeid.values() if r.outcome == TestOutcome.PASSED)
            failed = sum(1 for r in results_by_nodeid.values() if r.outcome == TestOutcome.FAILED)
            skipped = sum(1 for r in results_by_nodeid.values() if r.outcome == TestOutcome.SKIPPED)
            duration = sum(r.duration for r in results_by_nodeid.values())

            return {
                "total_tests": total_tests,
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "duration": duration,
            }

        return {
            "base": group_stats(base_sessions),
            "target": group_stats(target_sessions),
            "differences": {
                "new_tests": new_tests,
                "removed_tests": removed_tests,
                "status_changes": status_changes,
                "duration_changes": duration_changes,
            },
        }
