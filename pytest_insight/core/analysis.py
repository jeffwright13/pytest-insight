"""Analysis utilities for metrics and reliability calculations.

This module provides functions for calculating reliability scores from test sessions.
"""

from .models import TestSession


def calculate_reliability(sessions: list[TestSession]) -> float:
    """
    Calculate overall reliability score for a set of sessions.

    Args:
        sessions (list[TestSession]): List of test sessions to analyze.

    Returns:
        float: Reliability score between 0.0 and 1.0.
    """
    # Placeholder: implement real logic
    # return 1.0 if sessions else 0.0
    # Calculate the reliability index for each test over all sessions

    # Initialize a dictionary to store reliability for each test
    test_reliability = {}
    total_sessions = len(sessions)

    # Iterate over each session
    for session in sessions:
        # Iterate over each test in the session
        for test in session.test_results:
            # Get the test name
            test_name = test.nodeid

            # Initialize reliability for the test if not already present
            if test_name not in test_reliability:
                test_reliability[test_name] = {
                    "total_sessions": 0,
                    "reliable_sessions": 0,
                }

            # Update session count
            test_reliability[test_name]["total_sessions"] += 1

            # Check if the test passed in this session
            # FIX: Use enum comparison, not string
            if hasattr(test.outcome, "name"):
                is_passed = test.outcome.name.upper() == "PASSED"
            else:
                is_passed = str(test.outcome).upper() == "PASSED"
            if is_passed:
                test_reliability[test_name]["reliable_sessions"] += 1

    # Calculate the overall reliability score
    reliable_tests = sum(
        reliability["reliable_sessions"] for reliability in test_reliability.values()
    )
    total_tests = sum(
        reliability["total_sessions"] for reliability in test_reliability.values()
    )

    # Return the reliability score (0.0 if no tests, otherwise reliable_tests / total_tests)
    return reliable_tests / total_tests if total_tests > 0 else 0.0
