"""
Quick Start Guide for pytest-insight

This playground demonstrates common use cases and best practices for using pytest-insight.
Run this file directly to see the examples in action.
"""
from datetime import datetime, timedelta

from pytest_insight.analytics import SUTAnalytics
from pytest_insight.models import TestOutcome
from pytest_insight.query.comparison import Comparison
from pytest_insight.query.query import Query

print("pytest-insight Quick Start Guide\n")

# Example 1: Basic test health analysis
query = Query()  # Uses default storage (~/.pytest_insight/practice.json)

all_sessions = query.execute()

health = (query
    .for_sut("ref-sut-openjdk11")
    .in_last_days(7)
    .execute())

print("Test Health Metrics:")
print(f"Total tests: {len(health.sessions[0].test_results)}")
print(f"Pass rate: {health.pass_rate:.1%}")  # Typically ~45%
print(f"Flaky rate: {health.flaky_rate:.1%}")  # Typically ~17%
print(f"Warning rate: {health.warning_rate:.1%}")  # Typically ~8.5%

# Example 2: Finding ````````````````flaky tests with session context
print("\nAnalyzing flaky tests with session context:")
flaky_tests = (query
    .with_reruns(True)  # Session-level filter: has reruns
    .filter_by_test()   # Start filtering by test properties
    .with_outcome(TestOutcome.PASSED)  # Test-level: eventually passed
    .apply()            # Back to session context
    .execute())

print(f"Found {flaky_tests.total_count} sessions with flaky tests")
for session in flaky_tests.sessions:
    print(f"\nSession {session.session_id}:")
    # Show ALL tests in the session for context
    print("  All tests in session:")
    for test in session.test_results:
        status = []
        if test.rerun_count > 0:
            status.append(f"FLAKY ({test.rerun_count} attempts)")
        if test.duration > 10.0:
            status.append("SLOW")
        if test.outcome != TestOutcome.PASSED:
            status.append(test.outcome.value)
        status_str = f" ({', '.join(status)})" if status else ""
        print(f"    - {test.nodeid}{status_str}")

    # Show session-level warnings
    if session.warnings:
        print("\n  Session warnings:")
        for warning in session.warnings:
            print(f"    - {warning.message}")

# Example 3: Cross-version comparison with proper session filtering
print("\nAnalyzing Python version compatibility:")
comparison = Comparison()
result = (comparison
    .between_suts("ref-sut-python39", "ref-sut-python311")
    .with_session_id_pattern("base-*", "target-*")  # Critical for accurate comparison!
    .in_last_days(7)
    .execute())

# Show non-exclusive test categories
print("\nTest Categories (NOT mutually exclusive):")
all_failures = {t.nodeid for t in result.new_failures}
all_flaky = {t.nodeid for t in result.flaky_tests}
all_warnings = {t.nodeid for t in result.tests_with_warnings}

print("\nCategory counts:")
print(f"- New failures: {len(all_failures)}")
print(f"- Flaky tests: {len(all_flaky)}")
print(f"- Tests with warnings: {len(all_warnings)}")

# Show overlapping categories
flaky_failures = all_failures & all_flaky
warning_failures = all_failures & all_warnings
flaky_warnings = all_flaky & all_warnings
all_issues = all_failures & all_flaky & all_warnings

print("\nOverlapping categories:")
print(f"- Both flaky and failing: {len(flaky_failures)}")
print(f"- Both failing with warnings: {len(warning_failures)}")
print(f"- Both flaky with warnings: {len(flaky_warnings)}")
print(f"- All three categories: {len(all_issues)}")

if all_issues:
    print("\nTests with all issues:")
    for nodeid in all_issues:
        print(f"  - {nodeid}")

# Example 4: Performance analysis with full context
print("\nAnalyzing slow tests with context:")
slow_tests = (query
    .having_warnings(True)  # Session-level: has warnings
    .filter_by_test()      # Start test filtering
    .with_duration(10.0, float("inf"))  # Test-level: >10s runtime
    .apply()               # Back to session context
    .execute())

print(f"Found {slow_tests.total_count} sessions with slow tests")
for session in slow_tests.sessions:
    print(f"\nSession {session.session_id}:")
    # Show all tests in session for context
    print("  All tests in session:")
    total_duration = 0
    for test in session.test_results:
        total_duration += test.duration
        duration_note = " (SLOW!)" if test.duration > 10.0 else ""
        print(f"    - {test.nodeid}: {test.duration:.1f}s{duration_note}")
    print(f"\n  Total session duration: {total_duration:.1f}s")

    # Show session-level warnings
    if session.warnings:
        print("\n  Session warnings:")
        for warning in session.warnings:
            print(f"    - {warning.message}")

# Example 5: Test stability analysis
print("\nAnalyzing test stability patterns:")
last_month = datetime.now() - timedelta(days=30)
stability = (query
    .date_range(last_month, datetime.now())
    .filter_by_test()      # Filter by test properties
    .with_outcome(TestOutcome.FAILED)  # Looking for failures
    .apply()               # Back to session context
    .execute())

failure_counts = {}
test_outcomes = {}  # Track all outcomes for each test
for session in stability.sessions:
    for test in session.test_results:
        if test.outcome == TestOutcome.FAILED:
            failure_counts[test.nodeid] = failure_counts.get(test.nodeid, 0) + 1

        # Track all outcomes to identify inconsistent tests
        if test.nodeid not in test_outcomes:
            test_outcomes[test.nodeid] = set()
        test_outcomes[test.nodeid].add(test.outcome)

# Show tests that failed more than 3 times
frequent_failures = {
    nodeid: count for nodeid, count in failure_counts.items()
    if count > 3
}

print(f"\nTests with frequent failures (>3 times in 30 days):")
for nodeid, count in sorted(frequent_failures.items(), key=lambda x: x[1], reverse=True):
    outcomes = test_outcomes[nodeid]
    outcome_str = ", ".join(o.value for o in outcomes)
    print(f"  - {nodeid}:")
    print(f"    - Failed {count} times")
    print(f"    - All outcomes seen: {outcome_str}")  # Shows outcome instability
