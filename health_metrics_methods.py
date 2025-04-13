"""Health metrics methods to be added to SessionAnalysis class.

This file contains the implementation of four new health metrics methods:
1. top_failing_tests - Identifies tests that fail most frequently
2. regression_rate - Calculates percentage of tests that regressed
3. longest_running_tests - Identifies tests with longest execution times
4. test_suite_duration_trend - Analyzes trends in test suite execution time

Copy these methods into the SessionAnalysis class in pytest_insight/core/analysis.py
"""

from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Any

from pytest_insight.core.models import TestOutcome

def top_failing_tests(self, days=None, limit=10):
    """Identify tests that fail most frequently.
    
    Analyzes test results across sessions to identify tests with the highest
    failure rates and counts.
    
    Args:
        days: Optional number of days to look back
        limit: Maximum number of tests to return (default: 10)
        
    Returns:
        Dictionary containing:
        - top_failing: List of tests with highest failure rates
        - total_failures: Total number of test failures across all sessions
    """
    sessions = self._get_sessions(days)
    if not sessions:
        return {"top_failing": [], "total_failures": 0}
        
    # Track test failures across all sessions
    test_failures = defaultdict(lambda: {"failure_count": 0, "total_runs": 0})
    total_failures = 0
    
    # Analyze test results from all sessions
    for session in sessions:
        if not hasattr(session, "test_results") or not session.test_results:
            continue
            
        # Process regular test results
        for test in session.test_results:
            if not hasattr(test, "nodeid") or not test.nodeid:
                continue
                
            nodeid = test.nodeid
            test_failures[nodeid]["total_runs"] += 1
            
            if hasattr(test, "outcome") and test.outcome == TestOutcome.FAILED:
                test_failures[nodeid]["failure_count"] += 1
                total_failures += 1
                
        # Process rerun groups if available
        if hasattr(session, "rerun_test_groups") and session.rerun_test_groups:
            for rerun_group in session.rerun_test_groups:
                nodeid = rerun_group.nodeid
                
                # Count the initial failure
                if rerun_group.tests and len(rerun_group.tests) > 0:
                    # Only count if we haven't already counted this test in regular results
                    if nodeid not in test_failures:
                        test_failures[nodeid]["total_runs"] += 1
                        
                    # Check if the first run failed (typical for rerun groups)
                    first_test = rerun_group.tests[0]
                    if hasattr(first_test, "outcome") and first_test.outcome == TestOutcome.FAILED:
                        test_failures[nodeid]["failure_count"] += 1
                        total_failures += 1
    
    # Calculate failure rates and prepare results
    results = []
    for nodeid, data in test_failures.items():
        failure_count = data["failure_count"]
        total_runs = data["total_runs"]
        
        # Only include tests that have failed at least once
        if failure_count > 0:
            failure_rate = failure_count / total_runs if total_runs > 0 else 0
            results.append({
                "nodeid": nodeid,
                "failure_count": failure_count,
                "total_runs": total_runs,
                "failure_rate": failure_rate
            })
    
    # Sort by failure count (descending), then by failure rate (descending)
    sorted_results = sorted(
        results,
        key=lambda x: (x["failure_count"], x["failure_rate"]),
        reverse=True
    )
    
    return {
        "top_failing": sorted_results[:limit],
        "total_failures": total_failures
    }

