from pathlib import Path

from pytest_insight.models import TestOutcome
from pytest_insight.query.comparison import Comparison
from pytest_insight.query.query import Query
from pytest_insight.storage import JSONStorage

# Example: Simple query using default storage as set in constants.py
query = Query()  # Automatically uses ~/.pytest_insight/practice.json by default
print()


base_sessions = query.for_sut("ref-sut-python39").with_session_id_pattern("base-*").execute()
print(f"\nFound {base_sessions.total_count} base sessions")

# Example: Search for sessions without any reruns in the past 3 days
no_reruns = query.with_reruns(False).in_last_days(3).execute()
print(f"\nFound {no_reruns.total_count} sessions with no reruns in the last 3 days")
print(f"They were: {', '.join(s.session_id for s in no_reruns.sessions)}")

# Example 2: Simple comparison between SUTs
comparison = Comparison()  # Uses same default storage as Example 1
result = comparison.between_suts("ref-sut-python39", "ref-sut-python311").in_last_days(1).execute()

print("\nComparison Results:")
print(f"Base SUT: {result.base_session.sut_name}")
print(f"Target SUT: {result.target_session.sut_name}")
print(f"- New failures: {len(result.new_failures)}")
print(f"- Fixed tests: {len(result.fixed_tests)}")
print(f"- Flaky tests: {len(result.flaky_tests)}")

# Example 3: Find flaky tests that are also new failures
flaky_failures = {t.nodeid for t in result.flaky_tests} & {t.nodeid for t in result.new_failures}
if flaky_failures:
    print("\nTests that are both flaky and new failures:")
    for nodeid in flaky_failures:
        print(f"  - {nodeid}")
        old_outcome, new_outcome = result.outcome_changes[nodeid]
        print(f"    Changed from {old_outcome.value} to {new_outcome.value}")

# Example 4: Using custom storage location (optional)
storage = JSONStorage(Path.home() / ".pytest_insight" / "custom.json")
sessions = storage.load_sessions()

query = Query(sessions)  # Explicitly provide sessions
slow_tests = query.filter_tests().with_duration(10.0, float("inf")).apply().execute()
print(f"\nFound {slow_tests.total_count} sessions with slow tests")

# Example 5: Direct session comparison (optional)
if base_sessions.sessions:
    # Get most recent base and target sessions
    base = max(base_sessions.sessions, key=lambda s: s.session_start_time)
    target = max(result.target_session.test_results, key=lambda s: s.session_start_time)

    comparison = Comparison()
    result = comparison.execute([base, target])  # Direct comparison
    print("\nDirect Comparison Results:")
    print(f"- New failures: {len(result.new_failures)}")
    print(f"- Fixed tests: {len(result.fixed_tests)}")
    print(f"- Flaky tests: {len(result.flaky_tests)}")
    print(f"- Missing tests: {len(result.missing_tests)}")
    print(f"- New tests: {len(result.new_tests)}")

# Example 6: Find failed tests in the last day
query = Query()  # Uses default storage
recent_failures = query.in_last_days(1).with_outcome(TestOutcome.FAILED).execute()
print(f"\nFound {recent_failures.total_count} sessions with failures in the last day")
