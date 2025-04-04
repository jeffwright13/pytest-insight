# pytest-insight

A pytest plugin for analyzing test health, performance, and patterns across test runs.

## Features

- **Test Health Analysis**: Track pass rates, flaky tests, and warning patterns
- **Pattern Matching**: Filter tests using glob patterns or regex
- **Cross-Version Comparison**: Compare test behavior across Python versions
- **Performance Analysis**: Identify slow tests and track runtime trends
- **Session Context**: Preserve test relationships and session metadata
- **Metrics Visualization**: Expose metrics via REST API and visualize in Grafana
- **Storage Profiles**: Manage multiple storage configurations for different environments

## Installation

### Basic Installation

For the core plugin functionality:

```bash
pip install pytest-insight
```

### Installation Options

pytest-insight is organized with optional dependencies for different use cases:

```bash
# Basic plugin only
pip install pytest-insight

# With metrics server for Grafana integration
pip install pytest-insight[metrics]

# For development
pip install pytest-insight[dev]

# For demo notebooks
pip install pytest-insight[demo]

# For Jupyter notebook integration
pip install pytest-insight[jupyter]

# For all features
pip install pytest-insight[all]
```

## Quick Start

```python
from pytest_insight.core.core_api import InsightAPI, query

# Create a storage profile (one-time setup)
from pytest_insight.core.storage import create_profile
create_profile("my_profile", "json", "/path/to/data.json")  # Optional file_path

# Method 1: Using the InsightAPI class (recommended)
api = InsightAPI(profile_name="my_profile")

# Basic test health analysis
health = (api.query()
    .with_sut("my-service")
    .in_last_days(7)
    .execute())

print(f"Pass rate: {health.pass_rate:.1%}")
print(f"Flaky rate: {health.flaky_rate:.1%}")

# Find slow tests with warnings
slow_tests = (api.query()
    .with_warning(True)         # Session-level filter
    .filter_by_test()           # Test-level filter
    .with_duration_between(10.0, float("inf"))
    .apply()                    # Back to session context
    .execute())

# Method 2: Using the standalone query function
q = query(profile_name="my_profile")

# Pattern matching (glob or regex)
api_tests = (q
    .filter_by_test()
    .with_pattern("api")        # Matches test_api.py::test_get
    .apply()
    .execute())

regex_tests = (q
    .filter_by_test()
    .with_pattern(r"test_\w{3}$", use_regex=True)
    .apply()
    .execute())
```

### Environment Variables

You can control which storage profile is used via environment variables:

```bash
# Set the active profile for all operations
export PYTEST_INSIGHT_PROFILE=my_profile
```

This is particularly useful in CI/CD environments like Jenkins jobs.

### Metrics Server

If you've installed the metrics dependencies, you can run the metrics server:

```bash
# Start the metrics server
insight-metrics

# Or with custom options
insight-metrics --host 0.0.0.0 --port 8000 --profile my_profile
```

The metrics server provides a REST API with Swagger documentation at `/docs` and can be integrated with Grafana for visualization.

### API Servers

pytest-insight provides two API interfaces:

1. **High-Level API** - A structured REST API with predefined endpoints
2. **Introspected API** - A dynamic API that directly exposes the fluent interface methods

You can run both APIs simultaneously with a single command:

```bash
# Start both API servers (High-Level on port 8000, Introspected on port 8001)
insight-api

# Run only the High-Level API
insight-api --high-level-only

# Run only the Introspected API
insight-api --introspected-only

# Customize ports and profile
insight-api --high-level-port 9000 --introspected-port 9001 --profile my_profile
```

Both APIs provide Swagger documentation at `/docs` for exploring available endpoints.

## Documentation

- [User Guide](docs/user_guide.md): Detailed usage examples and best practices
- [API Reference](docs/api.md): Complete API documentation
- [Pattern Matching](docs/patterns.md): Pattern matching rules and examples
- [Storage Profiles](docs/STORAGE.md): Managing storage configurations
- [Query, Compare, Analyze](docs/QUERY_COMPARE_ANALYZE.md): Core workflow documentation
- [Examples](pytest_insight/playground.py): Interactive examples and playground

## Contributing

Contributions welcome! Please read our [Contributing Guide](CONTRIBUTING.md).

## License

MIT License - see [LICENSE](LICENSE) for details.
