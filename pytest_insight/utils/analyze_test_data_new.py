#!/usr/bin/env python3
"""
Pytest-Insight Analysis CLI

This script provides a command-line interface to:
1. Use the Analysis class to extract insights from test data
2. Apply filtering using the Query class
3. Visualize key metrics and trends

The script follows the fluent interface pattern established in the pytest-insight API.

NOTE: This is a backward-compatible wrapper around the new insights_cli.py implementation.
For new projects, please use insights_cli.py directly.
"""

import argparse
import json
import sys
from datetime import datetime, timedelta

from rich.console import Console

from pytest_insight.core.insights import Insights
from pytest_insight.utils.insights_cli import _format_rich_output


def analyze_test_data(
    data_path=None,
    sut_filter=None,
    days=None,
    output_format="text",
    test_pattern=None,
    profile=None,
    compare_with=None,
    show_trends=False,
    show_error_details=False,
):
    """Analyze test data using the Insights API.

    This is a wrapper around the new Insights API that maintains backward compatibility
    with the original analyze_test_data.py implementation.
    """
    # Always create the console object for test compatibility
    console = Console()

    # Flag to determine if we should actually print console output
    json_mode = output_format == "json"

    # Create insights instance
    insights = Insights(profile_name=profile)

    # Apply filters if provided
    if any([sut_filter, days, test_pattern]):
        insights = insights.with_query(
            lambda q: q.filter_by_sut(sut_filter) if sut_filter else q
        )
        insights = insights.with_query(lambda q: q.in_last_days(days) if days else q)
        insights = insights.with_query(
            lambda q: q.filter_by_test_name(test_pattern) if test_pattern else q
        )

    # Initialize result for JSON output
    result = {}

    # Generate insights
    if not json_mode:
        console.print("[bold]Pytest-Insight Analysis[/bold]")

    # 1. Test Health Score
    health_data = insights.tests.test_health_score()
    if not json_mode:
        _format_rich_output(health_data, title="Test Health Analysis")
    else:
        result["test_health"] = health_data

    # 2. Error Patterns
    error_data = insights.tests.error_patterns()
    if not json_mode:
        _format_rich_output(error_data, title="Error Patterns Analysis")
    else:
        result["error_patterns"] = error_data["patterns"]
        result["multi_error_tests"] = error_data["multi_error_tests"]

    # 3. Dependency Graph
    dependency_data = insights.tests.dependency_graph()
    if not json_mode:
        _format_rich_output(dependency_data, title="Test Dependency Graph")
    else:
        result["dependency_graph"] = dependency_data

    # 4. Environment Impact
    env_data = insights.sessions.environment_impact()
    if not json_mode:
        _format_rich_output(env_data, title="Environment Impact Analysis")
    else:
        result["environment_impact"] = env_data

    # 5. Correlation Analysis
    correlation_data = insights.tests.correlation_analysis()
    if not json_mode:
        _format_rich_output(correlation_data, title="Test Correlation Analysis")
    else:
        result["correlations"] = correlation_data

    # 6. Seasonal Patterns
    seasonal_data = insights.tests.seasonal_patterns()
    if not json_mode:
        _format_rich_output(seasonal_data, title="Seasonal Failure Patterns")
    else:
        result["seasonal_patterns"] = seasonal_data

    # 7. Stability Timeline
    if not json_mode:
        timeline_data = insights.tests.stability_timeline(days=7, limit=10)
        _format_rich_output(timeline_data, title="Test Stability Timeline")

    # Handle comparison if requested
    if compare_with:
        if not json_mode:
            console.print(f"\n[bold]Comparison Analysis: {compare_with}[/bold]")
            console.print(
                "[yellow]Note: Comparison is now handled by the new Insights API.[/yellow]"
            )

        # Parse the comparison criteria
        if ":" in compare_with:
            compare_type, compare_value = compare_with.split(":", 1)
        else:
            compare_type, compare_value = "days", compare_with

        if compare_type == "days":
            try:
                days_to_compare = int(compare_value)
                # Use the trends API to compare time periods
                trend_data = insights.trends.time_comparison()

                if not json_mode:
                    _format_rich_output(
                        trend_data,
                        title=f"Comparison with previous {days_to_compare} days",
                    )
                else:
                    result["comparison"] = trend_data
            except Exception as e:
                if not json_mode:
                    console.print(f"[bold red]Error in comparison:[/bold red] {str(e)}")
        else:
            if not json_mode:
                console.print(
                    f"[bold red]Unknown comparison type: {compare_type}[/bold red]"
                )
                console.print("Valid formats: days:N, version:X.Y.Z, or profile:name")

    # Show trends if requested
    if show_trends and not json_mode:
        duration_trends = insights.trends.duration_trends()
        _format_rich_output(duration_trends, title="Duration Trends")

        failure_trends = insights.trends.failure_trends()
        _format_rich_output(failure_trends, title="Failure Trends")

    # Output JSON if requested
    if json_mode:
        print(json.dumps(result, default=str, indent=2))

    return result


def main():
    """Main function to run the analysis CLI."""
    parser = argparse.ArgumentParser(description="Analyze pytest test results")
    parser.add_argument(
        "--data-path", "-d", help="Path to test data (default: use configured storage)"
    )
    parser.add_argument("--sut", "-s", help="Filter by system under test")
    parser.add_argument("--days", type=int, help="Filter by number of days")
    parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text", help="Output format"
    )
    parser.add_argument("--test", "-t", help="Filter by test name pattern")
    parser.add_argument("--profile", "-p", help="Storage profile to use")
    parser.add_argument(
        "--compare-with",
        "-c",
        help="Compare with another dataset (format: days:N, version:X.Y.Z, or profile:name)",
    )
    parser.add_argument(
        "--show-trends", action="store_true", help="Show trend analysis"
    )
    parser.add_argument(
        "--show-error-details",
        action="store_true",
        help="Show detailed error information",
    )

    args = parser.parse_args()

    analyze_test_data(
        data_path=args.data_path,
        sut_filter=args.sut,
        days=args.days,
        output_format=args.format,
        test_pattern=args.test,
        profile=args.profile,
        compare_with=args.compare_with,
        show_trends=args.show_trends,
        show_error_details=args.show_error_details,
    )


if __name__ == "__main__":
    main()
