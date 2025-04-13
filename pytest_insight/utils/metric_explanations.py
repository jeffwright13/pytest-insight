"""
Utility module providing standardized explanations for pytest-insight metrics.

This module contains both short and detailed explanations for all metrics
used in pytest-insight. These explanations can be used in tooltips, documentation,
and CLI help text to ensure consistent descriptions across the application.
"""

from typing import Dict, Any

# Short explanations suitable for tooltips and CLI help
SHORT_EXPLANATIONS: Dict[str, str] = {
    "flaky_rate": "Percentage of tests that were rerun and eventually passed. Lower is better.",
    "pass_rate": "Percentage of tests that passed on the first attempt. Higher is better.",
    "failure_rate": "Percentage of tests that failed. Lower is better.",
    "avg_duration": "Average time taken to execute a test. Lower is better.",
    "health_score": "Composite score (0-10) measuring overall test suite health. Higher is better.",
    "regression_rate": "Rate at which previously passing tests start failing. Lower is better.",
    "flakiness_delta": "Change in flakiness rate over time. Negative values indicate improvement.",
    "test_stability_score": "Score (0-100) measuring test stability. Higher is better.",
    "rerun_success_rate": "Percentage of tests that passed after being rerun. Higher values indicate more flaky tests.",
    "reliability_index": "Percentage of tests with consistent outcomes. Higher is better.",
    "rerun_recovery_rate": "Percentage of tests that passed after being rerun. Higher values indicate tests that are flaky but recoverable.",
}

# Detailed explanations suitable for documentation and expanded tooltips
DETAILED_EXPLANATIONS: Dict[str, Dict[str, Any]] = {
    "flaky_rate": {
        "definition": "The percentage of tests that exhibit flaky behavior out of all tests.",
        "calculation": "1. A test is considered flaky if it has been rerun and eventually passed\n"
                      "2. Overall Flaky Rate = (Number of Flaky Tests / Total Number of Unique Tests) * 100%\n"
                      "3. For individual tests, Flake Rate = (1 - Pass Rate) * 100%, where Pass Rate is the ratio of sessions where the test eventually passed to the total number of runs (including reruns)",
        "interpretation": "- Higher flaky rates indicate less stable test suites\n"
                         "- Tests with high individual flake rates require more attention as they are less reliable\n"
                         "- A healthy test suite should have a flaky rate below 5%",
        "weight_in_health_score": 20
    },
    "reliability_index": {
        "definition": "The percentage of tests with consistent outcomes out of all tests.",
        "calculation": "1. A test is considered unstable if it requires reruns\n"
                      "2. Reliability Index = 100% - (Number of Unstable Tests / Total Number of Unique Tests) * 100%",
        "interpretation": "- Higher reliability index indicates more stable test suites\n"
                         "- A healthy test suite should have a reliability index above 95%\n"
                         "- Tests with low reliability require more attention as they are less predictable",
        "weight_in_health_score": 20
    },
    "rerun_recovery_rate": {
        "definition": "The percentage of tests that passed after being rerun.",
        "calculation": "Rerun Recovery Rate = (Number of Tests That Passed After Rerun / Total Number of Rerun Tests) * 100%",
        "interpretation": "- Higher rerun recovery rates indicate more flaky tests rather than genuine failures\n"
                         "- This metric helps distinguish between flaky tests and actual bugs\n"
                         "- A high recovery rate with a low reliability index suggests environmental or timing issues"
    },
    "pass_rate": {
        "definition": "The percentage of tests that passed on the first attempt.",
        "calculation": "Pass Rate = (Number of Passed Tests / Total Number of Tests) * 100%",
        "interpretation": "- Higher pass rates indicate a healthier codebase and test suite\n"
                         "- A healthy test suite should have a pass rate above 85%",
        "weight_in_health_score": 50
    },
    "health_score": {
        "definition": "A composite score (0-10) that measures the overall health of the test suite.",
        "calculation": "Based on a weighted formula that considers:\n"
                      "- Pass rate (50% weight)\n"
                      "- Flakiness (20% weight)\n"
                      "- Duration stability (15% weight)\n"
                      "- Failure pattern (15% weight)",
        "interpretation": "- Higher scores indicate healthier test suites\n"
                         "- Scores below 6 indicate significant health issues\n"
                         "- Scores above 8 indicate a healthy test suite"
    },
    "regression_rate": {
        "definition": "The rate at which previously passing tests start failing.",
        "calculation": "Regression Rate = (Number of Tests That Changed from Pass to Fail / Total Number of Previously Passing Tests) * 100%",
        "interpretation": "- Higher rates indicate more code changes breaking existing functionality\n"
                         "- Lower rates indicate more stable code changes"
    },
    "flakiness_delta": {
        "definition": "The change in flakiness rate over time.",
        "calculation": "Flakiness Delta = Current Period Flaky Rate - Previous Period Flaky Rate",
        "interpretation": "- Negative values indicate improving stability\n"
                         "- Positive values indicate degrading stability\n"
                         "- Values close to zero indicate stable flakiness"
    },
    "test_stability_score": {
        "definition": "A composite score (0-100) that measures the overall stability of tests.",
        "calculation": "Based on a weighted formula that considers:\n"
                      "- Pass rate (50% weight)\n"
                      "- Flakiness (20% weight)\n"
                      "- Duration stability (15% weight)\n"
                      "- Failure pattern (15% weight)",
        "interpretation": "- Higher scores indicate more stable test suites\n"
                         "- Scores below 60 indicate significant stability issues\n"
                         "- Scores above 80 indicate a healthy, stable test suite"
    },
    "rerun_success_rate": {
        "definition": "The percentage of tests that passed after being rerun.",
        "calculation": "Rerun Success Rate = (Number of Tests That Passed After Rerun / Total Number of Rerun Tests) * 100%",
        "interpretation": "- Higher rerun success rates indicate more flaky tests rather than genuine failures\n"
                         "- This metric helps distinguish between flaky tests and actual bugs"
    }
}


def get_short_explanation(metric_name: str) -> str:
    """Get a short explanation for a metric.

    Args:
        metric_name: Name of the metric

    Returns:
        Short explanation string or a default message if not found
    """
    return SHORT_EXPLANATIONS.get(
        metric_name, 
        f"No explanation available for {metric_name}"
    )


def get_detailed_explanation(metric_name: str) -> Dict[str, Any]:
    """Get a detailed explanation for a metric.

    Args:
        metric_name: Name of the metric

    Returns:
        Dictionary with detailed explanation or empty dict if not found
    """
    return DETAILED_EXPLANATIONS.get(metric_name, {})
