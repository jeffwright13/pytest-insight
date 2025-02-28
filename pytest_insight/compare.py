from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
from statistics import mean

from pytest_insight.models import TestResult, TestSession

class ComparisonAnalyzer:
    """Compare test results between sessions or time periods."""

    @staticmethod
    def compare_sessions(
        sessions: List[TestSession],
        base_id: str,
        target_id: str,
        time_window: Optional[timedelta] = None
    ) -> Dict:
        """Compare two sessions within specified time windows."""
        now = datetime.now()
        cutoff = now - time_window if time_window else None

        # Filter both sessions by time window if specified
        filtered_sessions = sessions
        if cutoff:
            filtered_sessions = [s for s in sessions if s.session_start_time > cutoff]

        base_session = next((s for s in filtered_sessions if s.session_id == base_id), None)
        target_session = next((s for s in filtered_sessions if s.session_id == target_id), None)

        if not base_session or not target_session:
            raise ValueError(
                f"Sessions not found within the last {time_window}: "
                f"{'' if base_session else 'base session'}"
                f"{'' if target_session else 'target session'}"
            )

        base_results = {t.nodeid: t for t in base_session.test_results}
        target_results = {t.nodeid: t for t in target_session.test_results}

        all_tests = set(base_results.keys()) | set(target_results.keys())
        changes = []

        for test in all_tests:
            base = base_results.get(test)
            target = target_results.get(test)

            if not base:
                changes.append(("added", test, None, target.outcome))
            elif not target:
                changes.append(("removed", test, base.outcome, None))
            elif base.outcome != target.outcome:
                changes.append(("changed", test, base.outcome, target.outcome))

        return {
            "changes": changes,
            "total_tests": len(all_tests),
            "changed_tests": len(changes),
            "performance_changes": ComparisonAnalyzer._analyze_performance_changes(
                base_results, target_results
            )
        }

    @staticmethod
    def _analyze_performance_changes(
        base_results: Dict,
        target_results: Dict,
        threshold: float = 0.2
    ) -> List[Tuple[str, float, float]]:
        """Identify significant performance changes."""
        changes = []
        common_tests = set(base_results.keys()) & set(target_results.keys())

        for test in common_tests:
            base_duration = base_results[test].duration
            target_duration = target_results[test].duration
            if base_duration > 0 and abs(target_duration - base_duration) / base_duration > threshold:
                changes.append((test, base_duration, target_duration))

        return sorted(changes, key=lambda x: abs(x[2] - x[1]), reverse=True)

    @staticmethod
    def compare_periods(
        sessions: List[TestSession],
        period1_end: datetime,
        period2_end: datetime,
        days: int = 7
    ) -> Dict:
        """Compare test results between two time periods."""
        period1_start = period1_end - timedelta(days=days)
        period2_start = period2_end - timedelta(days=days)

        period1_sessions = [
            s for s in sessions
            if period1_start <= s.session_start_time <= period1_end
        ]
        period2_sessions = [
            s for s in sessions
            if period2_start <= s.session_start_time <= period2_end
        ]

        return ComparisonAnalyzer._compare_session_groups(
            period1_sessions,
            period2_sessions
        )

    @staticmethod
    def _compare_session_groups(
        group1: List[TestSession],
        group2: List[TestSession]
    ) -> Dict:
        """Compare two groups of sessions."""
        # Implementation for period comparison
        # ... add period comparison logic here ...
        return {}

