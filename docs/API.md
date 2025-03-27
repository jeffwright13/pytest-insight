# pytest-insight API Reference

This document provides a comprehensive reference for the pytest-insight API, detailing the core classes, methods, and usage patterns.

## Core Components

pytest-insight is built around three primary operations:

1. **Query** - Finding and filtering test sessions
2. **Compare** - Comparing between versions/times
3. **Analyze** - Extracting insights and metrics

Each component follows a fluent interface design pattern for intuitive and chainable operations.

## Query API

The Query API allows you to search and filter test sessions and their results.

### Creating a Query

```python
from pytest_insight.query import Query

# Create a query from all available sessions
query = Query.from_storage()

# Create a query from specific sessions
query = Query(sessions=[session1, session2])
```

### Session-Level Filtering

```python
# Filter by System Under Test (SUT)
sessions = query.for_sut("api-service").execute()

# Filter by time range
sessions = query.in_last_days(7).execute()

# Filter by session with warnings
sessions = query.with_warnings().execute()

# Combine filters
sessions = query.for_sut("api-service").in_last_days(7).with_warnings().execute()
```

### Test-Level Filtering

```python
# Start test-level filtering
test_filter = query.filter_by_test()

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

### Compare API
```
from pytest_insight.compare import Compare

# Create a comparison between base and target sessions
comparison = Compare(base_sessions, target_sessions)

# Get all differences
differences = comparison.get_differences()

# Get specific types of differences
new_failures = comparison.get_new_failures()
fixed_tests = comparison.get_fixed_tests()
slower_tests = comparison.get_slower_tests(threshold=1.5)  # 50% slower
```

#### Analysis API
The Analysis API provides metrics and insights from test sessions.
```python
from pytest_insight.analysis import Analysis

# Create an analysis instance
analysis = Analysis(sessions)

# Get health report
health_report = analysis.health_report()

# Get stability report
stability_report = analysis.stability_report()

# Get performance report
performance_report = analysis.performance_report()

# Find flaky tests
flaky_tests = analysis.find_flaky_tests()
```
