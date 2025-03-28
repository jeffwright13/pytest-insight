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
from collections import Counter
from pathlib import Path

from pytest_insight.analysis import Analysis
from pytest_insight.models import TestOutcome, TestSession


def analyze_test_data(data_path=None, sut_filter=None, days=None):
    """Analyze test data using the Analysis class."""
    print("\n=== Analyzing Test Data ===")

    # Default path if none provided
    if data_path is None:
        data_path = Path.home() / ".pytest_insight" / "practice.json"

    print(f"Using test data from: {data_path}")

    # Load the JSON data directly to extract the sessions
    try:
        with open(data_path, "r") as f:
            data = json.load(f)

        # Check if the data has a 'sessions' key
        if "sessions" in data and isinstance(data["sessions"], list):
            sessions = [TestSession.from_dict(session) for session in data["sessions"]]
            print(f"Successfully loaded {len(sessions)} test sessions")

            # Apply SUT filter if specified
            if sut_filter:
                sessions = [s for s in sessions if s.sut_name == sut_filter]
                print(f"Filtered to {len(sessions)} sessions for SUT: {sut_filter}")

            # Apply days filter if specified
            if days:
                from datetime import datetime, timedelta

                cutoff = datetime.now() - timedelta(days=days)
                sessions = [s for s in sessions if s.session_start_time >= cutoff]
                print(f"Filtered to {len(sessions)} sessions from the last {days} days")

            if not sessions:
                print("No sessions match the specified filters.")
                return
        else:
            print("Error: Data does not contain a 'sessions' array")
            print("\nTry generating test data with: insight-gen --days 14")
            return
    except FileNotFoundError:
        print(f"Error: Data file not found at {data_path}")
        print("\nTry generating test data with: insight-gen --days 14")
        return
    except json.JSONDecodeError:
        print(f"Error: The file at {data_path} is not valid JSON")
        return
    except Exception as e:
        print(f"Error loading data: {e}")
        return

    # Create an Analysis instance with the loaded sessions
    analysis = Analysis(sessions=sessions)

    # SECTION 1: BASIC HEALTH METRICS
    print("\n" + "=" * 50)
    print("SECTION 1: BASIC HEALTH METRICS")
    print("=" * 50)

    # Generate health report
    print("\n1.1 Overall Test Health Report")
    print("--------------------------")
    health_report = analysis.health_report()

    # Print overall health score
    print(f"Overall Health Score: {health_report['health_score']['overall_score']:.2f}/100")

    # Print component scores if they exist
    if "stability_score" in health_report["health_score"]:
        print(f"Stability Score: {health_report['health_score']['stability_score']:.2f}/100")
    if "performance_score" in health_report["health_score"]:
        print(f"Performance Score: {health_report['health_score']['performance_score']:.2f}/100")
    if "warning_score" in health_report["health_score"]:
        print(f"Warning Score: {health_report['health_score']['warning_score']:.2f}/100")

    # Print recommendations if they exist
    if "recommendations" in health_report:
        print("\nRecommendations:")
        for rec in health_report["recommendations"]:
            print(f"- {rec}")

    # Stability report
    print("\n1.2 Stability Report")
    print("----------------")
    stability_report = analysis.stability_report()
    if "failure_rate" in stability_report:
        print(f"Failure Rate: {stability_report['failure_rate'] * 100:.2f}%")

    # Performance report
    print("\n1.3 Performance Report")
    print("------------------")
    performance_report = analysis.performance_report()
    if "session_metrics" in performance_report:
        metrics = performance_report["session_metrics"]
        if "avg_duration" in metrics:
            print(f"Average Session Duration: {metrics['avg_duration']:.2f}s")
        if "avg_test_duration" in metrics:
            print(f"Average Test Duration: {metrics['avg_test_duration']:.2f}s")

    # SECTION 2: DETAILED TEST ANALYSIS
    print("\n" + "=" * 50)
    print("SECTION 2: DETAILED TEST ANALYSIS")
    print("=" * 50)

    # Analyze test outcomes
    print("\n2.1 Test Outcome Distribution")
    print("--------------------------")
    outcome_counts = Counter()
    total_tests = 0

    for session in sessions:
        for test in session.test_results:
            outcome_counts[test.outcome] += 1
            total_tests += 1

    print(f"Total Tests: {total_tests}")
    for outcome, count in outcome_counts.most_common():
        percentage = (count / total_tests) * 100 if total_tests else 0
        outcome_str = outcome.to_str() if hasattr(outcome, "to_str") else str(outcome)
        print(f"{outcome_str}: {count} ({percentage:.1f}%)")

    # Analyze flaky tests
    print("\n2.2 Flaky Test Detection")
    print("---------------------")
    flaky_tests = {}

    for session in sessions:
        if hasattr(session, "rerun_test_groups") and session.rerun_test_groups:
            for rerun_group in session.rerun_test_groups:
                nodeid = rerun_group.nodeid
                if nodeid not in flaky_tests:
                    flaky_tests[nodeid] = {"reruns": 0, "sessions": set()}
                flaky_tests[nodeid]["reruns"] += len(rerun_group.tests)
                flaky_tests[nodeid]["sessions"].add(session.session_id)

    if flaky_tests:
        print(f"Found {len(flaky_tests)} flaky tests:")
        for nodeid, data in sorted(flaky_tests.items(), key=lambda x: x[1]["reruns"], reverse=True)[:5]:
            print(f"- {nodeid}: {data['reruns']} reruns across {len(data['sessions'])} sessions")
    else:
        print("No flaky tests detected")

    # Analyze test durations
    print("\n2.3 Slowest Tests")
    print("--------------")
    test_durations = []

    for session in sessions:
        for test in session.test_results:
            test_durations.append((test.nodeid, test.duration))

    if test_durations:
        sorted_durations = sorted(test_durations, key=lambda x: x[1], reverse=True)
        print("Top 5 slowest tests:")
        for nodeid, duration in sorted_durations[:5]:
            print(f"- {nodeid}: {duration:.2f}s")
    else:
        print("No test duration data available")

    # SECTION 3: TREND ANALYSIS
    print("\n" + "=" * 50)
    print("SECTION 3: TREND ANALYSIS")
    print("=" * 50)

    # Sort sessions by start time for trend analysis
    sorted_sessions = sorted(sessions, key=lambda s: s.session_start_time)

    if len(sorted_sessions) >= 2:
        # Analyze duration trends
        print("\n3.1 Duration Trends")
        print("----------------")

        # Group sessions by day
        sessions_by_day = {}
        for session in sorted_sessions:
            day = session.session_start_time.date()
            if day not in sessions_by_day:
                sessions_by_day[day] = []
            sessions_by_day[day].append(session)

        # Calculate average duration per day
        daily_durations = []
        for day, day_sessions in sorted(sessions_by_day.items()):
            avg_duration = sum(s.session_duration for s in day_sessions) / len(day_sessions)
            daily_durations.append((day, avg_duration))

        if daily_durations:
            print(f"Session duration trend over {len(daily_durations)} days:")
            for day, duration in daily_durations:
                print(f"- {day}: {duration:.2f}s")

            # Calculate trend direction
            if len(daily_durations) >= 2:
                first_duration = daily_durations[0][1]
                last_duration = daily_durations[-1][1]
                change = ((last_duration - first_duration) / first_duration) * 100 if first_duration else 0
                print(f"\nOverall trend: {change:.1f}% {'increase' if change > 0 else 'decrease'} in session duration")

        # Analyze failure trends
        print("\n3.2 Failure Trends")
        print("---------------")

        # Calculate failure rate per day
        daily_failure_rates = []
        for day, day_sessions in sorted(sessions_by_day.items()):
            total_tests = 0
            failed_tests = 0
            for session in day_sessions:
                for test in session.test_results:
                    total_tests += 1
                    if test.outcome == TestOutcome.FAILED:
                        failed_tests += 1
            failure_rate = (failed_tests / total_tests) * 100 if total_tests else 0
            daily_failure_rates.append((day, failure_rate))

        if daily_failure_rates:
            print(f"Failure rate trend over {len(daily_failure_rates)} days:")
            for day, rate in daily_failure_rates:
                print(f"- {day}: {rate:.2f}%")

            # Calculate trend direction
            if len(daily_failure_rates) >= 2:
                first_rate = daily_failure_rates[0][1]
                last_rate = daily_failure_rates[-1][1]
                change = last_rate - first_rate
                print(f"\nOverall trend: {abs(change):.1f}% {'increase' if change > 0 else 'decrease'} in failure rate")

    # SECTION 4: TEST PATTERNS
    print("\n" + "=" * 50)
    print("SECTION 4: TEST PATTERNS")
    print("=" * 50)

    # Analyze test patterns
    print("\n4.1 Test Patterns")
    print("-------------")

    # Extract test prefixes
    test_prefixes = Counter()
    for session in sessions:
        for test in session.test_results:
            # Get the prefix (e.g., "test_api" from "test_api_get_user")
            parts = test.nodeid.split("::")
            if len(parts) >= 2:
                # Get the function name
                func_name = parts[-1]
                # Extract prefix (everything up to the first underscore)
                if "_" in func_name:
                    prefix = func_name.split("_")[0]
                    test_prefixes[prefix] += 1

    if test_prefixes:
        print("Most common test prefixes:")
        for prefix, count in test_prefixes.most_common(5):
            print(f"- {prefix}*: {count} tests")


