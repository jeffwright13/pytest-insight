# pytest-insight API Reference

This document provides a comprehensive reference for the pytest-insight API, detailing the core classes, methods, and usage patterns.

## API Structure

pytest-insight provides two distinct API interfaces:

1. **Core API** - A programmatic interface following a fluent design pattern for Python code
2. **Web API** - A FastAPI/uvicorn HTTP interface for remote access and integration

## Core API

The Core API is built around three primary operations:

1. **Query** - Finding and filtering test sessions
2. **Compare** - Comparing between versions/times
3. **Analyze** - Extracting insights and metrics

Each component follows a fluent interface design pattern for intuitive and chainable operations.

### Using the Core API

The recommended way to access the Core API is through the `core_api` module:

```python
from pytest_insight.core_api import query, compare, analyze, get_insights, InsightAPI

# Direct access to individual components
results = query().for_sut("my-service").in_last_days(7).execute()
diff = compare().between_suts("v1", "v2").execute()
health = analyze().health_report()
insights = get_insights().summary_report()

# Using the unified InsightAPI
api = InsightAPI()
results = api.query().for_sut("my-service").execute()

# With a specific profile
api_with_profile = InsightAPI("my_profile")
# or
api_with_profile = api.with_profile("my_profile")
results = api_with_profile.query().for_sut("my-service").execute()
```

## Query API

The Query API allows you to search and filter test sessions and their results.

### Creating a Query

```python
from pytest_insight.core_api import query

# Create a query from all available sessions
q = query()

# Create a query from specific sessions
query = query(sessions=[session1, session2])
```

### Session-Level Filtering

```python
# Filter by System Under Test (SUT)
sessions = q.for_sut("api-service").execute()

# Filter by time range
sessions = q.in_last_days(7).execute()

# Filter by session with warnings
sessions = q.with_warnings().execute()

# Combine filters
sessions = q.for_sut("api-service").in_last_days(7).with_warnings().execute()
```

### Test-Level Filtering

```python
# Start test-level filtering
test_filter = q.filter_by_test()

# Filter by test pattern
test_filter = test_filter.with_pattern("test_api*")

# Filter by test outcome
test_filter = test_filter.with_outcome(TestOutcome.FAILED)

# Filter by test duration
test_filter = test_filter.with_duration(10.0, float("inf"))

# Apply filters and return to session context
sessions = test_filter.apply().execute()
```

#### Important Note on Test-Level Filtering
The filter_by_test() method doesn't return individual tests but rather filters sessions containing matching tests. This preserves the valuable session context including warnings, reruns, and test relationships.

## Compare API
```python
from pytest_insight.core_api import compare

# Create a comparison between base and target sessions
comparison = compare().between_suts("v1", "v2")

# Get all differences
differences = comparison.get_differences()

# Get specific types of differences
new_failures = comparison.get_new_failures()
fixed_tests = comparison.get_fixed_tests()
slower_tests = comparison.get_slower_tests(threshold=1.5)  # 50% slower
```

## Analysis API
The Analysis API provides metrics and insights from test sessions.
```python
from pytest_insight.core_api import analyze

# Create an analysis instance
analysis = analyze()

# Get health report
health_report = analysis.health_report()

# Get stability report
stability_report = analysis.stability_report()

# Get performance report
performance_report = analysis.performance_report()

# Find flaky tests
flaky_tests = analysis.find_flaky_tests()
