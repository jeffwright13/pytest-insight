#!/usr/bin/env python3
"""
Pytest-Insight Analysis CLI

This script provides a command-line interface to the pytest-insight API,
serving as a thin wrapper around the Insights class to maintain backward
compatibility with the original analyze_test_data.py implementation.

For new projects, please use the Insights API directly.
"""

import argparse
import json
import sys
import traceback
from typing import Any, Dict

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pytest_insight.core.insights import Insights


def analyze_test_data(
    data_path=None,
    sut_filter=None,
    days=None,
    output_format="text",
    test_pattern=None,
    profile_name=None,
    compare_with=None,
    show_trends=False,
    show_error_details=False,
) -> Dict[str, Any]:
    """Analyze test data using the Insights API.

    This is a thin wrapper around the Insights API that maintains backward compatibility
    with the original analyze_test_data.py implementation.

    Args:
        data_path: Path to the test data file (deprecated, use profile_name instead)
        sut_filter: Filter by system under test name
        days: Filter by number of days
        output_format: Output format (text or json)
        test_pattern: Filter by test name pattern
        profile_name: Storage profile to use
        compare_with: Compare with another dataset (format: days:N, version:X.Y.Z, or profile:name)
        show_trends: Show trend analysis
        show_error_details: Show detailed error information

    Returns:
        Dict containing analysis results
    """
    console = Console()
    json_mode = output_format == "json"
    result = {}

    try:
        # If data_path is provided (legacy mode), create a profile for it
        if data_path and not profile_name:
            from pytest_insight.core.core_api import create_profile

            try:
                profile_name = f"temp_profile_{hash(data_path) % 10000:04d}"
                create_profile(profile_name, "json", data_path)
            except Exception as e:
                if not json_mode:
                    console.print(f"[bold red]Error creating profile for data path:[/bold red] {str(e)}")
                else:
                    print(
                        json.dumps(
                            {"error": f"Error creating profile: {str(e)}"},
                            default=str,
                            indent=2,
                        )
                    )
                return {"error": f"Error creating profile: {str(e)}"}

        # Create insights instance with the profile
        insights = Insights(profile_name=profile_name)

        # Apply filters directly using the fluent interface
        if sut_filter:
            insights = insights.filter_by_sut(sut_filter)
        if days:
            insights = insights.in_last_days(days)
        if test_pattern:
            insights = insights.filter_by_test_name(test_pattern)

        # Check if we have sessions by trying to access session metrics
        try:
            session_metrics = insights.sessions.session_metrics()
            session_count = session_metrics.get("total_sessions", 0)
            if session_count == 0:
                if not json_mode:
                    console.print("[bold red]Error:[/bold red] No test sessions found.")
                    console.print(
                        Panel(
                            "[bold red]No test data available.[/bold red]\n\n"
                            "To generate test data, run:\n"
                            "  [bold]insight-gen --days 14[/bold]\n\n"
                            "Or generate sample data with:\n"
                            "  [bold]insights-new --generate-sample[/bold]\n\n"
                            "Or specify a storage profile:\n"
                            "  [bold]insights-new --profile your_profile_name[/bold]"
                        )
                    )
                else:
                    result = {"error": "No test sessions found"}
                    print(json.dumps(result, default=str, indent=2))
                return result
        except Exception as e:
            if not json_mode:
                console.print(f"[bold red]Error accessing sessions:[/bold red] {str(e)}")
                console.print(
                    Panel(
                        "[bold red]No test data available or error accessing data.[/bold red]\n\n"
                        "To generate test data, run:\n"
                        "  [bold]insight-gen --days 14[/bold]\n\n"
                        "Or generate sample data with:\n"
                        "  [bold]insights-new --generate-sample[/bold]\n\n"
                        "Or specify a storage profile:\n"
                        "  [bold]insights-new --profile your_profile_name[/bold]"
                    )
                )
            else:
                result = {"error": f"Error accessing sessions: {str(e)}"}
                print(json.dumps(result, default=str, indent=2))
            return result

        # Run the analysis
        if json_mode:
            # For JSON output, collect all relevant data into a dictionary
            result = {
                "session_metrics": insights.sessions.session_metrics(),
                "outcome_distribution": insights.tests.outcome_distribution(),
                "reliability_tests": insights.tests.reliability_tests(),
                "stability": insights.tests.test_health_score(),
            }

            # Add additional data based on flags
            if show_error_details:
                result["error_patterns"] = insights.tests.error_patterns()

            # Add trend data if requested
            if show_trends:
                result["trends"] = {
                    "duration_trends": insights.trends.duration_trends(),
                    "failure_trends": insights.trends.failure_trends(),
                }

            # Add comparison data if requested
            if compare_with:
                if ":" in compare_with:
                    compare_type, compare_value = compare_with.split(":", 1)
                else:
                    compare_type = "days"

                if compare_type == "days":
                    try:
                        result["comparison"] = insights.trends.time_comparison()
                    except Exception as e:
                        result["comparison_error"] = str(e)

            # Output the JSON result
            print(json.dumps(result, default=str, indent=2))
            return result
        else:
            # For text output, display results using Rich
            console.print(f"[bold]Found {session_count} test sessions in {profile_name}[/bold]")

            # Display session metrics
            metrics = insights.sessions.session_metrics()
            metrics_table = Table(title="Test Metrics Summary")
            metrics_table.add_column("Metric", style="cyan")
            metrics_table.add_column("Value", style="green")

            metrics_table.add_row("Total Sessions", str(metrics.get("total_sessions", 0)))
            metrics_table.add_row("Total Tests", str(metrics.get("total_tests", 0)))

            # Calculate pass rate
            total_tests = metrics.get("total_tests", 0)
            total_passed = metrics.get("passed_tests", 0)
            pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
            metrics_table.add_row("Pass Rate", f"{pass_rate:.2f}%")

            # Add average duration
            avg_duration = metrics.get("avg_test_duration", 0)
            metrics_table.add_row("Avg Test Duration", f"{avg_duration:.3f}s")

            # Add unreliable test count
            reliability_tests = insights.tests.reliability_tests()
            reliability_count = reliability_tests.get("total_reliable", 0)
            metrics_table.add_row("Reliable Tests", str(reliability_count))

            console.print(metrics_table)

            # Display slowest tests
            slow_tests = insights.tests.slowest_tests(limit=5)
            if slow_tests and "slowest_tests" in slow_tests:
                slow_table = Table(title="Slowest Tests")
                slow_table.add_column("Test Name", style="cyan", no_wrap=False)
                slow_table.add_column("Avg Duration (s)", style="green")

                for test_name, duration in slow_tests["slowest_tests"]:
                    slow_table.add_row(test_name, f"{duration:.3f}")

                console.print(slow_table)

            # Display most failing tests
            error_patterns = insights.tests.error_patterns()
            if error_patterns and "patterns" in error_patterns:
                fail_table = Table(title="Most Failing Tests")
                fail_table.add_column("Test Name", style="cyan", no_wrap=False)
                fail_table.add_column("Failure Count", style="red")

                # Extract failing tests from error patterns
                failing_tests = {}
                for pattern in error_patterns["patterns"]:
                    if "tests" in pattern:
                        for test in pattern["tests"]:
                            failing_tests[test] = failing_tests.get(test, 0) + 1

                # Sort by failure count and display top 5
                sorted_failures = sorted(failing_tests.items(), key=lambda x: x[1], reverse=True)
                for test_name, count in sorted_failures[:5]:
                    fail_table.add_row(test_name, str(count))

                console.print(fail_table)

            # Display environment impact
            env_impact = insights.sessions.environment_impact()
            if env_impact:
                console.print("[bold]Environment Impact[/bold]")

                env_table = Table(show_header=True, header_style="bold")
                env_table.add_column("Environment", style="cyan")
                env_table.add_column("Sessions", style="green")
                env_table.add_column("Avg Pass Rate", style="green")

                if "environments" in env_impact:
                    for env_name, env_data in env_impact["environments"].items():
                        sessions = env_data.get("sessions", 0)
                        pass_rate = env_data.get("pass_rate", 0) * 100
                        env_table.add_row(env_name, str(sessions), f"{pass_rate:.2f}%")

                console.print(env_table)

                if "consistency" in env_impact:
                    console.print(f"Environment Consistency Score: {env_impact['consistency']:.2f} (0-1 scale)")

            # Show trends if requested
            if show_trends:
                console.print("\n[bold]Trend Analysis[/bold]")

                # Duration trends
                duration_trends = insights.trends.duration_trends()
                if duration_trends:
                    trend_pct = duration_trends.get("trend_percentage", 0)
                    increasing = duration_trends.get("increasing", False)
                    direction = "increase" if increasing else "decrease"
                    console.print(f"Duration Trend: {abs(trend_pct):.2f}% {direction}")

                # Failure trends
                failure_trends = insights.trends.failure_trends()
                if failure_trends:
                    trend_pct = failure_trends.get("trend_percentage", 0)
                    improving = failure_trends.get("improving", False)
                    direction = "decrease" if improving else "increase"
                    color = "green" if improving else "red"
                    console.print(
                        f"Failure Trend: [bold {color}]{abs(trend_pct):.2f}% {direction} in failures[/bold {color}]"
                    )

            # Show comparison if requested
            if compare_with and compare_type == "days":
                comparison = insights.trends.time_comparison()
                if comparison:
                    console.print("\n[bold]Comparison Analysis[/bold]")
                    early = comparison.get("early_period", {})
                    late = comparison.get("late_period", {})

                    early_pass = early.get("pass_rate", 0) * 100
                    late_pass = late.get("pass_rate", 0) * 100
                    diff = late_pass - early_pass

                    direction = "improved" if diff > 0 else "declined"
                    color = "green" if diff > 0 else "red"
                    console.print(f"Pass Rate: [bold {color}]{abs(diff):.2f}% {direction}[/bold {color}]")

            # Show completion message
            console.print(
                Panel(
                    "[bold green]Analysis complete![/bold green]\n\n"
                    "Advanced Usage Examples:\n"
                    "  • Compare with previous period:\n"
                    "    [bold]insights --days 7 --compare days:7[/bold]\n\n"
                    "  • Compare with specific version:\n"
                    "    [bold]insights --sut my-app --compare version:1.2.3[/bold]\n\n"
                    "  • Show trends over time:\n"
                    "    [bold]insights --days 30 --trends[/bold]\n\n"
                    "  • Filter by test pattern:\n"
                    "    [bold]insights --test 'test_login*'[/bold]\n\n"
                    "  • Output as JSON for further processing:\n"
                    "    [bold]insights --format json > analysis.json[/bold]"
                )
            )

            return {"status": "success"}

    except Exception as e:
        if not json_mode:
            console.print(f"[bold red]Error during analysis:[/bold red] {str(e)}")
            console.print(traceback.format_exc())

            # Provide helpful guidance
            console.print(
                Panel(
                    "[bold red]Error analyzing test data.[/bold red]\n\n"
                    "To generate test data, run:\n"
                    "  [bold]insight-gen --days 14[/bold]\n\n"
                    "Or generate sample data with:\n"
                    "  [bold]insights-new --generate-sample[/bold]\n\n"
                    "Or specify a storage profile:\n"
                    "  [bold]insights-new --profile your_profile_name[/bold]"
                )
            )
        else:
            error_result = {"error": str(e)}
            print(json.dumps(error_result, default=str, indent=2))
        return {"error": str(e)}


