# pytest-insight

A powerful analytics tool for pytest that helps you understand test behavior, identify patterns, and make data-driven decisions about your test suite.

## Overview

pytest-insight is a pytest plugin that helps you understand your test suite's behavior over time. Unlike traditional test reporting tools that treat each test in isolation, pytest-insight preserves the full context of test sessions, allowing you to see how tests interact and evolve together.

With its intuitive query system, you can easily filter test sessions by time range, system under test, system-specific tags, or other test criteria while maintaining relationships between tests that ran together. This unique approach enables you to spot performance trends, identify correlated failures, and track rerun patterns — giving you deeper insight into your test suite's health and behavior.

Whether you're debugging flaky tests, optimizing performance, or analyzing test patterns across different environments, pytest-insight helps you make data-driven decisions about your testing strategy.

pytest-insight transforms your test results into actionable insights by:
- Tracking test outcomes and performance metrics over time
- Detecting flaky tests and recurring failure patterns
- Comparing test behavior across Python versions and environments
- Providing statistical analysis of test execution trends
- Offering a flexible query API for custom analysis

## Understanding the Query System

pytest-insight uses a powerful two-level query system that preserves full test context:

### 1. Session-Level Filtering
Filter entire test sessions based on properties like:
- System under test (SUT) name
- Date/time range
- Presence of warnings or reruns
- Session ID patterns (critical for comparisons)
- System-specific tags

```python
# Find a specific SUT's recent sessions with warnings
query = Query()
results = (query
    .for_sut("my-service")
    .in_last_days(7)
    .having_warnings(True)
    .execute())
```

```python
# Find sessions with specific tags
results = (query
    .for_sut("my-service")
    .with_tag("env", "prod")
    .execute())
```

### 2. Test-Level Filtering
Filter sessions based on individual test properties while preserving full session context:

```python
# Find sessions with slow integration tests
results = (query
    .filter_tests()
    .with_pattern("*/integration/*")
    .with_duration(10.0, float("inf"))
    .apply()
    .execute())

# You get back full sessions with context
for session in results.sessions:
    print(f"\nSession {session.session_id}:")
    # Access all tests in the session
    for test in session.test_results:
        print(f"- {test.nodeid}: {test.duration}s")
    # See related warnings
    for warning in session.warnings:
        print(f"Warning: {warning.message}")
    # Analyze rerun patterns
    for rerun in session.rerun_test_groups:
        print(f"Rerun: {rerun.nodeid} ({rerun.attempts} attempts)")
```

### Key Benefits

1. **Full Context Preservation**:
   - See all tests that ran together
   - Access session-level warnings
   - Track rerun patterns
   - Analyze test relationships

2. **Flexible Filtering**:
   - Combine session and test filters
   - Filter by any test property
   - Chain multiple conditions
   - Use before/after timestamps

3. **Rich Analysis**:
   - Track test stability over time
   - Identify correlated failures
   - Monitor performance trends
   - Compare across versions

## Quick Start Guide

Install the package:
```bash
pip install pytest-insight
```

### Basic Usage

Here's how to analyze your test results:

```python
from pytest_insight.query.query import Query
from pytest_insight.models import TestOutcome

# Initialize a query
query = Query()

# Find flaky tests (tests with reruns)
flaky_tests = query.with_reruns(True).execute()
print(f"Found {flaky_tests.total_count} flaky test sessions")

# Analyze test performance across Python versions
from pytest_insight.query.comparison import Comparison
comparison = Comparison()
result = (comparison
    .between_suts("ref-sut-python39", "ref-sut-python311")
    .in_last_days(1)
    .execute())

print(f"Comparing {result.base_session.sut_name} vs {result.target_session.sut_name}")
print(f"New failures: {len(result.new_failures)}")
print(f"Fixed failures: {len(result.fixed_failures)}")

# Find slow tests (taking > 10 seconds)
slow_tests = (query
    .filter_tests()
    .with_duration(10.0, float("inf"))
    .apply()
    .execute())

# Find recent failures
recent_failures = (query
    .in_last_days(1)
    .with_outcome(TestOutcome.FAILED)
    .execute())
```

For more examples, see [playground.py](pytest_insight/playground.py).

### Common Use Cases

1. **Monitor Test Health**:
   ```python
   # Get test health metrics for a specific service
   query.for_sut("my-service").in_last_days(7).execute()
   ```

2. **Track Flaky Tests**:
   ```python
   # Find tests that needed reruns to pass
   query.with_reruns(True).with_outcome(TestOutcome.PASSED).execute()
   ```

3. **Performance Analysis**:
   ```python
   # Find tests that got slower
   comparison.between_dates("2025-03-01", "2025-03-11").with_duration_change(1.5).execute()
   ```

## Features

- **Test Session Analysis**:
  - Track test outcomes across sessions
  - Monitor pass/fail rates and trends
  - Identify unstable or flaky tests

- **Failure Pattern Detection**:
  - Find common failure modes
  - Track intermittent failures
  - Analyze error messages and stack traces

- **Performance Tracking**:
  - Monitor test execution times
  - Identify performance regressions
  - Track resource usage patterns

- **Cross-Version Comparison**:
  - Compare results across Python versions
  - Track compatibility issues
  - Validate version upgrades

- **Rich Query API**:
  - Filter by test outcomes, dates, and patterns
  - Custom analysis and reporting
  - Integration with existing tools

- **Data Generation**:
  - Generate practice datasets
  - Simulate test patterns
  - Validate analysis methods

## API Documentation

pytest-insight provides a RESTful API powered by FastAPI:

### Interactive Documentation
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Key Endpoints

```bash
GET /health           # System health status
GET /search           # List available metrics
POST /query           # Query test metrics
POST /compare         # Compare test sessions
```

Example query:
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "target": "test.duration.trend",
    "filters": {
      "sut": "my-service",
      "days": 7,
      "min_duration": 10.0
    }
  }'
```

For more API examples, see [docs/examples/curls.md](docs/examples/curls.md).

## Contributing

We welcome contributions! Whether it's bug reports, feature requests, or code contributions, please feel free to:

1. Open an issue to discuss your ideas
2. Submit a pull request with improvements
3. Help improve our documentation

## License

This project is licensed under the MIT License - see the LICENSE file for details.