def regression_rate(self, days=None):
    """Calculate the regression rate of tests.
    
    Analyzes test results across sessions to identify tests that have regressed
    (changed from passing to failing) and calculates the overall regression rate.
    
    Args:
        days: Optional number of days to look back
        
    Returns:
        Dictionary containing:
        - regression_rate: Percentage of tests that have regressed
        - regressed_tests: List of tests that have regressed
    """
    sessions = self._get_sessions(days)
    if not sessions or len(sessions) < 2:
        return {"regression_rate": 0.0, "regressed_tests": []}
        
    # Sort sessions by timestamp to analyze chronologically
    sorted_sessions = sorted(
        sessions,
        key=lambda s: s.session_start_time if hasattr(s, "session_start_time") else datetime.min
    )
    
    # Track test outcomes across sessions
    test_history = {}
    
    # First pass: build test history
    for session in sorted_sessions:
        if not hasattr(session, "test_results") or not session.test_results:
            continue
            
        session_timestamp = session.session_start_time if hasattr(session, "session_start_time") else datetime.now()
        
        # Process regular test results
        for test in session.test_results:
            if not hasattr(test, "nodeid") or not test.nodeid:
                continue
                
            nodeid = test.nodeid
            outcome = test.outcome if hasattr(test, "outcome") else None
            
            if nodeid not in test_history:
                test_history[nodeid] = []
                
            # Add this outcome to the test's history
            test_history[nodeid].append((session_timestamp, outcome))
            
        # Process rerun groups if available
        if hasattr(session, "rerun_test_groups") and session.rerun_test_groups:
            for rerun_group in session.rerun_test_groups:
                nodeid = rerun_group.nodeid
                
                # For rerun groups, use the final outcome
                if rerun_group.tests and len(rerun_group.tests) > 0:
                    final_test = rerun_group.tests[-1]
                    final_outcome = final_test.outcome if hasattr(final_test, "outcome") else None
                    
                    if nodeid not in test_history:
                        test_history[nodeid] = []
                        
                    # Add the final outcome to the test's history
                    test_history[nodeid].append((session_timestamp, final_outcome))
    
    # Second pass: identify regressions
    regressed_tests = []
    total_tests_with_multiple_runs = 0
    
    for nodeid, history in test_history.items():
        # Skip tests with fewer than 2 runs
        if len(history) < 2:
            continue
            
        total_tests_with_multiple_runs += 1
        
        # Get the most recent two outcomes
        history.sort(key=lambda x: x[0])  # Sort by timestamp
        prev_outcome = history[-2][1]
        current_outcome = history[-1][1]
        
        # Check for regression (passing to failing)
        if (prev_outcome == TestOutcome.PASSED and current_outcome == TestOutcome.FAILED):
            regressed_tests.append({
                "nodeid": nodeid,
                "previous": "passed",
                "current": "failed",
                "timestamp": history[-1][0]
            })
    
    # Calculate regression rate
    regression_rate = len(regressed_tests) / total_tests_with_multiple_runs if total_tests_with_multiple_runs > 0 else 0.0
    
    # Sort regressed tests by timestamp (most recent first)
    sorted_regressed_tests = sorted(
        regressed_tests,
        key=lambda x: x["timestamp"],
        reverse=True
    )
    
    return {
        "regression_rate": regression_rate,
        "regressed_tests": sorted_regressed_tests
    }

def longest_running_tests(self, days=None, limit=10):
    """Identify the longest running tests.
    
    Analyzes test durations across sessions to identify the tests that take
    the longest time to execute on average.
    
    Args:
        days: Optional number of days to look back
        limit: Maximum number of tests to return (default: 10)
        
    Returns:
        Dictionary containing:
        - longest_tests: List of tests with highest average durations
    """
    sessions = self._get_sessions(days)
    if not sessions:
        return {"longest_tests": []}
        
    # Track test durations across all sessions
    test_durations = defaultdict(lambda: {"durations": []})
    
    # Analyze test results from all sessions
    for session in sessions:
        if not hasattr(session, "test_results") or not session.test_results:
            continue
            
        # Process regular test results
        for test in session.test_results:
            if not hasattr(test, "nodeid") or not test.nodeid or not hasattr(test, "duration"):
                continue
                
            nodeid = test.nodeid
            duration = test.duration
            
            # Skip tests with zero or negative duration
            if duration <= 0:
                continue
                
            test_durations[nodeid]["durations"].append(duration)
            
        # Process rerun groups if available
        if hasattr(session, "rerun_test_groups") and session.rerun_test_groups:
            for rerun_group in session.rerun_test_groups:
                nodeid = rerun_group.nodeid
                
                # Add durations from all runs
                for test in rerun_group.tests:
                    if hasattr(test, "duration") and test.duration > 0:
                        test_durations[nodeid]["durations"].append(test.duration)
    
    # Calculate average durations and prepare results
    results = []
    for nodeid, data in test_durations.items():
        durations = data["durations"]
        
        # Only include tests with at least one valid duration
        if durations:
            avg_duration = sum(durations) / len(durations)
            max_duration = max(durations)
            min_duration = min(durations)
            
            results.append({
                "nodeid": nodeid,
                "avg_duration": avg_duration,
                "max_duration": max_duration,
                "min_duration": min_duration,
                "runs": len(durations)
            })
    
    # Sort by average duration (descending)
    sorted_results = sorted(
        results,
        key=lambda x: x["avg_duration"],
        reverse=True
    )
    
    return {
        "longest_tests": sorted_results[:limit]
    }