def main():
    """Main function to run the analysis CLI."""
    parser = argparse.ArgumentParser(description="Analyze pytest test results")
    parser.add_argument("--data-path", "-d", help="Path to test data (default: use configured storage)")
    parser.add_argument("--sut", "-s", help="Filter by system under test")
    parser.add_argument("--days", type=int, help="Filter by number of days")
    parser.add_argument("--format", "-f", choices=["text", "json"], default="text", help="Output format")
    parser.add_argument("--test", "-t", help="Filter by test name pattern")
    parser.add_argument("--profile", "-p", help="Storage profile to use")
    parser.add_argument(
        "--compare-with",
        "-c",
        help="Compare with another dataset (format: days:N, version:X.Y.Z, or profile:name)",
    )
    parser.add_argument("--show-trends", "--trends", action="store_true", help="Show trend analysis")
    parser.add_argument(
        "--show-error-details",
        "--errors",
        action="store_true",
        help="Show detailed error information",
    )
    parser.add_argument("--version", "-v", action="store_true", help="Show version information")
    parser.add_argument("--generate-sample", action="store_true", help="Generate sample test data")

    args = parser.parse_args()

    # Show version information if requested
    if args.version:
        from pytest_insight import __version__

        print(f"pytest-insight version: {__version__}")
        return

    # Generate sample data if requested
    if args.generate_sample:
        try:
            # Import the original analyze_test_data module
            from pytest_insight.utils import analyze_test_data as old_analyze

            # Call the generate_sample_data function directly if it exists
            if hasattr(old_analyze, "generate_sample_data"):
                old_analyze.generate_sample_data()
            else:
                # Otherwise, call the main function with the --generate-sample argument
                import sys as sys_module

                original_argv = sys_module.argv
                sys_module.argv = [original_argv[0], "--generate-sample"]
                old_analyze.main()
                sys_module.argv = original_argv
            return
        except Exception as e:
            print(f"Error generating sample data: {str(e)}")
            print(traceback.format_exc())
            return

    try:
        analyze_test_data(
            data_path=args.data_path,
            sut_filter=args.sut,
            days=args.days,
            output_format=args.format,
            test_pattern=args.test,
            profile_name=args.profile,
            compare_with=args.compare_with,
            show_trends=args.show_trends,
            show_error_details=args.show_error_details,
        )
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
