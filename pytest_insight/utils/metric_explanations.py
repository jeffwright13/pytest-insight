"""
Utility module providing standardized explanations for pytest-insight metrics.

This module contains both short and detailed explanations for all metrics
used in pytest-insight. These explanations can be used in tooltips, documentation,
and CLI help text to ensure consistent descriptions across the application.
"""

from typing import Any, Dict

# Short explanations suitable for tooltips and CLI help
SHORT_EXPLANATIONS: Dict[str, str] = {
    "reliability_rate": "Percentage of tests that were reliable (not rerun or always passed). Higher is better.",
    "pass_rate": "Percentage of tests that passed on the first attempt. Higher is better.",
    "failure_rate": "Percentage of tests that failed. Lower is better.",
    "avg_duration": "Average time taken to execute a test. Lower is better.",
    "health_score": "Composite score (0-10) measuring overall test suite health. Higher is better.",
    "regression_rate": "Rate at which previously passing tests start failing. Lower is better.",
    "reliability_delta": "Change in reliability rate over time. Positive values indicate improvement.",
    "test_stability_score": "Score (0-100) measuring test stability. Higher is better.",
    "rerun_success_rate": "Percentage of tests that passed after being rerun. Higher values indicate more unreliable tests.",
    "reliability_index": "Percentage of tests with consistent outcomes. Higher is better.",
    "rerun_recovery_rate": "Percentage of tests that passed after being rerun. Higher values indicate tests that are unreliable but recoverable.",
}

# Detailed explanations suitable for documentation and expanded tooltips
DETAILED_EXPLANATIONS: Dict[str, Dict[str, Any]] = {
    "reliability_rate": {
        "definition": "The percentage of tests that are reliable (not rerun or always passed) out of all tests.",
        "calculation": "1. A test is considered reliable if it has not been rerun or always passed\n"
        "2. Overall Reliability Rate = (Number of Reliable Tests / Total Number of Unique Tests) * 100%\n"
        "3. For individual tests, Reliability Rate = (1 - Rerun Rate) * 100%, where Rerun Rate is the ratio of sessions where the test was rerun to the total number of runs (including reruns)",
        "interpretation": "- Higher reliability rates indicate more stable test suites\n"
        "- A healthy test suite should have a reliability rate above 95%",
        "weight_in_health_score": 20,
    },
    "reliability_index": {
        "definition": "The percentage of tests with consistent outcomes out of all tests.",
        "calculation": "1. A test is considered unstable if it requires reruns\n"
        "2. Reliability Index = 100% - (Number of Unstable Tests / Total Number of Unique Tests) * 100%",
        "interpretation": "- Higher reliability index indicates more stable test suites\n"
        "- A healthy test suite should have a reliability index above 95%\n"
        "- Tests with low reliability require more attention as they are less predictable",
        "weight_in_health_score": 20,
    },
    "rerun_recovery_rate": {
        "definition": "The percentage of tests that passed after being rerun.",
        "calculation": "Rerun Recovery Rate = (Number of Tests That Passed After Rerun / Total Number of Rerun Tests) * 100%",
        "interpretation": "- Higher rerun recovery rates indicate more unreliable tests rather than genuine failures\n"
        "- This metric helps distinguish between unreliable tests and actual bugs",
    },
    "pass_rate": {
        "definition": "The percentage of tests that passed on the first attempt.",
        "calculation": "Pass Rate = (Number of Passed Tests / Total Number of Tests) * 100%",
        "interpretation": "- Higher pass rates indicate a healthier codebase and test suite\n"
        "- A healthy test suite should have a pass rate above 85%",
        "weight_in_health_score": 50,
    },
    "health_score": {
        "definition": "A composite score (0-10) that measures the overall health of the test suite.",
        "calculation": "Based on a weighted formula that considers:\n"
        "- Pass rate (50% weight)\n"
        "- Reliability (20% weight)\n"
        "- Duration stability (15% weight)\n"
        "- Failure pattern (15% weight)",
        "interpretation": "- Higher scores indicate healthier test suites\n"
        "- Scores below 6 indicate significant health issues\n"
        "- Scores above 8 indicate a healthy test suite",
    },
    "regression_rate": {
        "definition": "The rate at which previously passing tests start failing.",
        "calculation": "Regression Rate = (Number of Tests That Changed from Pass to Fail / Total Number of Previously Passing Tests) * 100%",
        "interpretation": "- Higher rates indicate more code changes breaking existing functionality\n"
        "- Lower rates indicate more stable code changes",
    },
    "reliability_delta": {
        "definition": "The change in reliability rate over time.",
        "calculation": "Reliability Delta = Current Period Reliability Rate - Previous Period Reliability Rate",
        "interpretation": "- Positive values indicate improvement (greater reliability)\n"
        "- Values close to zero indicate stable reliability",
    },
    "test_stability_score": {
        "definition": "A composite score (0-100) that measures the overall stability of tests.",
        "calculation": "Based on a weighted formula that considers:\n"
        "- Pass rate (50% weight)\n"
        "- Reliability (20% weight)\n"
        "- Duration stability (15% weight)\n"
        "- Failure pattern (15% weight)",
        "interpretation": "- Higher scores indicate more stable test suites\n"
        "- Scores below 60 indicate significant stability issues\n"
        "- Scores above 80 indicate a healthy, stable test suite",
    },
    "rerun_success_rate": {
        "definition": "The percentage of tests that passed after being rerun.",
        "calculation": "Rerun Success Rate = (Number of Tests That Passed After Rerun / Total Number of Rerun Tests) * 100%",
        "interpretation": "- Higher rerun success rates indicate more unreliable tests rather than genuine failures\n"
        "- This metric helps distinguish between unreliable tests and actual bugs",
    },
}


def get_short_explanation(metric_name: str) -> str:
    """Get a short explanation for a metric.

    Args:
        metric_name: Name of the metric

    Returns:
        Short explanation string or a default message if not found
    """
    return SHORT_EXPLANATIONS.get(
        metric_name, f"No explanation available for {metric_name}"
    )


def get_detailed_explanation(metric_name: str) -> Dict[str, Any]:
    """Get a detailed explanation for a metric.

    Args:
        metric_name: Name of the metric

    Returns:
        Dictionary with detailed explanation or empty dict if not found
    """
    return DETAILED_EXPLANATIONS.get(metric_name, {})
