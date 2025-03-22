# %% [markdown]
# # pytest-insight Tutorial
#
# This tutorial demonstrates the key features of pytest-insight, focusing on:
# - Test health analysis with session context
# - Pattern matching using glob and regex
# - Cross-version comparison
# - Performance analysis
# - Test stability tracking
#
# Each section contains examples you can run and modify to understand how pytest-insight works.

# %% [markdown]
# ## Setup
# First, let's import the necessary modules:

# %%
from collections import Counter
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from pytest_insight.comparison import Comparison
from pytest_insight.models import TestOutcome
from pytest_insight.query import Query

# %% [markdown]
# ## 1. Test Health Analysis with Session Context
#
# Let's analyze the overall health of our test suite. Remember that pytest-insight always preserves
# session context - you get back full TestSession objects that maintain relationships between tests
# that ran together, including warnings, reruns, and other session-level metadata.

# %%
# Initialize query with default storage
query = Query()  # Uses ~/.pytest_insight/practice.json

# Get test results from the last week - returns full sessions
health = query.for_sut("my-service").in_last_days(7).execute()

# Calculate health metrics while preserving session context
total_tests = 0
outcomes = Counter()
flaky_count = 0
warning_count = 0

# Analyze each session to maintain test relationships
for session in health.sessions:
    print(f"\nAnalyzing Session: {session.session_id}")
    session_tests = 0
    session_failures = 0
    session_warnings = 0
    session_flaky = 0

    # Look at all tests in the session together
    for test in session.test_results:
        session_tests += 1
        total_tests += 1
        outcomes[test.outcome] += 1

        if hasattr(test, "rerun_count") and test.rerun_count > 0:
            session_flaky += 1
            flaky_count += 1
        if test.has_warning:
            session_warnings += 1
            warning_count += 1
        if test.outcome == TestOutcome.FAILED:
            session_failures += 1

    # Show session-level metrics
    print(f"  Tests in session: {session_tests}")
    if session_failures > 0:
        print(f"  Failed tests: {session_failures}")
    if session_flaky > 0:
        print(f"  Flaky tests: {session_flaky}")
    if session_warnings > 0:
        print(f"  Tests with warnings: {session_warnings}")

    # Show session-level warnings if any
    if session.warnings:
        print("\n  Session Warnings:")
        for warning in session.warnings:
            print(f"    - {warning.message}")

# Calculate overall rates
pass_rate = outcomes[TestOutcome.PASSED] / total_tests if total_tests > 0 else 0
flaky_rate = flaky_count / total_tests if total_tests > 0 else 0
warning_rate = warning_count / total_tests if total_tests > 0 else 0

print("\nOverall Test Health Metrics:")
print(f"Total tests: {total_tests}")
print(f"Pass rate: {pass_rate:.1%}")
print(f"Flaky rate: {flaky_rate:.1%}")
print(f"Warning rate: {warning_rate:.1%}")

# Show outcome distribution
print("\nOutcome Distribution:")
for outcome, count in outcomes.items():
    print(f"- {outcome.value}: {count} ({count/total_tests:.1%})")

# %% [markdown]
# ## 2. Pattern Matching with Session Context
#
# pytest-insight provides two types of pattern matching, and both preserve full session context:
# 1. Non-regex patterns (automatically wrapped with `*{pattern}*`)
# 2. Regex patterns (used as-is)
#
# When using patterns, you always get back full sessions containing the matching tests,
# not just the matching tests in isolation. This helps you understand test relationships
# and identify correlated failures.

# %% [markdown]
# ### 2.1 Non-regex Pattern Examples
#
# Non-regex patterns follow these rules:
# - Pattern is wrapped with wildcards: `*{pattern}*`
# - Module part has `.py` extension stripped before matching
# - Pattern is matched against each part separately
# - Test matches if ANY part matches

# %%
# Pattern matches module part (strips .py before matching)
api_matches = (
    query.filter_by_test()
    .with_pattern("api")  # Matches test_api.py::test_get (*api* matches test_api after .py strip)
    .apply()
    .execute()
)

print("\nModule pattern matches ('api'):")
for session in api_matches.sessions:
    print(f"\nSession {session.session_id}:")
    print("  Matching tests:")
    for test in session.test_results:
        print(f"    - {test.nodeid}")

# %%
# Pattern matches test name part
test_api_matches = (
    query.filter_by_test()
    .with_pattern("test_api")  # Matches test_api.py::test_get (*test_api* matches test_api after .py strip)
    .apply()  # Also matches test_foo.py::test_api_post (*test_api* matches test_api_post)
    .execute()
)

print("\nTest name pattern matches ('test_api'):")
for session in test_api_matches.sessions:
    print(f"\nSession {session.session_id}:")
    print("  Matching tests:")
    for test in session.test_results:
        print(f"    - {test.nodeid}")

# %%
# Pattern matches any part
get_matches = (
    query.filter_by_test()
    .with_pattern("get")  # Matches test_api.py::test_get, test_api.py::TestAPI::get_item
    .apply()  # *get* matches against any part
    .execute()
)

print("\nAny part pattern matches ('get'):")
for session in get_matches.sessions:
    print(f"\nSession {session.session_id}:")
    print("  Matching tests:")
    for test in session.test_results:
        print(f"    - {test.nodeid}")

# %% [markdown]
# ### 2.2 Regex Pattern Examples
#
# Regex patterns follow these rules:
# - Pattern is used as-is (no wildcards added)
# - Pattern matches against full nodeid
# - Test matches if pattern matches anywhere in nodeid

