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
- **Interactive CLI**: Explore the API through a guided, interactive command-line interface
- **Predictive Analytics**: Forecast test failures, detect anomalies, and predict stability trends
- **Visual Dashboard**: Explore insights through an interactive web dashboard

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

# With dashboard for visual exploration
pip install pytest-insight[dashboard]

# With predictive analytics capabilities
pip install pytest-insight[dashboard]  # includes scikit-learn and other ML dependencies

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

# NEW: Predictive Analytics
# Predict test failures for the next 7 days
predictions = (api.predictive()
    .failure_prediction(days_ahead=7))

# Get high-risk tests
high_risk_tests = predictions["high_risk_tests"]
for test in high_risk_tests[:5]:  # Show top 5
    print(f"Test: {test['nodeid']}, Probability: {test['probability']:.1%}")

# Detect anomalous test behavior
anomalies = api.predictive().anomaly_detection()
for test in anomalies["anomalies"][:3]:  # Show top 3
    print(f"Anomalous test: {test['nodeid']}, Score: {test['score']:.1%}")

# Forecast test stability trends
stability = api.predictive().stability_forecast()
print(f"Current stability: {stability['current_stability']:.1f}%")
print(f"Forecasted stability: {stability['forecasted_stability']:.1f}%")
print(f"Trend: {stability['trend_direction']}")
```

### Using the Command Line Interface

```bash
# Generate insights report
insight analyze --sut my-service --days 30

# Compare test runs between versions
insight compare --base-sut service-v1 --target-sut service-v2

# Query for specific test patterns
insight query --pattern "test_api*" --days 7

# NEW: Generate predictive analytics
insight predict failures --sut my-service --days-ahead 7
insight predict anomalies --sut my-service
insight predict stability --profile production

# NEW: Launch the interactive dashboard
insight dashboard launch
```

### Using the Dashboard

```bash
# Launch the dashboard with default settings
insight dashboard launch

# Specify a port and profile
insight dashboard launch --port 8502 --profile production
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

### Interactive CLI

The interactive CLI provides a guided exploration of the pytest-insight API:

```bash
# Start the interactive CLI
insight core_api

# Or with a specific profile
insight core_api --profile my_profile
```

This interactive shell allows you to:
- Build complex queries step-by-step
- Compare test runs with guided workflows
- Explore test data with rich terminal visualizations
- Generate sample test data for experimentation

The CLI retains context between steps and provides progressive disclosure of features, making it ideal for both learning the API and for daily test analysis tasks.

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
