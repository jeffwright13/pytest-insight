#!/usr/bin/env python3
"""
Pytest-Insight Analysis CLI

This script provides a command-line interface to:
1. Use the Analysis class to extract insights from test data
2. Apply filtering using the Query class
3. Visualize key metrics and trends

The script follows the fluent interface pattern established in the pytest-insight API.
"""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pytest_insight.analysis import Analysis
from pytest_insight.core_api import InsightAPI
from pytest_insight.models import TestSession
from pytest_insight.storage import ProfileManager, get_storage_instance


def analyze_test_data(
    data_path=None,
    sut_filter=None,
    days=None,
    output_format="text",
    test_pattern=None,
    profile=None,
    compare_with=None,
    show_trends=False,
):
    """Analyze test data using the Analysis class."""
    console = Console()

    with console.status("[bold green]Analyzing test data..."):
        try:
            # Initialize sessions list
            sessions = []

            # Use profile if specified, otherwise load from file
            if profile:
                console.print(f"[bold]Using profile:[/bold] {profile}")
                try:
                    # Get storage instance for the specified profile
                    storage = get_storage_instance(profile_name=profile)
                    # Load sessions from the profile's storage
                    sessions = storage.load_sessions()
                    if not sessions:
                        console.print(f"[bold yellow]Warning:[/bold yellow] No sessions found in profile '{profile}'.")
                        return
                except Exception as e:
                    console.print(f"[bold red]Error loading from profile '{profile}':[/bold red] {str(e)}")
                    console.print("Falling back to file-based loading...")
                    # Fall back to file loading if profile loading fails
                    if data_path is None:
                        console.print("[bold red]Error:[/bold red] No data path specified and profile loading failed.")
                        return

            # Load from file if no profile or profile loading failed
            if not profile or not sessions:
                if not data_path:
                    console.print("[bold red]Error:[/bold red] No data path specified.")
                    return

                # Load the data file
                with open(data_path, "r") as f:
                    try:
                        raw_data = json.load(f)
                    except json.JSONDecodeError:
                        console.print(f"[bold red]Error:[/bold red] Invalid JSON format in {data_path}")
                        return

                # Determine the data structure and extract sessions
                # Case 1: Direct list of session dictionaries
                if isinstance(raw_data, list):
                    try:
                        sessions = [TestSession.from_dict(session) for session in raw_data]
                    except Exception as e:
                        console.print(f"[bold red]Error:[/bold red] Failed to parse sessions from list: {str(e)}")
                        return

                # Case 2: Dictionary with a 'sessions' key
                elif isinstance(raw_data, dict) and "sessions" in raw_data and isinstance(raw_data["sessions"], list):
                    try:
                        sessions = [TestSession.from_dict(session) for session in raw_data["sessions"]]
                    except Exception as e:
                        console.print(
                            f"[bold red]Error:[/bold red] Failed to parse sessions from 'sessions' key: {str(e)}"
                        )
                        return

                # Case 3: Unknown format
                else:
                    console.print(
                        f"[bold red]Error:[/bold red] Unknown data format in {data_path}. Expected a list of sessions or a dictionary with a 'sessions' key."
                    )
                    console.print("\nTo generate valid test data, run:")
                    console.print("  [bold]insight-gen --days 14[/bold]")
                    return

            if not sessions:
                console.print("[bold yellow]Warning:[/bold yellow] No sessions found in the data source.")
                return

            # Now use the InsightAPI for a consistent interface
            api = InsightAPI()

            # Apply filters to the loaded sessions
            filtered_sessions = sessions

            # Apply SUT filter if specified
            if sut_filter:
                filtered_sessions = [s for s in filtered_sessions if s.sut_name == sut_filter]
                console.print(f"[bold]Filtered to:[/bold] {len(filtered_sessions)} sessions for SUT '{sut_filter}'")

            # Apply days filter if specified
            if days:
                cutoff_date = datetime.now() - timedelta(days=days)
                filtered_sessions = [s for s in filtered_sessions if s.timestamp >= cutoff_date]
                console.print(f"[bold]Filtered to:[/bold] {len(filtered_sessions)} sessions from the last {days} days")

            # Apply test pattern filter if specified
            if test_pattern:
                import re

                pattern = re.compile(test_pattern.replace("*", ".*"))

                # We need to filter at the test level, not the session level
                filtered_sessions_by_test = []
                for session in filtered_sessions:
                    matching_tests = [test for test in session.test_results if pattern.search(test.nodeid)]
                    if matching_tests:
                        # Create a copy of the session with only matching tests
                        session_copy = TestSession.from_dict(session.to_dict())
                        session_copy.test_results = matching_tests
                        filtered_sessions_by_test.append(session_copy)

                filtered_sessions = filtered_sessions_by_test
                console.print(
                    f"[bold]Filtered to:[/bold] {len(filtered_sessions)} sessions with tests matching '{test_pattern}'"
                )

            if not filtered_sessions:
                console.print(
                    Panel(
                        "[bold red]No test sessions found with the current filters.[/bold red]\n"
                        "Try adjusting your filters or using a different data source."
                    )
                )
                return

            # Basic statistics
            console.print(Panel(f"[bold]Found {len(filtered_sessions)} test sessions[/bold]"))

            # Create an analysis object
            analysis = Analysis(sessions=filtered_sessions)

            # Get basic metrics
            total_tests = analysis.count_total_tests()
            pass_rate = analysis.calculate_pass_rate()
            avg_duration = analysis.calculate_average_duration()
            flaky_tests = analysis.identify_flaky_tests()
            slowest_tests = analysis.identify_slowest_tests(limit=5)
            most_failing = analysis.identify_most_failing_tests(limit=5)
            consistently_failing = analysis.identify_consistently_failing_tests(min_consecutive_failures=2)

            # Get tests with hysteresis (predominantly failing but with occasional passes)
            predominantly_failing = analysis.identify_consistently_failing_tests_with_hysteresis(
                min_consecutive_failures=2,
                hysteresis_threshold=0.2,  # Allow up to 20% passes
                min_failure_rate=0.7,  # At least 70% failures
            )

            # Display basic metrics
            metrics_table = Table(title="Test Metrics Summary")
            metrics_table.add_column("Metric", style="cyan")
            metrics_table.add_column("Value", style="green")

            metrics_table.add_row("Total Sessions", str(len(filtered_sessions)))
            metrics_table.add_row("Total Tests", str(total_tests))
            metrics_table.add_row("Pass Rate", f"{pass_rate:.2%}")
            metrics_table.add_row("Avg Test Duration", f"{avg_duration:.3f}s")
            metrics_table.add_row("Flaky Tests", str(len(flaky_tests)))

            console.print(metrics_table)

            # Display slowest tests
            if slowest_tests:
                slow_table = Table(title="Slowest Tests")
                slow_table.add_column("Test Name", style="cyan")
                slow_table.add_column("Avg Duration (s)", style="yellow")

                for test, duration in slowest_tests:
                    slow_table.add_row(test, f"{duration:.3f}")

                console.print(slow_table)

            # Display most failing tests
            if most_failing:
                fail_table = Table(title="Most Failing Tests")
                fail_table.add_column("Test Name", style="cyan")
                fail_table.add_column("Failure Count", style="red")

                for test, count in most_failing:
                    fail_table.add_row(test, str(count))

                console.print(fail_table)

            # Display consistently failing tests
            if consistently_failing:
                console.print(
                    Panel(
                        "[bold red]Consistently Failing Tests[/bold red]",
                        subtitle="Tests that have failed in consecutive sessions",
                    )
                )

                consistent_table = Table()
                consistent_table.add_column("Test Name", style="cyan")
                consistent_table.add_column("Consecutive Failures", style="red")
                consistent_table.add_column("First Failure", style="yellow")
                consistent_table.add_column("Last Failure", style="yellow")
                consistent_table.add_column("Duration", style="magenta")

                for test in consistently_failing[:5]:  # Show top 5
                    # Format timestamps - handle both datetime objects and float timestamps
                    try:
                        if isinstance(test["first_failure"], datetime):
                            first_failure = test["first_failure"].strftime("%Y-%m-%d %H:%M")
                        else:
                            first_failure = datetime.fromtimestamp(test["first_failure"]).strftime("%Y-%m-%d %H:%M")
                    except:
                        first_failure = "Unknown"

                    try:
                        if isinstance(test["last_failure"], datetime):
                            last_failure = test["last_failure"].strftime("%Y-%m-%d %H:%M")
                        else:
                            last_failure = datetime.fromtimestamp(test["last_failure"]).strftime("%Y-%m-%d %H:%M")
                    except:
                        last_failure = "Unknown"

                    # Format duration
                    duration_seconds = test["failure_duration"]
                    if duration_seconds < 60 * 60:  # Less than an hour
                        duration = f"{duration_seconds//60} min"
                    elif duration_seconds < 24 * 60 * 60:  # Less than a day
                        duration = f"{duration_seconds//(60*60)} hours"
                    else:  # Days
                        duration = f"{duration_seconds//(24*60*60)} days"

                    consistent_table.add_row(
                        test["nodeid"], str(test["consecutive_failures"]), first_failure, last_failure, duration
                    )

                console.print(consistent_table)

                if len(consistently_failing) > 5:
                    console.print(f"[dim]...and {len(consistently_failing) - 5} more consistently failing tests[/dim]")

            # Display predominantly failing tests with hysteresis
            if predominantly_failing:
                console.print(
                    Panel(
                        "[bold red]Predominantly Failing Tests with Hysteresis[/bold red]",
                        subtitle="Tests that predominantly fail but occasionally pass",
                    )
                )

                hysteresis_table = Table()
                hysteresis_table.add_column("Test Name", style="cyan")
                hysteresis_table.add_column("Failure Count", style="red")
                hysteresis_table.add_column("Pass Count", style="green")
                hysteresis_table.add_column("Failure Rate", style="yellow")
                hysteresis_table.add_column("First Seen", style="blue")
                hysteresis_table.add_column("Last Seen", style="blue")
                hysteresis_table.add_column("Duration", style="magenta")

                for test in predominantly_failing[:5]:  # Show top 5
                    # Format timestamps
                    first_occurrence = (
                        test["first_occurrence"].strftime("%Y-%m-%d %H:%M") if test["first_occurrence"] else "Unknown"
                    )
                    last_occurrence = (
                        test["last_occurrence"].strftime("%Y-%m-%d %H:%M") if test["last_occurrence"] else "Unknown"
                    )

                    # Format duration
                    duration_seconds = test["streak_duration"]
                    if duration_seconds < 60 * 60:  # Less than an hour
                        duration = f"{duration_seconds//60} min"
                    elif duration_seconds < 24 * 60 * 60:  # Less than a day
                        duration = f"{duration_seconds//(60*60)} hours"
                    else:  # Days
                        duration = f"{duration_seconds//(24*60*60)} days"

                    hysteresis_table.add_row(
                        test["nodeid"],
                        str(test["failure_count"]),
                        str(test["pass_count"]),
                        f"{test['failure_rate']:.2%}",
                        first_occurrence,
                        last_occurrence,
                        duration,
                    )

                console.print(hysteresis_table)

                if len(predominantly_failing) > 5:
                    console.print(
                        f"[dim]...and {len(predominantly_failing) - 5} more predominantly failing tests with hysteresis[/dim]"
                    )

            # Comparison analysis if requested
            if compare_with:
                console.print(Panel("[bold]Comparison Analysis[/bold]"))

                # Parse the comparison criteria
                if ":" in compare_with:
                    compare_type, compare_value = compare_with.split(":", 1)
                else:
                    compare_type, compare_value = "days", compare_with

                comparison = api.compare()

                if compare_type == "days":
                    try:
                        days_ago = int(compare_value)
                        cutoff_date = datetime.now() - timedelta(days=days_ago)

                        # Get current sessions (already filtered above)
                        current_sessions = filtered_sessions

                        # Get previous sessions with the same filters but different date range
                        prev_query = api.query()
                        if sut_filter:
                            prev_query = prev_query.filter_by_sut(sut_filter)
                        if test_pattern:
                            prev_query = prev_query.filter_by_test_name(test_pattern)

                        prev_query = prev_query.filter_by_date(
                            before=cutoff_date, after=cutoff_date - timedelta(days=days_ago)
                        )
                        previous_sessions = prev_query.execute()

                        # Compare the two sets
                        comparison_result = comparison.compare_sessions(
                            current_sessions,
                            previous_sessions,
                            label_a=f"Last {days} days",
                            label_b=f"Previous {days_ago} days",
                        )

                        # Display comparison results
                        comp_table = Table(title="Comparison Results")
                        comp_table.add_column("Metric", style="cyan")
                        comp_table.add_column(f"Last {days} days", style="green")
                        comp_table.add_column(f"Previous {days_ago} days", style="blue")
                        comp_table.add_column("Change", style="yellow")

                        # Add comparison metrics
                        current_pass_rate = comparison_result.pass_rate_a
                        previous_pass_rate = comparison_result.pass_rate_b
                        pass_rate_change = current_pass_rate - previous_pass_rate

                        current_duration = comparison_result.avg_duration_a
                        previous_duration = comparison_result.avg_duration_b
                        duration_change = current_duration - previous_duration

                        comp_table.add_row(
                            "Pass Rate",
                            f"{current_pass_rate:.2%}",
                            f"{previous_pass_rate:.2%}",
                            f"{pass_rate_change:+.2%}",
                        )

                        comp_table.add_row(
                            "Avg Duration",
                            f"{current_duration:.3f}s",
                            f"{previous_duration:.3f}s",
                            f"{duration_change:+.3f}s",
                        )

                        console.print(comp_table)

                        # Show newly failing tests
                        if comparison_result.newly_failing:
                            console.print("[bold red]Newly Failing Tests:[/bold red]")
                            for test in comparison_result.newly_failing[:5]:  # Limit to 5
                                console.print(f"  • {test}")

                        # Show newly passing tests
                        if comparison_result.newly_passing:
                            console.print("[bold green]Newly Passing Tests:[/bold green]")
                            for test in comparison_result.newly_passing[:5]:  # Limit to 5
                                console.print(f"  • {test}")

                    except ValueError:
                        console.print("[bold red]Invalid comparison value. Must be a number of days.[/bold red]")

                elif compare_type == "version":
                    # Compare with a specific version
                    version_query = api.query().filter_by_sut(sut_filter).filter_by_version(compare_value)
                    version_sessions = version_query.execute()

                    if version_sessions:
                        comparison_result = comparison.compare_sessions(
                            filtered_sessions, version_sessions, label_a="Current", label_b=f"Version {compare_value}"
                        )

                        # Display comparison results (similar to above)
                        # ...
                    else:
                        console.print(f"[bold red]No sessions found for version {compare_value}[/bold red]")

            # Show trends if requested
            if show_trends:
                console.print(Panel("[bold]Trend Analysis[/bold]"))

                # Group sessions by date
                date_groups = {}
                for session in filtered_sessions:
                    date_key = session.timestamp.date()
                    if date_key not in date_groups:
                        date_groups[date_key] = []
                    date_groups[date_key].append(session)

                # Calculate daily metrics
                dates = sorted(date_groups.keys())
                pass_rates = []
                durations = []

                for date in dates:
                    daily_sessions = date_groups[date]
                    daily_analysis = Analysis(sessions=daily_sessions)

                    pass_rates.append(daily_analysis.calculate_pass_rate())
                    durations.append(daily_analysis.calculate_average_duration())

                # Display trend data
                trend_table = Table(title="Daily Trends")
                trend_table.add_column("Date", style="cyan")
                trend_table.add_column("Pass Rate", style="green")
                trend_table.add_column("Avg Duration (s)", style="yellow")

                for i, date in enumerate(dates):
                    trend_table.add_row(date.strftime("%Y-%m-%d"), f"{pass_rates[i]:.2%}", f"{durations[i]:.3f}")

                console.print(trend_table)

            # Output format handling
            if output_format == "json":
                # Create a JSON-friendly structure
                result = {
                    "summary": {
                        "total_sessions": len(filtered_sessions),
                        "total_tests": total_tests,
                        "pass_rate": pass_rate,
                        "avg_duration": avg_duration,
                        "flaky_tests_count": len(flaky_tests),
                    },
                    "slowest_tests": [{"name": name, "duration": dur} for name, dur in slowest_tests],
                    "most_failing": [{"name": name, "failures": count} for name, count in most_failing],
                    "flaky_tests": [name for name in flaky_tests],
                }

                # Print JSON output
                print(json.dumps(result, indent=2))
        except Exception as e:
            console.print(f"[bold red]Error during analysis:[/bold red] {str(e)}")