# %%
# Match specific test format
regex_matches = (
    query.filter_by_test()
    .with_pattern(r"test_\w{3}$", use_regex=True)  # Matches test_get, test_put, etc.
    .apply()  # No wildcards added
    .execute()
)

print("\nRegex pattern matches (test_\\w{3}$):")
for session in regex_matches.sessions:
    print(f"\nSession {session.session_id}:")
    print("  Matching tests:")
    for test in session.test_results:
        print(f"    - {test.nodeid}")

# %% [markdown]
# ## 3. Cross-Version Comparison with Session Context
#
# Compare test behavior across different Python versions while maintaining
# session context to understand related failures:

# %%
print("\nAnalyzing Python version compatibility:")
comparison = Comparison()
result = (
    comparison.between_suts("python39", "python311")
    .with_session_id_pattern("base-*", "target-*")  # Critical for accurate comparison
    .in_last_days(7)
    .execute()
)

print("\nChanges between versions:")
print(f"- New failures: {len(result.new_failures)}")
print(f"- Fixed failures: {len(result.fixed_failures)}")
print(f"- Flaky tests: {len(result.flaky_tests)}")

# Show related failures
if result.new_failures:
    print("\nNew failures and their session context:")
    for failure in result.new_failures:
        print(f"\nTest: {failure.nodeid}")
        # Find the session containing this failure
        for session in result.target_session.sessions:
            if any(t.nodeid == failure.nodeid for t in session.test_results):
                print("  Other tests in the same session:")
                for test in session.test_results:
                    if test.nodeid != failure.nodeid:
                        print(f"    - {test.nodeid}: {test.outcome.value}")
                break

# %% [markdown]
# ## 4. Performance Analysis with Session Context
#
# Find slow tests while preserving session context to understand performance patterns:

# %%
print("\nAnalyzing slow tests with context:")
slow_tests = (
    query.with_warning(True)  # Session-level: has warnings
    .filter_by_test()  # Start test filtering
    .with_duration_between(10.0, float("inf"))  # Test-level: >10s runtime
    .apply()  # Back to session context
    .execute()
)

print(f"\nFound {len(slow_tests)} sessions with slow tests")
for session in slow_tests.sessions:
    print(f"\nSession {session.session_id}:")
    # Show ALL tests in session for context
    print("  All tests in session:")
    total_duration = 0
    slow_tests_in_session = []

    for test in session.test_results:
        total_duration += test.duration
        if test.duration > 10.0:
            slow_tests_in_session.append(test)
        duration_note = " (SLOW!)" if test.duration > 10.0 else ""
        print(f"    - {test.nodeid}: {test.duration:.1f}s{duration_note}")

    print("\n  Session Summary:")
    print(f"    Total duration: {total_duration:.1f}s")
    print(f"    Slow tests: {len(slow_tests_in_session)} of {len(session.test_results)}")
    print(f"    Average test duration: {total_duration/len(session.test_results):.1f}s")

    # Show session-level warnings
    if session.warnings:
        print("\n  Session warnings:")
        for warning in session.warnings:
            print(f"    - {warning.message}")

# %% [markdown]
# ## 5. Test Stability Analysis with Session Context
#
# Track test stability over time to identify problematic tests and their relationships:


# %%
def query_failed_tests():
    """Query for failed tests in the last month."""
    last_month = datetime.now(ZoneInfo("UTC")) - timedelta(days=30)
    failed_tests = (
        query.date_range(last_month, datetime.now(ZoneInfo("UTC")))
        .filter_by_test()
        .with_outcome(TestOutcome.FAILED)
        .apply()
        .execute()
    )

    return failed_tests


failed_tests = query_failed_tests()

failure_counts = {}
test_outcomes = {}  # Track all outcomes for each test
session_relationships = {}  # Track which tests fail together

for session in failed_tests.sessions:
    failed_tests = set()
    for test in session.test_results:
        # Track all outcomes for each test
        if test.nodeid not in test_outcomes:
            test_outcomes[test.nodeid] = set()
        test_outcomes[test.nodeid].add(test.outcome)

        # Track failures
        if test.outcome == TestOutcome.FAILED:
            failed_tests.add(test.nodeid)
            failure_counts[test.nodeid] = failure_counts.get(test.nodeid, 0) + 1

    # Record which tests fail together
    if len(failed_tests) > 1:
        for test_id in failed_tests:
            if test_id not in session_relationships:
                session_relationships[test_id] = set()
            session_relationships[test_id].update(failed_tests - {test_id})

# Show tests that failed more than 3 times
frequent_failures = {nodeid: count for nodeid, count in failure_counts.items() if count > 3}

print("\nTests with frequent failures (>3 times in 30 days):")
for nodeid, count in sorted(frequent_failures.items(), key=lambda x: x[1], reverse=True):
    outcomes = test_outcomes[nodeid]
    outcome_str = ", ".join(o.value for o in outcomes)
    print(f"\n{nodeid}:")
    print(f"  Failed {count} times")
    print(f"  All outcomes seen: {outcome_str}")

    # Show related failures
    if nodeid in session_relationships:
        related = session_relationships[nodeid]
        print("  Often fails with:")
        for related_test in related:
            if related_test in frequent_failures:
                print(f"    - {related_test}")

# %% [markdown]
# ## Next Steps
#
# Now that you've seen how pytest-insight preserves session context, try:
# 1. Modifying the patterns to match your test naming conventions
# 2. Adjusting time ranges to analyze different periods
# 3. Combining multiple filters to find specific test patterns
# 4. Using session context to understand test relationships
#
# For more examples and detailed documentation, see:
# - [User Guide](docs/user_guide.md)
# - [API Reference](docs/api.md)
# - [Pattern Matching](docs/patterns.md)