def main():
    """Main function to run the analysis CLI."""
    parser = argparse.ArgumentParser(description="Analyze pytest-insight test data")
    parser.add_argument(
        "--path",
        "-p",
        type=str,
        help="Path to the JSON data file (default: ~/.pytest_insight/practice.json)",
    )
    parser.add_argument("--sut", "-s", type=str, help="Filter by System Under Test name")
    parser.add_argument("--days", "-d", type=int, help="Filter to sessions from the last N days")
    parser.add_argument("--version", "-v", action="store_true", help="Show version information")

    args = parser.parse_args()

    if args.version:
        from importlib.metadata import version

        try:
            ver = version("pytest-insight")
            print(f"pytest-insight version: {ver}")
        except:
            print("pytest-insight version: unknown")
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
                    print(f"No practice.json found, using {data_path.name} instead")

    if data_path is None or not data_path.exists():
        print("Error: No test data found.")
        print("\nTo generate test data, run:")
        print("  insight-gen --days 14")
        print("\nOr specify a custom path:")
        print("  insights --path /path/to/your/data.json")
        return

    # Analyze the data
    analyze_test_data(data_path, args.sut, args.days)

    print("\nAnalysis complete! You can now explore more advanced features of the Analysis class.")
    print("For example, try filtering by specific test patterns or comparing different time periods.")


if __name__ == "__main__":
    main()