def main():
    """Main function to run the analysis CLI."""
    console = Console()

    parser = argparse.ArgumentParser(description="Analyze pytest-insight test data")
    parser.add_argument(
        "--path",
        "-p",
        type=str,
        help="Path to the JSON data file (default: ~/.pytest_insight/practice.json)",
    )
    parser.add_argument("--sut", "-s", type=str, help="Filter by System Under Test name")
    parser.add_argument("--days", "-d", type=int, help="Filter to sessions from the last N days")
    parser.add_argument("--test", "-t", type=str, help="Filter by test name pattern (supports wildcards)")
    parser.add_argument("--profile", type=str, help="Use a specific storage profile")
    parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text", help="Output format (default: text)"
    )
    parser.add_argument(
        "--compare", "-c", type=str, help="Compare with previous data (format: days:N or version:X.Y.Z)"
    )
    parser.add_argument("--trends", action="store_true", help="Show trends over time")
    parser.add_argument("--list-profiles", action="store_true", help="List available storage profiles")
    parser.add_argument("--generate-sample", action="store_true", help="Generate sample test data if none exists")
    parser.add_argument("--version", "-v", action="store_true", help="Show version information")

    args = parser.parse_args()

    if args.version:
        from importlib.metadata import version

        try:
            ver = version("pytest-insight")
            console.print(f"[bold]pytest-insight version:[/bold] {ver}")
        except:
            console.print("[bold]pytest-insight version:[/bold] unknown")
        return

    if args.list_profiles:
        # List available profiles
        profile_manager = ProfileManager()
        profiles = profile_manager.list_profiles()

        if not profiles:
            console.print("[bold yellow]No storage profiles found.[/bold yellow]")
            return

        profile_table = Table(title="Available Storage Profiles")
        profile_table.add_column("Name", style="cyan")
        profile_table.add_column("Type", style="green")
        profile_table.add_column("Path", style="blue")
        profile_table.add_column("Active", style="yellow")

        active_profile = profile_manager.get_active_profile()

        for name, profile in profiles.items():
            is_active = name == active_profile.name if active_profile else False
            profile_table.add_row(name, profile.storage_type, str(profile.file_path), "✓" if is_active else "")

        console.print(profile_table)
        return

    # Determine data path
    data_path = None
    if args.path:
        data_path = Path(args.path)
    else:
        # Try to find data in the default location
        default_path = Path.home() / ".pytest_insight" / "practice.json"
        if default_path.exists():
            data_path = default_path
        else:
            # Try to find any JSON file in the default directory
            default_dir = Path.home() / ".pytest_insight"
            if default_dir.exists() and default_dir.is_dir():
                json_files = list(default_dir.glob("*.json"))
                if json_files:
                    data_path = json_files[0]
                    console.print(f"[yellow]No practice.json found, using {data_path.name} instead[/yellow]")

    # Generate sample data if requested or if no data exists
    if (args.generate_sample or (data_path is None or not data_path.exists())) and not args.path:
        if not args.generate_sample:
            console.print("[yellow]No test data found. Generating sample data...[/yellow]")
        else:
            console.print("[green]Generating sample test data...[/green]")

        # Create default directory if it doesn't exist
        default_dir = Path.home() / ".pytest_insight"
        default_dir.mkdir(parents=True, exist_ok=True)

        # Generate sample data
        import random
        from datetime import datetime, timedelta

        # Create sample test sessions
        sample_data = []

        # Generate data for the last 7 days
        for day in range(7):
            session_date = datetime.now() - timedelta(days=day)

            # Create 1-3 sessions per day
            for session_num in range(random.randint(1, 3)):
                session = {
                    "session_id": f"sample-{day}-{session_num}",
                    "sut_name": "sample-app",
                    "version": "1.0.0",
                    "timestamp": (session_date - timedelta(hours=random.randint(0, 23))).isoformat(),
                    "session_duration": random.uniform(5.0, 30.0),
                    "test_results": [],
                }

                # Add 10-20 tests per session
                for test_num in range(random.randint(10, 20)):
                    test_type = random.choice(["api", "ui", "unit", "integration"])
                    test_name = (
                        f"test_{test_type}_{random.choice(['login', 'logout', 'create', 'update', 'delete', 'search'])}"
                    )

                    # Randomize outcomes with a bias toward passing
                    outcome = random.choices(
                        ["passed", "failed", "skipped", "xfailed", "xpassed"], weights=[0.7, 0.15, 0.1, 0.03, 0.02]
                    )[0]

                    test = {
                        "nodeid": f"tests/{test_type}/{test_name}.py::test_function_{test_num}",
                        "outcome": outcome,
                        "duration": random.uniform(0.1, 5.0),
                        "timestamp": (
                            session_date - timedelta(hours=random.randint(0, 23), minutes=random.randint(0, 59))
                        ).isoformat(),
                    }

                    session["test_results"].append(test)

                sample_data.append(session)

        # Save the sample data
        data_path = default_dir / "practice.json"
        with open(data_path, "w") as f:
            json.dump(sample_data, f, indent=2)

        console.print(f"[green]Sample data generated at {data_path}[/green]")

    if data_path is None or not data_path.exists():
        console.print(
            Panel(
                "[bold red]Error: No test data found.[/bold red]\n\n"
                "To generate test data, run:\n"
                "  [bold]insight-gen --days 14[/bold]\n\n"
                "Or generate sample data with:\n"
                "  [bold]insights --generate-sample[/bold]\n\n"
                "Or specify a custom path:\n"
                "  [bold]insights --path /path/to/your/data.json[/bold]"
            )
        )
        return

    # Analyze the data
    analyze_test_data(
        data_path=data_path,
        sut_filter=args.sut,
        days=args.days,
        output_format=args.format,
        test_pattern=args.test,
        profile=args.profile,
        compare_with=args.compare,
        show_trends=args.trends,
    )

    console.print(
        Panel(
            "[bold green]Analysis complete![/bold green]\n\n"
            "[bold]Advanced Usage Examples:[/bold]\n"
            "  • Compare with previous period:\n"
            "    [cyan]insights --days 7 --compare days:7[/cyan]\n\n"
            "  • Compare with specific version:\n"
            "    [cyan]insights --sut my-app --compare version:1.2.3[/cyan]\n\n"
            "  • Show trends over time:\n"
            "    [cyan]insights --days 30 --trends[/cyan]\n\n"
            "  • Filter by test pattern:\n"
            "    [cyan]insights --test 'test_login*'[/cyan]\n\n"
            "  • Output as JSON for further processing:\n"
            "    [cyan]insights --format json > analysis.json[/cyan]"
        )
    )


if __name__ == "__main__":
    main()
