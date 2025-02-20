from typing import Dict, Any, Optional, List
from datetime import timedelta, datetime
from pytest_insight.core.analyzer import InsightAnalyzer, SessionFilter
from pytest_insight.storage import BaseStorage

class InsightAPI:
    """Public API for UI-agnostic test analytics."""

    def __init__(self, storage: BaseStorage):
        self._analyzer = InsightAnalyzer(storage)

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get analytics summary for a session."""
        session = self._analyzer.storage.get_session_by_id(session_id)
        if not session:
            return {}

        return {
            "metrics": self._analyzer.calculate_test_metrics(session.test_results),
            "trends": self._analyzer.detect_trends(session.test_results),
            "patterns": self._analyzer.detect_patterns(session.test_results)
        }

    def get_trend_analysis(self, timespan: timedelta) -> Dict[str, Any]:
        """Get trend analysis for a time period."""
        results = self._analyzer.get_test_results(
            SessionFilter(timespan=timespan)
        )

        if not results:
            return {
                "duration_trend": {"trend": "insufficient_data", "data_points": []},
                "outcome_trend": {"trend": "insufficient_data", "data_points": []},
                "failure_rate": 0.0
            }

        return {
            "duration_trend": self._analyzer.detect_trends(results, metric="duration"),
            "outcome_trend": self._analyzer.detect_trends(results, metric="outcome"),
            "failure_rate": self._analyzer.calculate_failure_rate(results)
        }

    def get_failure_patterns(self, filters: SessionFilter) -> Dict[str, Any]:
        """Get failure pattern analysis."""
        return self._analyzer.detect_patterns(
            self._analyzer.get_test_results(filters)
        )

    def get_sessions(self, filters: Optional[SessionFilter] = None) -> List[Dict[str, Any]]:
        """Get filtered session summaries."""
        sessions = self._analyzer.get_sessions(filters)
        return [
            {
                "session_id": session.session_id,
                "sut_name": session.sut_name,
                "metrics": self._analyzer.calculate_test_metrics(session.test_results),
                "trends": self._analyzer.detect_trends(session.test_results),
                "patterns": self._analyzer.detect_patterns(session.test_results)
            }
            for session in sessions
        ]

    def get_latest_session(self) -> Optional[Dict[str, Any]]:
        """Get summary of most recent session."""
        session = self._analyzer.storage.get_last_session()
        if not session:
            return None
        return self.get_sessions([session])[0]

    def analyze_health(self, sut: str) -> Dict[str, Any]:
        """Get health analysis for a SUT."""
        sessions = self._analyzer.get_sessions(SessionFilter(sut=sut))
        results = []
        for session in sessions:
            results.extend(session.test_results)

        return {
            "health_scores": self._analyzer.calculate_health_scores(results),
            "warning_patterns": self._analyzer.analyze_warnings(results),
            "failure_rate": self._analyzer.calculate_failure_rate(results)
        }

    def get_test_history(self, nodeid: str) -> Dict[str, Any]:
        """Get execution history for a specific test."""
        results = self._analyzer.get_test_results(SessionFilter(nodeid=nodeid))
        return {
            "total_runs": len(results),
            "failure_rate": self._analyzer.calculate_failure_rate(results),
            "duration_trend": self._analyzer.detect_trends(results, metric="duration"),
            "warnings": [r for r in results if r.has_warning]
        }

    def compare_suts(self, sut1: str, sut2: str) -> Dict[str, Any]:
        """Compare test results between two SUTs."""
        filters1 = SessionFilter(sut=sut1)
        filters2 = SessionFilter(sut=sut2)

        results1 = self._analyzer.get_test_results(filters1)
        results2 = self._analyzer.get_test_results(filters2)

        return {
            "metrics": self._analyzer.compare_metrics(results1, results2),
            "stability": self._analyzer.compare_stability(results1, results2),
            "duration": self._analyzer.compare_durations(results1, results2)
        }

    def compare_periods(
        self,
        base_date: datetime,
        target_date: datetime,
        days: int
    ) -> Dict[str, Any]:
        """Compare test results between two time periods."""
        base_filter = SessionFilter(
            timespan=timedelta(days=days),
            end_time=base_date
        )
        target_filter = SessionFilter(
            timespan=timedelta(days=days),
            end_time=target_date
        )

        base_results = self._analyzer.get_test_results(base_filter)
        target_results = self._analyzer.get_test_results(target_filter)

        return {
            "metrics": self._analyzer.compare_metrics(base_results, target_results),
            "stability": self._analyzer.compare_stability(base_results, target_results),
            "duration": self._analyzer.compare_durations(base_results, target_results),
            "timespan": {
                "base": {"start": base_date - timedelta(days=days), "end": base_date},
                "target": {"start": target_date - timedelta(days=days), "end": target_date}
            }
        }

"""
# Test Analytics API

## Session Analysis
- `get_session_summary(session_id: str) -> Dict[str, Any]`
  - Returns metrics, trends, and patterns for a specific session
  - Returns empty dict if session not found

- `get_latest_session() -> Optional[Dict[str, Any]]`
  - Returns most recent session summary
  - Returns None if no sessions exist

## Trend Analysis
- `get_trend_analysis(timespan: timedelta) -> Dict[str, Any]`
  - Returns duration trends, outcome trends, and failure rates
  - Timespan controls how far back to analyze

## Failure Analysis
- `get_failure_patterns(filters: SessionFilter) -> Dict[str, Any]`
  - Returns detected failure patterns
  - Filterable by SUT, timespan, nodeid

## Health Analysis
- `analyze_health(sut: str) -> Dict[str, Any]`
  - Returns health scores, warning patterns, failure rates
  - SUT-specific analysis

## Test History
- `get_test_history(nodeid: str) -> Dict[str, Any]`
  - Returns execution history for specific test
  - Includes runs, failure rate, duration trends

## Comparison Analysis
- `compare_suts(sut1: str, sut2: str) -> Dict[str, Any]`
  - Compares metrics between two SUTs
  - Returns metrics, stability, duration comparisons

- `compare_periods(base_date: datetime, target_date: datetime, days: int) -> Dict[str, Any]`
  - Compares metrics between two time periods
  - Returns metrics, stability, duration comparisons
"""
