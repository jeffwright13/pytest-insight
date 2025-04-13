"""Health metrics methods for pytest-insight.

This module contains implementations of health metrics methods that can be used
by both the Analysis and SessionAnalysis classes to provide insights into test
suite health, performance, and stability.
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
        return {"regression_rate": 0, "regressed_tests": []}
        
    # Sort sessions by timestamp
    sorted_sessions = sorted(
        sessions,
        key=lambda s: s.session_start_time if hasattr(s, "session_start_time") else datetime.min
    )
    
    # Track test outcomes across sessions
    test_history = {}
    
    # Analyze test results from all sessions
    for session in sorted_sessions:
        if not hasattr(session, "test_results") or not session.test_results:
            continue
            
        # Process regular test results
        for test in session.test_results:
            if not hasattr(test, "nodeid") or not test.nodeid:
                continue
                
            nodeid = test.nodeid
            outcome = test.outcome if hasattr(test, "outcome") else None
            
            # Initialize history for this test if needed
            if nodeid not in test_history:
                test_history[nodeid] = []
                
            # Add outcome to history
            test_history[nodeid].append({
                "session_id": session.id if hasattr(session, "id") else None,
                "timestamp": session.session_start_time if hasattr(session, "session_start_time") else None,
                "outcome": outcome
            })
    
    # Identify regressions (tests that changed from passing to failing)
    regressed_tests = []
    total_tests = 0
    
    for nodeid, history in test_history.items():
        # Skip tests with only one run
        if len(history) < 2:
            continue
            
        total_tests += 1
        
        # Check if test regressed
        last_passing_idx = None
        for i, entry in enumerate(history):
            if entry["outcome"] == TestOutcome.PASSED:
                last_passing_idx = i
                
        # If test passed at some point and then failed in the most recent run
        if (last_passing_idx is not None and 
            last_passing_idx < len(history) - 1 and 
            history[-1]["outcome"] == TestOutcome.FAILED):
            
            regressed_tests.append({
                "nodeid": nodeid,
                "last_passing": history[last_passing_idx]["timestamp"],
                "first_failing": history[last_passing_idx + 1]["timestamp"]
            })
    
    # Calculate regression rate
    regression_rate = (len(regressed_tests) / total_tests) * 100 if total_tests > 0 else 0
    
    return {
        "regression_rate": regression_rate,
        "regressed_tests": regressed_tests
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
    test_durations = defaultdict(list)
    
    # Analyze test results from all sessions
    for session in sessions:
        if not hasattr(session, "test_results") or not session.test_results:
            continue
            
        # Process regular test results
        for test in session.test_results:
            if not hasattr(test, "nodeid") or not test.nodeid:
                continue
                
            nodeid = test.nodeid
            
            # Get test duration if available
            if hasattr(test, "duration") and test.duration is not None and test.duration > 0:
                test_durations[nodeid].append(test.duration)
    
    # Calculate average durations and prepare results
    results = []
    for nodeid, durations in test_durations.items():
        if durations:
            avg_duration = sum(durations) / len(durations)
            results.append({
                "nodeid": nodeid,
                "avg_duration": avg_duration,
                "max_duration": max(durations),
                "min_duration": min(durations),
                "run_count": len(durations)
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