class SUTComparator:
    """Compare test results between different SUTs."""

    @staticmethod
    def compare_suts(
        sessions: List[TestSession],
        sut1: str,
        sut2: str,
        days: Optional[int] = None
    ) -> Dict:
        """Compare test execution between two SUTs."""
        # Filter sessions by SUT and optionally by time
        sut1_sessions = [s for s in sessions if s.sut_name == sut1]
        sut2_sessions = [s for s in sessions if s.sut_name == sut2]

        if days:
            cutoff = datetime.now() - timedelta(days=days)
            sut1_sessions = [s for s in sut1_sessions if s.session_start_time > cutoff]
            sut2_sessions = [s for s in sut2_sessions if s.session_start_time > cutoff]

        # Get unique tests for each SUT
        sut1_tests = {t.nodeid for s in sut1_sessions for t in s.test_results}
        sut2_tests = {t.nodeid for s in sut2_sessions for t in s.test_results}

        return {
            "test_coverage": {
                "unique_to_sut1": sorted(sut1_tests - sut2_tests),
                "unique_to_sut2": sorted(sut2_tests - sut1_tests),
                "common": sorted(sut1_tests & sut2_tests),
                "total_sut1": len(sut1_tests),
                "total_sut2": len(sut2_tests)
            },
            "performance": SUTComparator._compare_performance(
                sut1_sessions, sut2_sessions, sut1_tests & sut2_tests
            ),
            "stability": SUTComparator._compare_stability(
                sut1_sessions, sut2_sessions, sut1_tests & sut2_tests
            ),
            "session_stats": {
                "sut1": SUTComparator._get_session_stats(sut1_sessions),
                "sut2": SUTComparator._get_session_stats(sut2_sessions)
            }
        }

    @staticmethod
    def _compare_performance(
        sut1_sessions: List[TestSession],
        sut2_sessions: List[TestSession],
        common_tests: Set[str]
    ) -> Dict:
        """Compare test performance between SUTs with safety checks."""
        sut1_durations = defaultdict(list)
        sut2_durations = defaultdict(list)

        for session in sut1_sessions:
            for test in session.test_results:
                if test.nodeid in common_tests:
                    sut1_durations[test.nodeid].append(test.duration)

        for session in sut2_sessions:
            for test in session.test_results:
                if test.nodeid in common_tests:
                    sut2_durations[test.nodeid].append(test.duration)

        differences = []
        for test in common_tests:
            if test in sut1_durations and test in sut2_durations:
                avg1 = mean(sut1_durations[test]) if sut1_durations[test] else 0
                avg2 = mean(sut2_durations[test]) if sut2_durations[test] else 0
                if avg1 > 0:  # Prevent division by zero
                    diff_pct = ((avg2 - avg1) / avg1) * 100
                    differences.append((test, avg1, avg2, diff_pct))

        return {
            "significant_differences": sorted(
                differences,
                key=lambda x: abs(x[3]),
                reverse=True
            )[:10]
        }

    @staticmethod
    def _compare_stability(
        sut1_sessions: List[TestSession],
        sut2_sessions: List[TestSession],
        common_tests: Set[str]
    ) -> Dict:
        """Compare test stability between SUTs with safety checks."""
        def get_failure_rates(sessions):
            failures = defaultdict(int)
            totals = defaultdict(int)
            failure_rates = {}

            for session in sessions:
                for test in session.test_results:
                    if test.nodeid in common_tests:
                        totals[test.nodeid] += 1
                        if test.outcome == "FAILED":
                            failures[test.nodeid] += 1

            # Safe division
            for test in common_tests:
                if test in totals and totals[test] > 0:
                    failure_rates[test] = failures[test] / totals[test]
                else:
                    failure_rates[test] = 0.0

            return failure_rates

        sut1_rates = get_failure_rates(sut1_sessions)
        sut2_rates = get_failure_rates(sut2_sessions)

        differences = []
        for test in common_tests:
            rate1 = sut1_rates.get(test, 0.0)
            rate2 = sut2_rates.get(test, 0.0)
            diff = rate2 - rate1
            if abs(diff) > 0.05:  # 5% threshold
                differences.append((test, rate1, rate2, diff * 100))

        return {
            "stability_differences": sorted(
                differences,
                key=lambda x: abs(x[3]),
                reverse=True
            )
        }

    @staticmethod
    def _get_session_stats(sessions: List[TestSession]) -> Dict:
        """Calculate aggregate session statistics."""
        if not sessions:
            return {}

        total_duration = sum(
            (s.session_stop_time - s.session_start_time).total_seconds()
            for s in sessions
        )
        return {
            "total_sessions": len(sessions),
            "avg_duration": total_duration / len(sessions),
            "total_tests": sum(len(s.test_results) for s in sessions),
            "date_range": (
                min(s.session_start_time for s in sessions),
                max(s.session_start_time for s in sessions)
            )
        }
