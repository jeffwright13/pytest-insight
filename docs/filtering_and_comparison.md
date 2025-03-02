# Filtering and Comparing Test Sessions in pytest-insight

This guide explains how to use pytest-insight's powerful filtering and comparison capabilities to analyze your test results effectively.

## Table of Contents
- [Filtering Test Sessions](#filtering-test-sessions)
  - [Basic Filtering](#basic-filtering)
  - [Advanced Filtering](#advanced-filtering)
  - [Custom Predicates](#custom-predicates)
- [Comparing Test Sessions](#comparing-test-sessions)
  - [Available Dimensions](#available-dimensions)
  - [Using the DimensionalComparator](#using-the-dimensional-comparator)
- [Examples](#examples)
  - [Filtering Examples](#filtering-examples)
  - [Comparison Examples](#comparison-examples)
  - [Analyzing Test Stability Trends](#analyzing-test-stability-trends)

## Filtering Test Sessions

### Basic Filtering

pytest-insight provides a flexible filtering system through the `DimensionFilter` class. You can filter test sessions based on:

1. Pattern matching on test nodeids
2. Session tags
3. Custom predicates

Basic filter example:
```python
from pytest_insight.filterable import DimensionFilter
from pytest_insight.dimensions import OutcomeDimension

# Create a filter for tests in the "auth" module
filter = DimensionFilter(pattern="tests/auth/*")

# Create a dimension with the filter
dimension = OutcomeDimension(filters=[filter])

# Group sessions - only includes sessions with tests matching the pattern
groups = dimension.group_sessions(sessions)
```

### Advanced Filtering

You can combine multiple filters and filter types:

```python
# Filter by both pattern and tags
filter = DimensionFilter(
    pattern="tests/api/*",
    tags={"environment": "prod", "feature": "login"}
)

# Multiple filters are applied with AND logic
filters = [
    DimensionFilter(pattern="tests/api/*"),
    DimensionFilter(tags={"environment": "prod"}),
]
dimension = OutcomeDimension(filters=filters)
```

### Custom Predicates

For more complex filtering needs, you can use custom predicates:

```python
# Filter sessions with long-running tests
def has_slow_tests(session):
    return any(result.duration > 5.0 for result in session.test_results)

filter = DimensionFilter(predicate=has_slow_tests)
dimension = DurationDimension(filters=[filter])
```

## Comparing Test Sessions

The `DimensionalComparator` allows you to compare test sessions across different dimensions like outcome, duration, or module.

### Available Dimensions

1. **OutcomeDimension**: Groups tests by their outcome (PASSED, FAILED, etc.)
```python
from pytest_insight.dimensions import OutcomeDimension

dimension = OutcomeDimension()
groups = dimension.group_sessions(sessions)
# Returns: {"PASSED": [...], "FAILED": [...], ...}
```

2. **DurationDimension**: Groups tests by duration ranges
```python
from pytest_insight.dimensions import DurationDimension

# Custom duration ranges
ranges = [
    (1.0, "FAST"),    # < 1s
    (5.0, "MEDIUM"),  # 1-5s
    (float("inf"), "SLOW")  # > 5s
]
dimension = DurationDimension(ranges=ranges)
```

3. **ModuleDimension**: Groups tests by module
```python
from pytest_insight.dimensions import ModuleDimension

dimension = ModuleDimension()
# Groups by test module path
```

4. **SUTDimension**: Groups tests by System Under Test
```python
from pytest_insight.dimensions import SUTDimension

dimension = SUTDimension()
# Groups by SUT name
```

### Using the DimensionalComparator

The `DimensionalComparator` helps analyze differences between groups:

```python
from pytest_insight.dimensional_comparator import DimensionalComparator

# Compare test outcomes between prod and staging
dimension = OutcomeDimension(filters=[
    DimensionFilter(tags={"environment": "prod"}),
    DimensionFilter(tags={"environment": "staging"})
])
comparator = DimensionalComparator(dimension)
results = comparator.compare(sessions, "PASSED", "FAILED")

# Results include:
# - Total tests in each group
# - New and removed tests
# - Status changes between groups
```

## Examples

### Filtering Examples

1. **Find Flaky Tests**:
```python
# Find tests that sometimes pass and sometimes fail
def is_flaky(session):
    outcomes = {r.outcome for r in session.test_results}
    return TestOutcome.PASSED in outcomes and TestOutcome.FAILED in outcomes

filter = DimensionFilter(predicate=is_flaky)
dimension = OutcomeDimension(filters=[filter])
flaky_groups = dimension.group_sessions(sessions)
```

2. **Analyze Production Tests**:
```python
# Group production tests by module
filters = [
    DimensionFilter(tags={"environment": "prod"}),
    DimensionFilter(pattern="tests/api/*")  # Only API tests
]
dimension = ModuleDimension(filters=filters)
prod_groups = dimension.group_sessions(sessions)
```

### Comparison Examples

1. **Compare Test Performance**:
```python
# Compare test durations between two SUTs
dimension = DurationDimension()
comparator = DimensionalComparator(dimension)
results = comparator.compare(sessions, "FAST", "SLOW")

print(f"Fast tests: {results['base']['total_tests']}")
print(f"Slow tests: {results['target']['total_tests']}")
print(f"New slow tests: {results['differences']['new_tests']}")
```

2. **Compare Environment Stability**:
```python
# Compare test outcomes between staging and prod
staging_filter = DimensionFilter(tags={"environment": "staging"})
prod_filter = DimensionFilter(tags={"environment": "prod"})

dimension = OutcomeDimension()
comparator = DimensionalComparator(dimension)

staging_sessions = [s for s in sessions if staging_filter.matches(s)]
prod_sessions = [s for s in sessions if prod_filter.matches(s)]

results = comparator.compare(
    staging_sessions + prod_sessions,
    "PASSED",
    "FAILED"
)

# Analyze differences
for change in results["differences"]["status_changes"]:
    print(f"Test {change['nodeid']} changed from "
          f"{change['base_status']} to {change['target_status']}")
```

### Analyzing Test Stability Trends

1. **Detect Newly Unstable Tests**:
```python
from pytest_insight.dimensions import OutcomeDimension
from pytest_insight.dimensional_comparator import DimensionalComparator
from datetime import datetime, timedelta

def find_newly_unstable_tests(all_sessions, lookback_days=30, failure_threshold=0.2):
    """Find previously stable tests that are now failing."""
    now = datetime.now()
    cutoff = now - timedelta(days=lookback_days)
    
    # Split sessions into past and recent
    past_sessions = [
        s for s in all_sessions 
        if cutoff <= s.session_start_time <= (now - timedelta(days=7))
    ]
    recent_sessions = [
        s for s in all_sessions 
        if s.session_start_time > (now - timedelta(days=7))
    ]
    
    # Helper to calculate failure rate
    def get_failure_rate(sessions):
        test_results = {}
        for session in sessions:
            for result in session.test_results:
                if result.nodeid not in test_results:
                    test_results[result.nodeid] = {"total": 0, "failed": 0}
                test_results[result.nodeid]["total"] += 1
                if result.outcome == TestOutcome.FAILED:
                    test_results[result.nodeid]["failed"] += 1
        
        return {
            nodeid: stats["failed"] / stats["total"]
            for nodeid, stats in test_results.items()
            if stats["total"] >= 5  # Require minimum runs
        }
    
    past_failure_rates = get_failure_rate(past_sessions)
    recent_failure_rates = get_failure_rate(recent_sessions)
    
    # Find tests with significant stability degradation
    degraded_tests = []
    for nodeid, recent_rate in recent_failure_rates.items():
        past_rate = past_failure_rates.get(nodeid, 0)
        if past_rate < 0.1 and recent_rate > failure_threshold:  # Was stable, now unstable
            degraded_tests.append({
                "nodeid": nodeid,
                "past_failure_rate": past_rate,
                "recent_failure_rate": recent_rate,
                "change": recent_rate - past_rate
            })
    
    return sorted(degraded_tests, key=lambda x: x["change"], reverse=True)

# Usage example
unstable_tests = find_newly_unstable_tests(sessions)
for test in unstable_tests:
    print(f"Test: {test['nodeid']}")
    print(f"Past failure rate: {test['past_failure_rate']:.1%}")
    print(f"Recent failure rate: {test['recent_failure_rate']:.1%}")
    print(f"Stability degradation: {test['change']:.1%}\n")
```

2. **Identify Recently Stabilized Tests**:
```python
def find_recently_stabilized_tests(all_sessions, lookback_days=30, improvement_threshold=0.3):
    """Find previously flaky/failing tests that are now stable."""
    now = datetime.now()
    cutoff = now - timedelta(days=lookback_days)
    
    # Split sessions by time
    past_sessions = [
        s for s in all_sessions 
        if cutoff <= s.session_start_time <= (now - timedelta(days=7))
    ]
    recent_sessions = [
        s for s in all_sessions 
        if s.session_start_time > (now - timedelta(days=7))
    ]
    
    # Create comparator for outcome analysis
    dimension = OutcomeDimension()
    comparator = DimensionalComparator(dimension)
    
    # Compare past and recent sessions
    results = comparator.compare(past_sessions + recent_sessions, "FAILED", "PASSED")
    
    # Calculate improvement metrics
    improvements = []
    for nodeid in results["differences"]["status_changes"]:
        past_results = [
            r for s in past_sessions 
            for r in s.test_results 
            if r.nodeid == nodeid
        ]
        recent_results = [
            r for s in recent_sessions 
            for r in s.test_results 
            if r.nodeid == nodeid
        ]
        
        if not past_results or not recent_results:
            continue
            
        past_failure_rate = sum(1 for r in past_results if r.outcome == TestOutcome.FAILED) / len(past_results)
        recent_failure_rate = sum(1 for r in recent_results if r.outcome == TestOutcome.FAILED) / len(recent_results)
        
        improvement = past_failure_rate - recent_failure_rate
        if improvement >= improvement_threshold:
            improvements.append({
                "nodeid": nodeid,
                "past_failure_rate": past_failure_rate,
                "recent_failure_rate": recent_failure_rate,
                "improvement": improvement
            })
    
    return sorted(improvements, key=lambda x: x["improvement"], reverse=True)

# Usage example
stabilized_tests = find_recently_stabilized_tests(sessions)
print("Recently Stabilized Tests:")
for test in stabilized_tests:
    print(f"\nTest: {test['nodeid']}")
    print(f"Past failure rate: {test['past_failure_rate']:.1%}")
    print(f"Recent failure rate: {test['recent_failure_rate']:.1%}")
    print(f"Stability improvement: {test['improvement']:.1%}")
```

3. **Generate Stability Trend Report**:
```python
def generate_stability_report(all_sessions, min_runs=10):
    """Generate a comprehensive test stability report."""
    # Find both degrading and improving tests
    degraded = find_newly_unstable_tests(all_sessions)
    improved = find_recently_stabilized_tests(all_sessions)
    
    # Group tests by module for better organization
    def group_by_module(tests):
        modules = {}
        for test in tests:
            module = test["nodeid"].split("::")[0]
            if module not in modules:
                modules[module] = []
            modules[module].append(test)
        return modules
    
    degraded_by_module = group_by_module(degraded)
    improved_by_module = group_by_module(improved)
    
    # Generate report
    print("=== Test Stability Trend Report ===\n")
    
    print("🔴 Recently Degraded Tests:")
    for module, tests in degraded_by_module.items():
        print(f"\nModule: {module}")
        for test in tests:
            print(f"  • {test['nodeid'].split('::')[-1]}")
            print(f"    Past failure rate: {test['past_failure_rate']:.1%}")
            print(f"    Recent failure rate: {test['recent_failure_rate']:.1%}")
    
    print("\n🟢 Recently Stabilized Tests:")
    for module, tests in improved_by_module.items():
        print(f"\nModule: {module}")
        for test in tests:
            print(f"  • {test['nodeid'].split('::')[-1]}")
            print(f"    Past failure rate: {test['past_failure_rate']:.1%}")
            print(f"    Recent failure rate: {test['recent_failure_rate']:.1%}")
    
    # Summary statistics
    total_tests = len({r.nodeid for s in all_sessions for r in s.test_results})
    print(f"\nSummary:")
    print(f"Total unique tests: {total_tests}")
    print(f"Tests with degraded stability: {len(degraded)} ({len(degraded)/total_tests:.1%})")
    print(f"Tests with improved stability: {len(improved)} ({len(improved)/total_tests:.1%})")

# Usage example
generate_stability_report(sessions)
```

This filtering and comparison system provides powerful tools for analyzing test results across different dimensions. Use it to:
- Identify problematic test patterns
- Compare test behavior across environments
- Track performance regressions
- Monitor test stability
- Analyze test coverage by module

For more examples and detailed API documentation, refer to the pytest-insight API reference.
