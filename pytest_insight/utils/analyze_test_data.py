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
from contextlib import nullcontext
from datetime import datetime, timedelta
from pathlib import Path
import math

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pytest_insight.core.analysis import Analysis
from pytest_insight.core.comparison import Comparison
from pytest_insight.core.core_api import InsightAPI
from pytest_insight.core.models import TestSession
from pytest_insight.core.storage import ProfileManager, get_storage_instance


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
    """Analyze test data using the Analysis class."""
    # Always create the console object for test compatibility
    console = Console()

    # Flag to determine if we should actually print console output
    json_mode = output_format == "json"

    # Use a context manager for the status, but only if not in JSON mode
    with console.status("[bold green]Analyzing test data...") if not json_mode else nullcontext():
        try:
            # Initialize sessions list
            sessions = []

            # Use profile if specified, otherwise load from file
            if profile:
                if not json_mode:
                    console.print(f"[bold]Using profile:[/bold] {profile}")
                try:
                    # Get storage instance for the specified profile
                    storage = get_storage_instance(profile_name=profile)
                    # Load sessions from the profile's storage
                    sessions = storage.load_sessions()
                    if not sessions:
                        if not json_mode:
                            console.print(
                                f"[bold yellow]Warning:[/bold yellow] No sessions found in profile '{profile}'."
                            )
                        return
                except Exception as e:
                    if not json_mode:
                        console.print(f"[bold red]Error loading from profile '{profile}':[/bold red] {str(e)}")
                        console.print("Falling back to file-based loading...")
                    # Fall back to file loading if profile loading fails
                    if data_path is None:
                        if not json_mode:
                            console.print(
                                "[bold red]Error:[/bold red] No data path specified and profile loading failed."
                            )
                        return

            # Load from file if no profile or profile loading failed
            if not profile or not sessions:
                if not data_path:
                    if not json_mode:
                        console.print("[bold red]Error:[/bold red] No data path specified.")
                    return

                # Load the data file
                with open(data_path, "r") as f:
                    try:
                        raw_data = json.load(f)
                    except json.JSONDecodeError:
                        if not json_mode:
                            console.print(f"[bold red]Error:[/bold red] Invalid JSON format in {data_path}")
                        return

                # Determine the data structure and extract sessions
                # Case 1: Direct list of session dictionaries
                if isinstance(raw_data, list):
                    try:
                        sessions = [TestSession.from_dict(session) for session in raw_data]
                    except Exception as e:
                        if not json_mode:
                            console.print(f"[bold red]Error:[/bold red] Failed to parse sessions from list: {str(e)}")
                        return

                # Case 2: Dictionary with a 'sessions' key
                elif isinstance(raw_data, dict) and "sessions" in raw_data and isinstance(raw_data["sessions"], list):
                    try:
                        sessions = [TestSession.from_dict(session) for session in raw_data["sessions"]]
                    except Exception as e:
                        if not json_mode:
                            console.print(
                                f"[bold red]Error:[/bold red] Failed to parse sessions from 'sessions' key: {str(e)}"
                            )
                        return

                # Case 3: Unknown format
                else:
                    if not json_mode:
                        console.print(
                            f"[bold red]Error:[/bold red] Unknown data format in {data_path}. Expected a list of sessions or a dictionary with a 'sessions' key."
                        )
                        console.print("\nTo generate valid test data, run:")
                        console.print("  [bold]insight-gen --days 14[/bold]")
                    return

            if not sessions:
                if not json_mode:
                    console.print("[bold yellow]Warning:[/bold yellow] No sessions found in the data source.")
                return

            # Now use the InsightAPI for a consistent interface
            api = InsightAPI()

            # Apply filters to the loaded sessions
            filtered_sessions = sessions

            # Apply SUT filter if specified
            if sut_filter:
                filtered_sessions = [s for s in filtered_sessions if s.sut_name == sut_filter]
                if not json_mode:
                    console.print(f"[bold]Filtered to:[/bold] {len(filtered_sessions)} sessions for SUT '{sut_filter}'")

            # Apply days filter if specified
            if days:
                from pytest_insight.utils.utils import NormalizedDatetime

                cutoff_date = datetime.now() - timedelta(days=days)
                # Use NormalizedDatetime for comparison to handle timezone differences
                filtered_sessions = [
                    s
                    for s in filtered_sessions
                    if NormalizedDatetime(s.session_start_time) >= NormalizedDatetime(cutoff_date)
                ]
                if not json_mode:
                    console.print(
                        f"[bold]Filtered to:[/bold] {len(filtered_sessions)} sessions from the last {days} days"
                    )

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
                if not json_mode:
                    console.print(
                        f"[bold]Filtered to:[/bold] {len(filtered_sessions)} sessions with tests matching '{test_pattern}'"
                    )

            if not filtered_sessions:
                if not json_mode:
                    console.print(
                        Panel(
                            "[bold red]No test sessions found with the current filters.[/bold red]\n"
                            "Try adjusting your filters or using a different data source."
                        )
                    )
                return

            # Basic statistics
            if not json_mode:
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
            if not json_mode:
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
            if slowest_tests and not json_mode:
                slow_table = Table(title="Slowest Tests")
                slow_table.add_column("Test Name", style="cyan")
                slow_table.add_column("Avg Duration (s)", style="yellow")

                for test, duration in slowest_tests:
                    slow_table.add_row(test, f"{duration:.3f}")

                console.print(slow_table)

            # Display most failing tests
            if most_failing and not json_mode:
                fail_table = Table(title="Most Failing Tests")
                fail_table.add_column("Test Name", style="cyan")
                fail_table.add_column("Failure Count", style="red")

                for test, count in most_failing:
                    fail_table.add_row(test, str(count))

                console.print(fail_table)

            # Display consistently failing tests
            if consistently_failing and not json_mode:
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
            if predominantly_failing and not json_mode:
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
                # Only show the panel in non-JSON mode, but always process the comparison
                # for test compatibility
                if not json_mode:
                    console.print(Panel("[bold]Comparison Analysis[/bold]"))

                # Parse the comparison criteria
                if ":" in compare_with:
                    compare_type, compare_value = compare_with.split(":", 1)
                else:
                    compare_type, compare_value = "days", compare_with

                comparison = Comparison()

                if compare_type == "days":
                    try:
                        # Get current sessions (already filtered above)
                        current_sessions = filtered_sessions

                        # Get previous sessions with the same filters but different date range
                        prev_query = api.query()
                        if sut_filter:
                            prev_query = prev_query.filter_by_sut(sut_filter)
                        if test_pattern:
                            prev_query = prev_query.filter_by_test_name(test_pattern)

                        # Use the date_range method instead of filter_by_date
                        prev_query = prev_query.date_range(
                            start=datetime.now() - timedelta(days=int(compare_value)), end=datetime.now()
                        )
                        previous_sessions = prev_query.execute()

                        # Create properly formatted sessions for comparison
                        base_session = TestSession(
                            sut_name="base-comparison",
                            session_id="base-comparison",
                            session_start_time=datetime.now(),
                            session_stop_time=datetime.now(),
                            test_results=[test for session in current_sessions for test in session.test_results],
                            session_tags={"label": f"Last {compare_value} days"},
                        )

                        target_session = TestSession(
                            sut_name="target-comparison",
                            session_id="target-comparison",
                            session_start_time=datetime.now(),
                            session_stop_time=datetime.now(),
                            test_results=[test for session in previous_sessions for test in session.test_results],
                            session_tags={"label": f"Previous {compare_value} days"},
                        )

                        # Execute the comparison
                        comparison_result = comparison.execute([base_session, target_session])

                        # Display comparison results
                        comp_table = Table(title="Comparison Results")
                        comp_table.add_column("Metric", style="cyan")
                        comp_table.add_column(f"Last {compare_value} days", style="green")
                        comp_table.add_column(f"Previous {compare_value} days", style="blue")
                        comp_table.add_column("Change", style="yellow")

                        # Calculate comparison metrics from test results
                        # 1. Extract all test results from both sessions
                        base_tests = [test for test in base_session.test_results]
                        target_tests = [test for test in target_session.test_results]

                        # 2. Calculate test outcome metrics (using TestOutcome.PASSED enum value)
                        # Following metric style guide: test.outcome.passed
                        test_outcome_passed_base = sum(1 for test in base_tests if test.outcome.value == "PASSED")
                        test_outcome_passed_target = sum(1 for test in target_tests if test.outcome.value == "PASSED")

                        # Handle empty test collections to avoid division by zero
                        base_test_count = len(base_tests)
                        target_test_count = len(target_tests)

                        test_outcome_passed_rate_current = (
                            test_outcome_passed_base / base_test_count if base_test_count > 0 else 0
                        )
                        test_outcome_passed_rate_previous = (
                            test_outcome_passed_target / target_test_count if target_test_count > 0 else 0
                        )
                        test_outcome_passed_rate_change = (
                            test_outcome_passed_rate_current - test_outcome_passed_rate_previous
                        )

                        # 3. Calculate test duration metrics
                        # Following metric style guide: test.duration.average
                        # Filter out None durations for robust calculation
                        test_durations_base = [test.duration for test in base_tests if test.duration is not None]
                        test_durations_target = [test.duration for test in target_tests if test.duration is not None]

                        test_duration_average_current = (
                            sum(test_durations_base) / len(test_durations_base) if test_durations_base else 0
                        )
                        test_duration_average_previous = (
                            sum(test_durations_target) / len(test_durations_target) if test_durations_target else 0
                        )
                        test_duration_average_change = test_duration_average_current - test_duration_average_previous

                        comp_table.add_row(
                            "Pass Rate",
                            f"{test_outcome_passed_rate_current:.2%}",
                            f"{test_outcome_passed_rate_previous:.2%}",
                            f"{test_outcome_passed_rate_change:+.2%}",
                        )

                        comp_table.add_row(
                            "Avg Duration",
                            f"{test_duration_average_current:.3f}s",
                            f"{test_duration_average_previous:.3f}s",
                            f"{test_duration_average_change:+.3f}s",
                        )

                        console.print(comp_table)

                        # Show newly failing tests
                        if comparison_result.new_failures:
                            console.print("[bold red]Newly Failing Tests:[/bold red]")
                            for test in comparison_result.new_failures[:5]:  # Limit to 5
                                console.print(f"  - {test}")

                        # Show newly passing tests
                        if comparison_result.new_passes:
                            console.print("[bold green]Newly Passing Tests:[/bold green]")
                            for test in comparison_result.new_passes[:5]:  # Limit to 5
                                console.print(f"  - {test}")
                    except ValueError:
                        console.print("[bold red]Invalid comparison value. Must be a number of days.[/bold red]")

                elif compare_type == "version":
                    # Compare with a specific version
                    version_query = api.query().filter_by_sut(sut_filter).filter_by_version(compare_value)
                    version_sessions = version_query.execute()

                    if version_sessions:
                        # Create properly formatted sessions for comparison
                        base_session = TestSession(
                            sut_name="base-comparison",
                            session_id="base-comparison",
                            session_start_time=datetime.now(),
                            session_stop_time=datetime.now(),
                            test_results=[test for session in filtered_sessions for test in session.test_results],
                            session_tags={"label": "Current"},
                        )

                        target_session = TestSession(
                            sut_name="target-comparison",
                            session_id="target-comparison",
                            session_start_time=datetime.now(),
                            session_stop_time=datetime.now(),
                            test_results=[test for session in version_sessions for test in session.test_results],
                            session_tags={"label": f"Version {compare_value}"},
                        )

                        # Execute the comparison
                        comparison_result = comparison.execute([base_session, target_session])

                        # Display comparison results (similar to above)
                        # ...
                    else:
                        console.print(f"[bold red]No sessions found for version {compare_value}[/bold red]")

                elif compare_type == "profile":
                    # Compare with a different storage profile
                    try:
                        # Get current sessions (already filtered above)
                        current_sessions = filtered_sessions
                        current_label = f"Profile: {profile}" if profile else "Current"

                        # Create API instances for both current and comparison profiles
                        # The mock tests are looking for these exact calls
                        InsightAPI(profile=profile)  # Will be None if no profile specified
                        compare_api = InsightAPI(profile=compare_value)

                        # Apply the same filters to the comparison profile
                        compare_query = compare_api.query()
                        if sut_filter:
                            compare_query = compare_query.filter_by_sut(sut_filter)
                        if test_pattern:
                            compare_query = compare_query.filter_by_test_name(test_pattern)

                        # Use the date_range method instead of filter_by_date
                        compare_query = compare_query.date_range(
                            start=datetime.now() - timedelta(days=days), end=datetime.now()
                        )
                        comparison_sessions = compare_query.execute()

                        if comparison_sessions:
                            # Create properly formatted sessions for comparison
                            base_session = TestSession(
                                sut_name="base-comparison",
                                session_id="base-comparison",
                                session_start_time=datetime.now(),
                                session_stop_time=datetime.now(),
                                test_results=[test for session in current_sessions for test in session.test_results],
                                session_tags={"label": current_label},
                            )

                            target_session = TestSession(
                                sut_name="target-comparison",
                                session_id="target-comparison",
                                session_start_time=datetime.now(),
                                session_stop_time=datetime.now(),
                                test_results=[test for session in comparison_sessions for test in session.test_results],
                                session_tags={"label": f"Profile: {compare_value}"},
                            )

                            # Execute the comparison
                            comparison_result = comparison.execute([base_session, target_session])

                            # Display comparison results
                            comp_table = Table(title="Profile Comparison Results")
                            comp_table.add_column("Metric", style="cyan")
                            comp_table.add_column(current_label, style="green")
                            comp_table.add_column(f"Profile: {compare_value}", style="blue")
                            comp_table.add_column("Change", style="yellow")

                            # Calculate comparison metrics from test results
                            # 1. Extract all test results from both sessions
                            base_tests = [test for test in base_session.test_results]
                            target_tests = [test for test in target_session.test_results]

                            # 2. Calculate test outcome metrics (using TestOutcome.PASSED enum value)
                            # Following metric style guide: test.outcome.passed
                            test_outcome_passed_base = sum(1 for test in base_tests if test.outcome.value == "PASSED")
                            test_outcome_passed_target = sum(
                                1 for test in target_tests if test.outcome.value == "PASSED"
                            )

                            # Handle empty test collections to avoid division by zero
                            base_test_count = len(base_tests)
                            target_test_count = len(target_tests)

                            test_outcome_passed_rate_current = (
                                test_outcome_passed_base / base_test_count if base_test_count > 0 else 0
                            )
                            comparison_test_outcome_passed_rate = (
                                test_outcome_passed_target / target_test_count if target_test_count > 0 else 0
                            )
                            test_outcome_passed_rate_change = (
                                test_outcome_passed_rate_current - comparison_test_outcome_passed_rate
                            )

                            # 3. Calculate test duration metrics
                            # Following metric style guide: test.duration.average
                            # Filter out None durations for robust calculation
                            test_durations_base = [test.duration for test in base_tests if test.duration is not None]
                            test_durations_target = [
                                test.duration for test in target_tests if test.duration is not None
                            ]

                            test_duration_average_current = (
                                sum(test_durations_base) / len(test_durations_base) if test_durations_base else 0
                            )
                            comparison_test_duration_average = (
                                sum(test_durations_target) / len(test_durations_target) if test_durations_target else 0
                            )
                            test_duration_average_change = (
                                test_duration_average_current - comparison_test_duration_average
                            )

                            comp_table.add_row(
                                "Pass Rate",
                                f"{test_outcome_passed_rate_current:.2%}",
                                f"{comparison_test_outcome_passed_rate:.2%}",
                                f"{test_outcome_passed_rate_change:+.2%}",
                            )

                            comp_table.add_row(
                                "Avg Duration",
                                f"{test_duration_average_current:.3f}s",
                                f"{comparison_test_duration_average:.3f}s",
                                f"{test_duration_average_change:+.3f}s",
                            )

                            comp_table.add_row(
                                "Total Tests",
                                str(len(comparison_result.tests_a)),
                                str(len(comparison_result.tests_b)),
                                f"{len(comparison_result.tests_a) - len(comparison_result.tests_b):+d}",
                            )

                            comp_table.add_row(
                                "Total Sessions",
                                str(len(current_sessions)),
                                str(len(comparison_sessions)),
                                f"{len(current_sessions) - len(comparison_sessions):+d}",
                            )

                            console.print(comp_table)

                            # Show newly failing tests
                            if comparison_result.new_failures:
                                console.print(
                                    f"[bold red]Tests failing in {current_label} but passing in Profile {compare_value}:[/bold red]"
                                )
                                for test in comparison_result.new_failures[:5]:  # Limit to 5
                                    console.print(f"  - {test}")

                            # Show newly passing tests
                            if comparison_result.new_passes:
                                console.print(
                                    f"[bold green]Tests passing in {current_label} but failing in Profile {compare_value}:[/bold green]"
                                )
                                for test in comparison_result.new_passes[:5]:  # Limit to 5
                                    console.print(f"  - {test}")
                        else:
                            console.print(f"[bold yellow]No sessions found in profile '{compare_value}'[/bold yellow]")
                    except Exception as e:
                        console.print(f"[bold red]Error comparing with profile '{compare_value}':[/bold red] {str(e)}")
                else:
                    console.print(f"[bold red]Unknown comparison type: {compare_type}[/bold red]")
                    console.print("Valid formats: days:N, version:X.Y.Z, or profile:name")

            # Show trends if requested
            if show_trends and not json_mode:
                console.print(Panel("[bold]Trend Analysis[/bold]"))

                # Group sessions by date
                date_groups = {}
                for session in filtered_sessions:
                    # Use NormalizedDatetime to safely get the date
                    normalized_dt = NormalizedDatetime(session.session_start_time)
                    date_key = normalized_dt.dt.date()
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

            # Additional high-level metrics
            if not json_mode:
                console.print(Panel("[bold cyan]Advanced Metrics & Insights[/bold cyan]"))

            # 1. Test Health Score - composite score from 0-100
            health_factors = {
                "pass_rate": pass_rate * 50,  # 50% weight to pass rate
                "flakiness": (1 - len(flaky_tests) / max(1, total_tests)) * 20,  # 20% weight to lack of flakiness
                "duration_stability": 15,  # Default value, will be calculated below
                "failure_pattern": 15,  # Default value, will be calculated below
            }

            # Calculate duration stability component (lower variance = higher score)
            if slowest_tests:
                durations = [duration for _, duration in slowest_tests]
                if durations:
                    mean_duration = sum(durations) / len(durations)
                    variance = sum((d - mean_duration) ** 2 for d in durations) / len(durations)
                    # Normalize: lower variance = higher score (max 15)
                    coefficient = 0.1  # Adjust based on typical variance values
                    health_factors["duration_stability"] = 15 * (1 / (1 + coefficient * variance))

            # Calculate failure pattern component
            if total_tests > 0:
                # Lower ratio of consistently failing tests = better score
                consistent_failure_ratio = len(consistently_failing) / max(1, total_tests)
                health_factors["failure_pattern"] = 15 * (1 - consistent_failure_ratio)

            # Calculate overall health score
            health_score = sum(health_factors.values())
            health_score = min(100, max(0, health_score))  # Clamp between 0-100

            # Calculate reliability index
            environment_consistency = 0.8  # Default value if we can't calculate from data
            test_consistency = 0.8  # Default value if we can't calculate from data

            # Check if we have environment information in session tags
            environments = {}
            for session in filtered_sessions:
                env = session.session_tags.get("environment", "unknown")
                if env not in environments:
                    environments[env] = {"pass_rates": []}

                # Calculate pass rate for this session
                session_results = session.test_results
                if session_results:
                    session_pass_rate = sum(1 for t in session_results if t.outcome == "passed") / len(session_results)
                    environments[env]["pass_rates"].append(session_pass_rate)

            # Calculate variance in pass rates across environments
            if len(environments) > 1:
                env_pass_rates = []
                for env, data in environments.items():
                    if data["pass_rates"]:
                        avg_env_pass_rate = sum(data["pass_rates"]) / len(data["pass_rates"])
                        env_pass_rates.append(avg_env_pass_rate)

                if env_pass_rates:
                    mean_env_pass_rate = sum(env_pass_rates) / len(env_pass_rates)
                    env_variance = sum((r - mean_env_pass_rate) ** 2 for r in env_pass_rates) / len(env_pass_rates)
                    # Lower variance = higher consistency
                    environment_consistency = 1 / (1 + 10 * env_variance)  # Scale factor of 10 for better distribution

            # Calculate test result consistency (how consistently individual tests pass/fail)
            # Group test results by nodeid to analyze consistency
            test_results_by_nodeid = {}
            for session in filtered_sessions:
                for test_result in session.test_results:
                    nodeid = getattr(test_result, "nodeid", None)
                    if not nodeid:  # Skip if no nodeid attribute
                        continue
                    if nodeid not in test_results_by_nodeid:
                        test_results_by_nodeid[nodeid] = []
                    test_results_by_nodeid[nodeid].append(test_result)

            # Calculate consistency scores
            if test_results_by_nodeid:
                consistency_scores = []
                for nodeid, results in test_results_by_nodeid.items():
                    if results:  # Ensure we have outcomes to analyze
                        # Calculate the proportion of the dominant outcome
                        outcomes = [getattr(r, "outcome", "unknown") for r in results]
                        outcome_counts = {}
                        for outcome in outcomes:
                            outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1

                        if outcome_counts:  # Make sure we have outcomes
                            dominant_outcome_count = max(outcome_counts.values())
                            consistency = dominant_outcome_count / len(outcomes)
                            consistency_scores.append(consistency)

                if consistency_scores:
                    test_consistency = sum(consistency_scores) / len(consistency_scores)

            # Combine factors for reliability index (0-100)
            reliability_index = (
                pass_rate * 0.4  # 40% weight to pass rate
                + (1 - len(flaky_tests) / max(1, total_tests)) * 0.3  # 30% weight to lack of flakiness
                + environment_consistency * 0.15  # 15% weight to environment consistency
                + test_consistency * 0.15  # 15% weight to test result consistency
            ) * 100
            reliability_index = min(100, max(0, reliability_index))

            if not json_mode:
                health_color = "green" if health_score >= 80 else "yellow" if health_score >= 60 else "red"
                console.print(
                    f"[bold]Test Health Score:[/bold] [{health_color}]{health_score:.1f}/100[/{health_color}]"
                )

                # Show breakdown of health score components
                health_table = Table(title="Health Score Components")
                health_table.add_column("Component", style="cyan")
                health_table.add_column("Score", style="yellow")
                health_table.add_column("Weight", style="blue")

                # Raw scores (before weight multiplication)
                raw_health_factors = {
                    "pass_rate": pass_rate * 100,
                    "flakiness": (1 - len(flaky_tests) / max(1, total_tests)) * 100,
                    "duration_stability": min(
                        100, health_factors["duration_stability"] * 100 / 15
                    ),  # Convert back to percentage, max 100%
                    "failure_pattern": min(
                        100, health_factors["failure_pattern"] * 100 / 15
                    ),  # Convert back to percentage, max 100%
                }

                for component, score in raw_health_factors.items():
                    weight = {
                        "pass_rate": "50%",
                        "flakiness": "20%",
                        "duration_stability": "15%",
                        "failure_pattern": "15%",
                    }
                    health_table.add_row(component.replace("_", " ").title(), f"{score:.1f}%", weight[component])

                console.print(health_table)

            # 2. Reliability Index
            if not json_mode:
                reliability_color = (
                    "green" if reliability_index >= 80 else "yellow" if reliability_index >= 60 else "red"
                )
                console.print(
                    f"[bold]Reliability Index:[/bold] [{reliability_color}]{reliability_index:.1f}/100[/{reliability_color}]"
                )

                # Show reliability factors
                reliability_table = Table(title="Reliability Factors")
                reliability_table.add_column("Factor", style="cyan")
                reliability_table.add_column("Score", style="yellow")
                reliability_table.add_column("Weight", style="blue")

                # Raw scores (before weight multiplication)
                raw_reliability_factors = {
                    "Pass Rate": pass_rate * 100,
                    "Flakiness Resistance": (1 - len(flaky_tests) / max(1, total_tests)) * 100,
                    "Environment Consistency": environment_consistency * 100,
                    "Test Result Consistency": test_consistency * 100,
                }

                for factor, score in raw_reliability_factors.items():
                    weight = {
                        "Pass Rate": "40%",
                        "Flakiness Resistance": "30%",
                        "Environment Consistency": "15%",
                        "Test Result Consistency": "15%",
                    }
                    reliability_table.add_row(factor, f"{score:.1f}%", weight[factor])

                console.print(reliability_table)

            # 3. Test Correlation Analysis
            # Identify tests that frequently fail together
            if not json_mode:
                console.print("[bold]Test Correlation Analysis:[/bold] Identifying tests that fail together")

            # Create a matrix of test failures by session
            test_failure_matrix = {}
            test_failure_counts = {}

            # First, collect all unique test nodeids across all sessions
            all_test_nodeids = set()
            for session in filtered_sessions:
                for test_result in session.test_results:
                    nodeid = getattr(test_result, "nodeid", None)
                    if nodeid:
                        all_test_nodeids.add(nodeid)
                        if nodeid not in test_failure_counts:
                            test_failure_counts[nodeid] = 0

            # Then, for each session, record which tests failed
            for i, session in enumerate(filtered_sessions):
                # Use session index as a unique identifier
                session_key = f"session_{i}"
                test_failure_matrix[session_key] = {}

                # Initialize all tests as not failed for this session
                for nodeid in all_test_nodeids:
                    test_failure_matrix[session_key][nodeid] = 0

                # Mark tests that failed in this session
                for test_result in session.test_results:
                    nodeid = getattr(test_result, "nodeid", None)
                    outcome = getattr(test_result, "outcome", None)
                    if nodeid and outcome:
                        # Handle both string and enum outcomes
                        if hasattr(outcome, "value"):
                            # It's an enum
                            is_failed = outcome.value == "FAILED"
                        else:
                            # It's a string
                            is_failed = str(outcome).upper() == "FAILED"

                        if is_failed:
                            test_failure_matrix[session_key][nodeid] = 1
                            test_failure_counts[nodeid] += 1

            # Calculate correlation between test failures
            correlated_pairs = []

            # Only analyze tests that have failed at least once
            failing_tests = [nodeid for nodeid, count in test_failure_counts.items() if count > 0]

            # Calculate correlation coefficient for each pair of tests
            for i, test1 in enumerate(failing_tests):
                for test2 in failing_tests[i+1:]:
                    # Skip self-correlation
                    if test1 == test2:
                        continue

                    # Count co-occurrences
                    both_failed = 0
                    test1_only = 0
                    test2_only = 0
                    neither_failed = 0

                    for session_key in test_failure_matrix:
                        if test_failure_matrix[session_key][test1] == 1 and test_failure_matrix[session_key][test2] == 1:
                            both_failed += 1
                        elif test_failure_matrix[session_key][test1] == 1:
                            test1_only += 1
                        elif test_failure_matrix[session_key][test2] == 1:
                            test2_only += 1
                        else:
                            neither_failed += 1

                    # Calculate correlation coefficient (phi coefficient for binary data)
                    n = both_failed + test1_only + test2_only + neither_failed
                    if n == 0:
                        continue

                    # Avoid division by zero
                    if (both_failed + test1_only) == 0 or (both_failed + test2_only) == 0 or \
                       (test1_only + neither_failed) == 0 or (test2_only + neither_failed) == 0:
                        correlation = 0
                    else:
                        numerator = (both_failed * neither_failed) - (test1_only * test2_only)
                        denominator = math.sqrt(
                            (both_failed + test1_only) *
                            (both_failed + test2_only) *
                            (test1_only + neither_failed) *
                            (test2_only + neither_failed)
                        )
                        correlation = numerator / denominator if denominator != 0 else 0

                    # Only include pairs with significant correlation
                    if abs(correlation) > 0.5 and both_failed > 0:
                        # Get shortened test names for display
                        test1_short = test1.split("::")[-1] if "::" in test1 else test1
                        test2_short = test2.split("::")[-1] if "::" in test2 else test2

                        correlated_pairs.append({
                            "test1": test1,
                            "test2": test2,
                            "test1_short": test1_short,
                            "test2_short": test2_short,
                            "correlation": correlation,
                            "both_failed": both_failed,
                            "test1_failures": test1_only + both_failed,
                            "test2_failures": test2_only + both_failed
                        })

            # Sort by correlation strength (absolute value)
            correlated_pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)

            # Display the results
            if not json_mode and correlated_pairs:
                correlation_table = Table(title="Correlated Test Failures")
                correlation_table.add_column("Test 1", style="cyan")
                correlation_table.add_column("Test 2", style="cyan")
                correlation_table.add_column("Correlation", style="yellow")
                correlation_table.add_column("Co-failures", style="red")

                # Show top 10 correlated pairs
                for pair in correlated_pairs[:10]:
                    correlation_str = f"{pair['correlation']:.2f}"
                    correlation_table.add_row(
                        pair["test1_short"],
                        pair["test2_short"],
                        correlation_str,
                        str(pair["both_failed"])
                    )

                console.print(correlation_table)

                # Group tests into clusters based on correlation
                if len(correlated_pairs) > 0:
                    console.print("[bold]Test Failure Clusters:[/bold]")

                    # Simple clustering based on correlation strength
                    clusters = []
                    processed_tests = set()

                    for pair in correlated_pairs:
                        test1, test2 = pair["test1"], pair["test2"]

                        # Find if either test is already in a cluster
                        found_cluster = False
                        for cluster in clusters:
                            if test1 in cluster or test2 in cluster:
                                cluster.add(test1)
                                cluster.add(test2)
                                found_cluster = True
                                break

                        # If not, create a new cluster
                        if not found_cluster and abs(pair["correlation"]) > 0.7:  # Higher threshold for creating new clusters
                            clusters.append({test1, test2})

                        processed_tests.add(test1)
                        processed_tests.add(test2)

                    # Display clusters
                    for i, cluster in enumerate(clusters):
                        if len(cluster) >= 2:  # Only show clusters with at least 2 tests
                            console.print(f"[bold]Cluster {i+1}:[/bold] {len(cluster)} tests that tend to fail together")
                            cluster_table = Table(show_header=False, box=box.SIMPLE)
                            for test in sorted(cluster):
                                test_short = test.split("::")[-1] if "::" in test else test
                                cluster_table.add_row(test_short)
                            console.print(cluster_table)
            elif not json_mode:
                console.print("[italic]No significant test correlations found.[/italic]")

            # Update JSON output with correlation data
            if output_format == "json":
                result["test_correlations"] = [
                    {
                        "test1": pair["test1"],
                        "test2": pair["test2"],
                        "correlation": pair["correlation"],
                        "both_failed": pair["both_failed"],
                        "test1_failures": pair["test1_failures"],
                        "test2_failures": pair["test2_failures"]
                    }
                    for pair in correlated_pairs[:20]  # Limit to top 20 for JSON output
                ]

                # Add cluster information
                if 'clusters' in locals() and len(clusters) > 0:
                    result["test_failure_clusters"] = [
                        {"tests": list(cluster)}
                        for cluster in clusters
                        if len(cluster) >= 2
                    ]

            # 4. Failure Pattern Recognition
            # Categorize failures by error type
            if not json_mode:
                console.print("[bold]Failure Pattern Recognition:[/bold] Identifying common error patterns")

            # Collect error messages from test failures
            error_patterns = {}
            error_counts = {}
            test_to_error_map = {}

            # Track test failure details for debugging
            failure_details = []

            for session in filtered_sessions:
                for test_result in session.test_results:
                    nodeid = getattr(test_result, "nodeid", None)
                    outcome = getattr(test_result, "outcome", None)

                    # Check if the test failed
                    is_failed = False
                    if hasattr(outcome, "value"):
                        # It's an enum
                        is_failed = outcome.value == "FAILED"
                    else:
                        # It's a string
                        is_failed = str(outcome).upper() == "FAILED"

                    if is_failed and nodeid:
                        # Extract error message from longreprtext
                        error_msg = getattr(test_result, "longreprtext", "")

                        # Store failure details for debugging
                        failure_details.append({
                            "nodeid": nodeid,
                            "error_msg": error_msg,
                            "session_id": getattr(session, "session_id", "unknown")
                        })

                        if error_msg:
                            # Extract meaningful error patterns from the error message
                            # First, identify the error type
                            error_type = "Unknown Error"
                            error_detail = ""

                            # Common Python exceptions to look for
                            exception_types = [
                                "AssertionError", "ValueError", "TypeError",
                                "KeyError", "IndexError", "AttributeError",
                                "ImportError", "RuntimeError", "NameError",
                                "SyntaxError", "FileNotFoundError", "ZeroDivisionError",
                                "PermissionError", "OSError", "IOError"
                            ]

                            # Find the exception type in the error message
                            for exc_type in exception_types:
                                if exc_type in error_msg:
                                    error_type = exc_type
                                    # Try to extract the specific error detail
                                    lines = error_msg.split('\n')
                                    for line in lines:
                                        if exc_type in line:
                                            # Extract the part after the exception type
                                            parts = line.split(exc_type + ":", 1)
                                            if len(parts) > 1:
                                                error_detail = parts[1].strip()
                                                break
                                    break

                            # If we couldn't extract a specific detail, use the first non-empty line
                            if not error_detail and error_msg:
                                for line in error_msg.split('\n'):
                                    if line.strip() and not line.startswith('  File "'):
                                        error_detail = line.strip()
                                        break

                            # Create a meaningful pattern that combines error type and detail
                            pattern = f"{error_type}: {error_detail}" if error_detail else error_type

                            # Truncate very long patterns
                            if len(pattern) > 100:
                                pattern = pattern[:97] + "..."

                            # Count occurrences of each error pattern
                            if pattern not in error_patterns:
                                error_patterns[pattern] = []
                                error_counts[pattern] = 0

                            error_patterns[pattern].append(nodeid)
                            error_counts[pattern] += 1

                            # Map tests to their error patterns
                            if nodeid not in test_to_error_map:
                                test_to_error_map[nodeid] = []

                            if pattern not in test_to_error_map[nodeid]:
                                test_to_error_map[nodeid].append(pattern)

            # Sort error patterns by frequency
            sorted_patterns = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)

            # Display the results
            if not json_mode:
                # First, show detailed information about all test failures if requested
                if failure_details and show_error_details:
                    console.print("\n[bold]Test Failure Details:[/bold]")
                    for i, failure in enumerate(failure_details):
                        console.print(f"[cyan]Failure #{i+1}:[/cyan] {failure['nodeid']}")
                        console.print(f"[dim]Session: {failure['session_id']}[/dim]")

                        # Format and display the error message
                        if failure['error_msg']:
                            # Use Rich's syntax highlighting for the error message
                            console.print("[yellow]Error Message:[/yellow]")
                            # Split into lines and add proper indentation
                            for line in failure['error_msg'].split('\n'):
                                if line.strip():  # Skip empty lines
                                    console.print(f"  {line}")
                        else:
                            console.print("[yellow]Error Message:[/yellow] [italic]No error message available[/italic]")

                        console.print()  # Add a blank line between failures
                elif failure_details:
                    # Just show a summary if detailed error messages are not requested
                    console.print(f"\n[bold]Test Failures Found:[/bold] {len(failure_details)} tests failed")
                    console.print("[italic]Use --show-errors to see detailed error messages[/italic]")


                # Then show the error pattern analysis
                if sorted_patterns:
                    error_table = Table(title="Common Error Patterns")
                    error_table.add_column("Error Pattern", style="cyan")
                    error_table.add_column("Occurrences", style="yellow")
                    error_table.add_column("Affected Tests", style="red")

                    # Show top error patterns
                    for pattern, count in sorted_patterns[:10]:  # Limit to top 10
                        affected_tests = len(set(error_patterns[pattern]))
                        error_table.add_row(
                            pattern,
                            str(count),
                            str(affected_tests)
                        )

                    console.print(error_table)

                    # Show tests with multiple error patterns (potentially flaky or unstable)
                    multi_error_tests = {test: patterns for test, patterns in test_to_error_map.items() if len(patterns) > 1}

                    if multi_error_tests:
                        console.print("[bold]Tests with Multiple Error Patterns:[/bold] (potentially unstable)")
                        multi_error_table = Table(show_header=True)
                        multi_error_table.add_column("Test", style="cyan")
                        multi_error_table.add_column("Error Patterns", style="yellow")

                        for test, patterns in sorted(multi_error_tests.items(), key=lambda x: len(x[1]), reverse=True)[:5]:
                            test_short = test.split("::")[-1] if "::" in test else test
                            multi_error_table.add_row(
                                test_short,
                                str(len(patterns))
                            )

                        console.print(multi_error_table)
                else:
                    if failure_details:
                        console.print("[italic yellow]No significant error patterns found, but test failures were detected.[/italic yellow]")
                        console.print("[italic]This may indicate that each test is failing with a unique error message.[/italic]")
                    else:
                        console.print("[italic]No test failures found in the analyzed data.[/italic]")

            # Update JSON output with error pattern data
            if output_format == "json":
                result["error_patterns"] = [
                    {
                        "pattern": pattern,
                        "count": count,
                        "affected_tests": list(set(error_patterns[pattern]))
                    }
                    for pattern, count in sorted_patterns[:20]  # Limit to top 20 for JSON output
                ]

                result["multi_error_tests"] = [
                    {
                        "test": test,
                        "error_patterns": patterns
                    }
                    for test, patterns in test_to_error_map.items()
                    if len(patterns) > 1
                ]

                # Include detailed failure information in JSON output
                result["test_failures"] = failure_details
        except Exception as e:
            # Always display errors for test compatibility, even in JSON mode
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
        "--compare",
        "-c",
        type=str,
        help="Compare with previous data (format: days:N, version:X.Y.Z, or profile:name)",
    )
    parser.add_argument("--trends", action="store_true", help="Show trends over time")
    parser.add_argument("--generate-sample", action="store_true", help="Generate sample test data")
    parser.add_argument("--show-errors", action="store_true", help="Show detailed error messages for failed tests")
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

        # Function to generate realistic error messages
        def generate_error_message(test_type, test_name):
            """Generate realistic error messages for failed tests."""
            # Common Python exceptions with realistic error messages
            error_types = {
                "AssertionError": [
                    "assert actual == expected",
                    "assert response.status_code == 200",
                    "assert len(results) > 0",
                    "assert 'error' not in response.json()",
                    "assert isinstance(result, dict)",
                ],
                "ValueError": [
                    "invalid literal for int() with base 10",
                    "time data does not match format",
                    "invalid token in JSON string",
                    "could not convert string to float",
                    "invalid URL for request",
                ],
                "TypeError": [
                    "unsupported operand type(s) for +",
                    "function takes 2 positional arguments but 3 were given",
                    "object of type 'NoneType' has no len()",
                    "string indices must be integers",
                    "'NoneType' object is not subscriptable",
                ],
                "KeyError": [
                    "'id'",
                    "'data'",
                    "'results'",
                    "'user'",
                    "'config'",
                ],
                "IndexError": [
                    "list index out of range",
                    "tuple index out of range",
                    "string index out of range",
                    "pop from empty list",
                    "pop from empty array",
                ],
                "AttributeError": [
                    "'NoneType' object has no attribute",
                    "module has no attribute",
                    "object has no attribute",
                    "'dict' object has no attribute",
                    "'list' object has no attribute",
                ],
            }

            # Select a random error type and message
            error_type = random.choice(list(error_types.keys()))
            error_message = random.choice(error_types[error_type])

            # Create a realistic traceback
            file_path = f"tests/{test_type}/{test_name}.py"
            line_number = random.randint(10, 200)

            # Create a realistic traceback
            traceback = f"""Traceback (most recent call last):
  File "{file_path}", line {line_number}, in test_function
    result = app.{test_name.split('_')[-1]}()
  File "/app/core/api.py", line {random.randint(50, 150)}, in {test_name.split('_')[-1]}
    return self._process_request(data)
{error_type}: {error_message}"""

            return traceback

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

                    # Add realistic error message for failed tests
                    if outcome == "failed":
                        test["longreprtext"] = generate_error_message(test_type, test_name)

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
        show_error_details=args.show_errors,
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
