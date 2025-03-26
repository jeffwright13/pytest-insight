#!/usr/bin/env python3
"""
Pytest-Insight Analysis Demo

This script demonstrates how to:
1. Use the Analysis class to extract insights from test data
2. Apply filtering using the Query class
3. Visualize key metrics and trends

The script follows the fluent interface pattern established in the pytest-insight API.
"""

import json
from collections import Counter
from pathlib import Path

from pytest_insight.analysis import Analysis
from pytest_insight.models import TestOutcome, TestSession


def analyze_test_data(data_path=None):
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
        else:
            print("Error: Data does not contain a 'sessions' array")
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
    if "stability" in health_report["health_score"]:
        print(f"Stability Score: {health_report['health_score']['stability']:.2f}/100")
    if "performance" in health_report["health_score"]:
        print(f"Performance Score: {health_report['health_score']['performance']:.2f}/100")
    if "warning_score" in health_report["health_score"]:
        print(f"Warning Score: {health_report['health_score']['warning_score']:.2f}/100")

    # Print recommendations if they exist
    if "recommendations" in health_report:
        print("\nRecommendations:")
        for rec in health_report["recommendations"]:
            print(f"- [{rec['priority']}] {rec['message']}")

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
        percentage = (count / total_tests) * 100
        print(f"{outcome}: {count} ({percentage:.1f}%)")

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
                change = ((last_duration - first_duration) / first_duration) * 100
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

            if total_tests > 0:
                failure_rate = failed_tests / total_tests
                daily_failure_rates.append((day, failure_rate))

        if daily_failure_rates:
            print(f"Failure rate trend over {len(daily_failure_rates)} days:")
            for day, rate in daily_failure_rates:
                print(f"- {day}: {rate*100:.1f}%")

            # Calculate trend direction
            if len(daily_failure_rates) >= 2:
                first_rate = daily_failure_rates[0][1]
                last_rate = daily_failure_rates[-1][1]
                if first_rate > 0:
                    change = ((last_rate - first_rate) / first_rate) * 100
                    print(f"\nOverall trend: {change:.1f}% {'increase' if change > 0 else 'decrease'} in failure rate")
                else:
                    change = last_rate * 100
                    if change > 0:
                        print(f"\nOverall trend: Increased from 0% to {change:.1f}%")
                    else:
                        print("\nOverall trend: Stable at 0% failure rate")

    # SECTION 4: SUT COMPARISON
    print("\n" + "=" * 50)
    print("SECTION 4: SUT COMPARISON")
    print("=" * 50)

    # Get available SUTs for filtering
    suts = set(session.sut_name for session in sessions)

    print(f"\nAvailable SUTs: {', '.join(suts)}")

    # Demonstrate fluent interface with query filtering
    if suts:
        # Pick the first SUT for demonstration
        example_sut = next(iter(suts))

        print(f"\n4.1 Filtered Analysis ({example_sut} Only)")
        print("-------------------------------------")
        sut_sessions = [s for s in sessions if s.sut_name == example_sut]
        sut_analysis = Analysis(sessions=sut_sessions)
        sut_health = sut_analysis.health_report()
        print(f"{example_sut} Health Score: {sut_health['health_score']['overall_score']:.2f}/100")

        # Test-level filtering
        print("\n4.2 Test-Level Filtering (Failed Tests Only)")
        print("----------------------------------------")
        failed_sessions = []
        for session in sessions:
            has_failures = any(test.outcome == TestOutcome.FAILED for test in session.test_results)
            if has_failures:
                failed_sessions.append(session)

        Analysis(sessions=failed_sessions)
        print(f"Sessions with failures: {len(failed_sessions)}")

        # Compare health if we have multiple SUTs
        if len(suts) >= 2:
            sut_list = list(suts)
            print(f"\n4.3 Health Comparison ({sut_list[0]} vs {sut_list[1]})")
            print("-------------------------------------")
            sut1_sessions = [s for s in sessions if s.sut_name == sut_list[0]]
            sut2_sessions = [s for s in sessions if s.sut_name == sut_list[1]]

            if sut1_sessions and sut2_sessions:
                comparison = analysis.compare_health(base_sessions=sut1_sessions, target_sessions=sut2_sessions)
                print(f"{sut_list[0]} Health: {comparison['base_health']['health_score']['overall_score']:.2f}/100")
                print(f"{sut_list[1]} Health: {comparison['target_health']['health_score']['overall_score']:.2f}/100")
                print(f"Health Difference: {comparison['health_difference']:.2f}")
                print(f"Improved: {comparison['improved']}")

                # Compare test counts
                sut1_test_count = sum(len(s.test_results) for s in sut1_sessions)
                sut2_test_count = sum(len(s.test_results) for s in sut2_sessions)
                print("\nTest Count Comparison:")
                print(f"- {sut_list[0]}: {sut1_test_count} tests")
                print(f"- {sut_list[1]}: {sut2_test_count} tests")

                # Compare failure rates
                sut1_failures = sum(1 for s in sut1_sessions for t in s.test_results if t.outcome == TestOutcome.FAILED)
                sut2_failures = sum(1 for s in sut2_sessions for t in s.test_results if t.outcome == TestOutcome.FAILED)

                if sut1_test_count > 0 and sut2_test_count > 0:
                    sut1_failure_rate = sut1_failures / sut1_test_count
                    sut2_failure_rate = sut2_failures / sut2_test_count
                    print("\nFailure Rate Comparison:")
                    print(f"- {sut_list[0]}: {sut1_failure_rate*100:.2f}%")
                    print(f"- {sut_list[1]}: {sut2_failure_rate*100:.2f}%")
            else:
                print("Not enough data for comparison")

    # SECTION 5: TIME-BASED ANALYSIS
    print("\n" + "=" * 50)
    print("SECTION 5: TIME-BASED ANALYSIS")
    print("=" * 50)

    # Demonstrate automatic splitting for comparison
    if len(sessions) >= 2:
        print("\n5.1 Automatic Time-Based Comparison")
        print("--------------------------------")
        try:
            # Sort sessions by start time
            sorted_sessions = sorted(sessions, key=lambda s: s.session_start_time)
            # Split into two halves
            midpoint = len(sorted_sessions) // 2
            early_sessions = sorted_sessions[:midpoint]
            late_sessions = sorted_sessions[midpoint:]

            # Get date ranges for each period
            early_start = min(s.session_start_time for s in early_sessions).date()
            early_end = max(s.session_start_time for s in early_sessions).date()
            late_start = min(s.session_start_time for s in late_sessions).date()
            late_end = max(s.session_start_time for s in late_sessions).date()

            print(f"Earlier Period: {early_start} to {early_end}")
            print(f"Later Period: {late_start} to {late_end}")

            auto_comparison = analysis.compare_health(base_sessions=early_sessions, target_sessions=late_sessions)
            print(f"Earlier Period Health: {auto_comparison['base_health']['health_score']['overall_score']:.2f}/100")
            print(f"Later Period Health: {auto_comparison['target_health']['health_score']['overall_score']:.2f}/100")
            print(f"Health Trend: {auto_comparison['health_difference']:.2f}")
            print(f"Improving: {auto_comparison['improved']}")

            # Compare test counts and durations
            early_test_count = sum(len(s.test_results) for s in early_sessions)
            late_test_count = sum(len(s.test_results) for s in late_sessions)

            early_avg_duration = sum(s.session_duration for s in early_sessions) / len(early_sessions)
            late_avg_duration = sum(s.session_duration for s in late_sessions) / len(late_sessions)

            print("\nTest Count Comparison:")
            print(f"- Earlier Period: {early_test_count} tests")
            print(f"- Later Period: {late_test_count} tests")

            print("\nAverage Session Duration Comparison:")
            print(f"- Earlier Period: {early_avg_duration:.2f}s")
            print(f"- Later Period: {late_avg_duration:.2f}s")

            duration_change = ((late_avg_duration - early_avg_duration) / early_avg_duration) * 100
            print(f"Duration Change: {duration_change:.1f}% {'increase' if duration_change > 0 else 'decrease'}")

        except Exception as e:
            print(f"Could not perform automatic comparison: {e}")

    # SECTION 6: TEST PATTERN ANALYSIS
    print("\n" + "=" * 50)
    print("SECTION 6: TEST PATTERN ANALYSIS")
    print("=" * 50)

    # Analyze test patterns
    print("\n6.1 Test Module Distribution")
    print("-------------------------")

    # Extract module names from nodeids
    modules = Counter()
    for session in sessions:
        for test in session.test_results:
            # Extract module from nodeid (format: path/to/module.py::test_name)
            parts = test.nodeid.split("::")
            if len(parts) > 0:
                module = parts[0]
                modules[module] += 1

    if modules:
        print("Top 5 modules by test count:")
        for module, count in modules.most_common(5):
            print(f"- {module}: {count} tests")

    # Analyze test name patterns
    print("\n6.2 Test Name Patterns")
    print("-------------------")

    # Extract test names from nodeids
    test_names = Counter()
    test_prefixes = Counter()

    for session in sessions:
        for test in session.test_results:
            # Extract test name from nodeid (format: path/to/module.py::test_name)
            parts = test.nodeid.split("::")
            if len(parts) > 1:
                test_name = parts[1]
                test_names[test_name] += 1

                # Extract prefix (e.g., "test_create_" from "test_create_user")
                words = test_name.split("_")
                if len(words) > 2:
                    prefix = "_".join(words[:2]) + "_"
                    test_prefixes[prefix] += 1

    if test_prefixes:
        print("Common test name patterns:")
        for prefix, count in test_prefixes.most_common(5):
            print(f"- {prefix}*: {count} tests")


def main():
    """Main function to run the analysis demo."""
    # Use the existing practice data
    data_path = Path.home() / ".pytest_insight" / "practice.json"

    if not data_path.exists():
        print(f"Error: Practice data file not found at {data_path}")
        print("Please generate data first with: insight-gen --days 14")
        return

    # Analyze the data
    analyze_test_data(data_path)

    print("\nAnalysis complete! You can now explore more advanced features of the Analysis class.")
    print("For example, try filtering by specific test patterns or comparing different time periods.")


if __name__ == "__main__":
    main()