def test_suite_duration_trend(self, days=None, window_size=5):
    """Analyze trends in test suite execution time.
    
    Analyzes the total duration of test sessions over time to identify
    trends in test suite execution time.
    
    Args:
        days: Optional number of days to look back
        window_size: Size of the window for trend analysis (default: 5)
        
    Returns:
        Dictionary containing:
        - trend: Dictionary with direction and change percentage
        - significant: Boolean indicating if the trend is significant
        - durations: List of session durations
    """
    sessions = self._get_sessions(days)
    if not sessions or len(sessions) < 2:
        return {
            "trend": {"direction": "stable", "change": 0},
            "significant": False,
            "durations": []
        }
        
    # Sort sessions by timestamp
    sorted_sessions = sorted(
        sessions,
        key=lambda s: s.session_start_time if hasattr(s, "session_start_time") else datetime.min
    )
    
    # Calculate total duration for each session
    session_durations = []
    for session in sorted_sessions:
        if not hasattr(session, "session_start_time") or not hasattr(session, "session_stop_time"):
            continue
            
        # Calculate session duration in seconds
        duration = (session.session_stop_time - session.session_start_time).total_seconds()
        
        # Skip invalid durations
        if duration <= 0:
            continue
            
        session_durations.append(duration)
    
    # If we don't have enough data, return stable trend
    if len(session_durations) < 2:
        return {
            "trend": {"direction": "stable", "change": 0},
            "significant": False,
            "durations": session_durations
        }
    
    # Calculate trend using moving average
    if len(session_durations) < window_size:
        window_size = len(session_durations)
        
    # Calculate moving averages if we have enough data
    if len(session_durations) >= window_size:
        # Calculate first and last window averages
        first_window = session_durations[:window_size]
        last_window = session_durations[-window_size:]
        
        first_avg = sum(first_window) / window_size
        last_avg = sum(last_window) / window_size
        
        # Calculate percent change
        if first_avg == 0:
            percent_change = 100 if last_avg > 0 else 0
        else:
            percent_change = ((last_avg - first_avg) / first_avg) * 100
            
        # Determine trend direction
        if abs(percent_change) < 5:  # Less than 5% change is considered stable
            direction = "stable"
        elif percent_change > 0:
            direction = "increasing"
        else:
            direction = "decreasing"
            
        # Determine if trend is statistically significant
        # For simplicity, we'll consider a change significant if it's more than 10%
        significant = abs(percent_change) > 10
    else:
        # Not enough data for moving averages, use simple comparison
        first = session_durations[0]
        last = session_durations[-1]
        
        # Calculate percent change
        if first == 0:
            percent_change = 100 if last > 0 else 0
        else:
            percent_change = ((last - first) / first) * 100
            
        # Determine trend direction
        if abs(percent_change) < 5:
            direction = "stable"
        elif percent_change > 0:
            direction = "increasing"
        else:
            direction = "decreasing"
            
        # Determine if trend is statistically significant
        significant = abs(percent_change) > 10
    
    return {
        "trend": {"direction": direction, "change": percent_change},
        "significant": significant,
        "durations": session_durations
    }
