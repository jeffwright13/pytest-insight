"""
Dashboard formatter for pytest-insight terminal output.
Formats summary tables, test insights, and sparklines for trends.
"""
from typing import Any, Dict, List
from pytest_insight.insight_api import InsightAPI
from sparklines import sparklines
from tabulate import tabulate


def sparkline(data: List[float]) -> str:
    return ''.join(sparklines(data)) if data else ""

def insights_dashboard(summary: Dict[str, Any], slowest: List[Dict[str, Any]], least_reliable: List[Dict[str, Any]], trends: List[Dict[str, Any]], tests_by_day: List[int]) -> str:
    out = [
        "\nPYTEST-INSIGHT DASHBOARD\n" + "=" * 30,
        "\nTest Summary:",
    ]
    # Test Summary (fix: always compact and readable)
    if isinstance(summary, str):
        out.append(summary)
    elif isinstance(summary, dict):
        # Only show a compact subset of keys
        display_keys = [
            k for k in ["total_sessions", "total_tests", "pass_rate", "fail_rate", "avg_duration", "median_duration", "min_duration", "max_duration"]
            if k in summary
        ]
        if display_keys:
            compact_summary = {k: summary.get(k, "") for k in display_keys}
            out.append(tabulate([compact_summary], headers="keys", tablefmt="github"))
        else:
            # If no compact keys, fallback to string
            out.append(str(summary))
    else:
        out.append(str(summary))
    out.append("\nTop 3 Slowest Tests:")
    if slowest:
        out.append(tabulate(slowest, headers="keys", tablefmt="github"))
    else:
        out.append("(No data)")
    # Least reliable tests table (fix: restrict columns for readability)
    display_keys = ["nodeid", "reliability", "runs", "failures", "unreliable_rate"]
    table_data = [
        {k: d.get(k, "") for k in display_keys}
        for d in least_reliable
    ] if least_reliable else []
    if table_data:
        out.append("\nLeast Reliable Tests:")
        out.append(tabulate(table_data, headers="keys", tablefmt="github"))
    else:
        out.append("(No data)")
    # Trends sparklines
    out.append("\nTrends:")
    for trend in trends:
        for trend_name, values in trend.items():
            # Ensure values is a sequence for sparkline
            if isinstance(values, dict):
                series = list(values.values())  # Do NOT slice, show all points
            elif isinstance(values, (list, tuple)):
                series = values
            else:
                series = [values]
            out.append(f"{trend_name}: {sparkline(series)}  ({series[-1] if series else ''})")
    # Tests by day sparkline
    out.append("\nTotal Tests by Day:")
    out.append(sparkline(tests_by_day))
    return '\n'.join(out)

def build_dashboard_from_api(api: InsightAPI) -> str:
    """
    Given an InsightAPI instance, gather all analytics and return the formatted dashboard string.
    This is the single entrypoint for plugin.py or any CLI/dashboard code.
    """
    summary = api.session().insight("health")
    test_insights = api.test().insight("detailed")
    slowest = test_insights.get("slowest_tests", [])[:3]
    least_reliable = test_insights.get("unreliable_tests", [])[:3]
    trend_insights = api.trend().insight("trend")
    duration_trends = trend_insights.get("duration_trends", {}).get("avg_duration_by_day", {})
    failure_trends = trend_insights.get("failure_trends", {}).get("failures_by_day", {})
    # For sparkline, show total tests by day (using duration_trends keys as days for simplicity)
    tests_by_day = [len(api.session(session_id=day).sessions) for day in duration_trends.keys()] if duration_trends else []
    return insights_dashboard(
        summary=summary,
        slowest=slowest,
        least_reliable=least_reliable,
        trends=[duration_trends, failure_trends],
        tests_by_day=tests_by_day,
    )
