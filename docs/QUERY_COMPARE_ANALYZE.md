# Query, Compare, Analyze: The pytest-insight Workflow

This document explains the core workflow of pytest-insight, built around three fundamental operations: Query, Compare, and Analyze.

## The Three Core Operations

pytest-insight is designed around a simple yet powerful workflow:

1. **Query** - Find and filter relevant test sessions
2. **Compare** - Identify differences between test runs
3. **Analyze** - Extract insights and metrics from test data

Each operation builds on the previous one, allowing you to progressively refine your understanding of test results.

## Query: Finding the Right Data

The Query operation is your starting point for working with test data. It allows you to find and filter test sessions based on various criteria.

### Two-Level Filtering Design

The Query API uses a two-level filtering approach:

1. **Session-Level Filtering**: Filter entire test sessions based on properties like SUT name, time range, or presence of warnings.
2. **Test-Level Filtering**: Filter by individual test properties while preserving the session context.

### Key Concept: Preserving Session Context

An important aspect of the Query API is that both levels of filtering return complete `TestSession` objects, not individual test results. This preserves the valuable session context, including:

- Warnings that occurred during the session
- Rerun patterns for flaky tests
- Relationships between tests
- Environmental factors

### Example Workflow

```python
from pytest_insight.core.core_api import InsightAPI, query

# Method 1: Using the InsightAPI class (recommended)
api = InsightAPI(profile_name="my_profile")

# Session-level filtering
sessions = api.query().with_sut("api-service").in_last_days(7).execute()

# Test-level filtering (still returns sessions)
sessions = api.query().filter_by_test().with_pattern("test_api*").with_outcome("failed").apply().execute()

# Method 2: Using the standalone query function
# Create a query using the specified profile
q = query(profile_name="my_profile")

# Session-level filtering
sessions = q.with_sut("api-service").in_last_days(7).execute()
```

## Compare: Understanding Differences

The Compare operation helps you identify differences between test runs, making it easy to spot regressions, improvements, or changes in test behavior.

```python
from pytest_insight.core.core_api import InsightAPI

# Initialize API with a specific profile
api = InsightAPI(profile_name="my_profile")

# Compare test results between two SUTs
comparison = api.compare().between_suts("sut-v1", "sut-v2")

# Get the comparison results
results = comparison.get_results()

# Access specific comparison metrics
new_failures = results.new_failures
fixed_tests = results.fixed_tests
```

## Analyze: Extracting Insights

The Analyze operation helps you extract meaningful insights from your test data, such as identifying flaky tests, performance trends, and patterns in test failures.

```python
from pytest_insight.core.core_api import InsightAPI

# Initialize API with a specific profile
api = InsightAPI(profile_name="my_profile")

# Create an analysis instance
analysis = api.analyze()

# Get flaky tests
flaky_tests = analysis.identify_flaky_tests()

# Get performance metrics
slowest_tests = analysis.get_slowest_tests(limit=10)

# Get consistently failing tests
failing_tests = analysis.identify_consistently_failing_tests()
```

## Profile-Based Approach

As of the latest version, pytest-insight uses a profile-based approach for all operations. This means:

1. You specify a profile name instead of storage details
2. All operations (Query, Compare, Analyze) use the specified profile
3. Profiles can be managed via the storage API
4. Environment variables can override the active profile

This simplifies usage, especially in CI/CD environments where you can set the `PYTEST_INSIGHT_PROFILE` environment variable to control which profile is used.
