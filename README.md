# pytest-insight

A pytest plugin for analyzing test health, performance, and patterns across test runs.

## Features

- **Test Health Analysis**: Track pass rates, flaky tests, and warning patterns
- **Pattern Matching**: Filter tests using glob patterns or regex
- **Cross-Version Comparison**: Compare test behavior across Python versions
- **Performance Analysis**: Identify slow tests and track runtime trends
- **Session Context**: Preserve test relationships and session metadata
- **Metrics Visualization**: Expose metrics via REST API and visualize in the built-in dashboard
- **Storage Profiles**: Manage multiple storage configurations for different environments
- **Interactive CLI**: Explore the API through a guided, interactive command-line interface
- **Predictive Analytics**: Forecast test failures, detect anomalies, and predict stability trends
- **Visual Dashboard**: Explore insights through an interactive web dashboard

## Installation

### Recommended Installation

We recommend using [uv](https://github.com/astral-sh/uv) for faster and more reliable package installation:

```bash
# Install with uv
uv pip install pytest-insight
```

### Traditional Installation

If you prefer using pip directly:

```bash
pip install pytest-insight
```

### Installation Options

pytest-insight is organized with optional dependencies for different use cases:

```bash
# Basic plugin only
uv pip install pytest-insight

# With metrics server for API integration
uv pip install pytest-insight[metrics]

# With dashboard for visual exploration
uv pip install pytest-insight[dashboard]

# With predictive analytics capabilities
uv pip install pytest-insight[predictive]  # includes scikit-learn and other ML dependencies

# For development
uv pip install pytest-insight[dev]

# For demo data generation
uv pip install pytest-insight[demo]

# For all features
uv pip install pytest-insight[all]
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

# Generate predictive analytics
insight predict failures --sut my-service --days-ahead 7
insight predict anomalies --sut my-service
insight predict stability --profile production

# Launch the interactive dashboard
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

The metrics server provides a REST API with Swagger documentation at `/docs` and can be integrated with the built-in dashboard for visualization.

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

### Generating Trend Data

You can generate realistic trend data to explore the dashboard features:

```bash
# Generate trend data with default settings
insight generate trends --profile demo

# Customize trend generation
insight generate trends --profile demo --days 14 --trend-strength 0.8 --anomaly-rate 0.1
```

This creates test data with realistic patterns including:
- Gradual degradation in test stability
- Cyclic patterns in test failures
- Correlated test failures
- Anomaly patterns for detection

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

## Usage

### Basic Usage

To enable pytest-insight, use the `--insight` flag:

```bash
pytest --insight
```

### Configuration Options

pytest-insight provides several configuration options:

- `--insight`: Enable the pytest-insight plugin
- `--insight-sut`, `--is`: Specify the System Under Test (SUT) name (defaults to current directory name)
- `--insight-test-system-name`, `--itsn`: Specify the testing system name (overrides hostname)
- `--insight-profile`, `--ip`: Specify the storage profile to use (defaults to "default")

### System Under Test (SUT) vs Testing System

pytest-insight makes an important distinction between:

- **System Under Test (SUT)**: The application, component, or service being tested (e.g., "auth-service", "payment-api")
- **Testing System**: Information about the environment where tests are running (hostname, OS, etc.)

By default, the SUT name is derived from your current directory name. You can specify a custom SUT name:

```bash
pytest --insight --insight-sut="my-application"
```

The testing system information (including hostname) is automatically collected and stored with each test session. You can also specify a custom testing system name:

```bash
pytest --insight --insight-test-system-name="ci-runner-1"
```

Using short options:

```bash
pytest --insight --is="my-application" --itsn="ci-runner-1"
