# Pytest-Insight CLI

A unified command-line interface for the pytest-insight API.

## Overview

The Pytest-Insight CLI provides a comprehensive interface to the entire pytest-insight API, allowing you to:

- Analyze test data for insights
- Query test results with flexible filters
- Compare test metrics between different systems under test
- Generate detailed reports and visualizations
- Manage storage profiles and test sessions
- Configure which metrics and analyses are included in reports

The CLI follows a unified structure with subcommands, making it easy to discover and use:

```bash
insight [subcommand] [options]
```

## Installation

The CLI is included with the pytest-insight package. No additional installation is required.

## Usage

### Basic Usage

```bash
insight [subcommand] [options]
```

For the legacy dynamic CLI:

```bash
python -m pytest_insight.utils.insights_cli [COMMAND] [OPTIONS]
```

### Common Options

Most commands support the following options:

- `--data-path, -d`: Path to test data
- `--sut, -s`: Filter by system under test
- `--days`: Filter by number of days
- `--test, -t`: Filter by test name pattern
- `--profile, -p`: Storage profile to use
- `--format, -f`: Output format (text or json)
- `--insight`: Enable pytest-insight
- `--insight-sut, --is`: Specify the system under test name
- `--insight-test-system-name, --itsn`: Specify the testing system name

### System Under Test (SUT) vs Testing System

pytest-insight makes an important distinction between:

- **System Under Test (SUT)**: The application, component, or service being tested (e.g., "auth-service", "payment-api")
- **Testing System**: Information about the environment where tests are running (hostname, OS, etc.)

When running pytest with pytest-insight enabled:

```bash
# Using long options
pytest --insight --insight-sut="my-application" --insight-test-system-name="ci-runner-1"

# Using short options
pytest --insight --is="my-application" --itsn="ci-runner-1"
```

By default, the SUT name is derived from your current directory name. The testing system information (including hostname) is automatically collected and stored with each test session.

When analyzing test data, you can filter by SUT name:

```bash
insight analyze --sut="my-application"
```

This allows you to compare the same application's test results across different testing environments, which is particularly useful for identifying environment-specific issues.

### Available Subcommands

To see a list of all available subcommands:

```bash
insight --help
```

#### Main Subcommands

- `generate_insights`: Generate insights from test data
- `compare`: Compare test metrics between different versions or time periods
- `analyze`: Analyze test data for specific metrics
- `profile`: Manage storage profiles
- `query`: Query test data with flexible filters
- `core_api`: Interactive REPL for exploring the pytest-insight API

### Configurable Insights

The `generate_insights` command supports configurable insights, allowing you to specify which metrics and analyses are included in reports:

```bash
insight generate_insights [options]
```

#### Configuration Options

- `--config-file`: Path to configuration file
- `--include-metrics`: Comma-separated list of metrics to include (e.g., 'pass_rate,flaky_rate')
- `--include-sections`: Comma-separated list of sections to include (e.g., 'top_failures,top_flaky')
- `--exclude-metrics`: Comma-separated list of metrics to exclude
- `--exclude-sections`: Comma-separated list of sections to exclude

Example:

```bash
insight generate_insights --sut my-system --include-metrics="pass_rate,flaky_rate" --include-sections="top_failures,top_flaky"
```

### Configuration File

You can specify configuration options in a `pytest-insight.toml` file in your project root:

```toml
[reports.summary]
enabled = true
metrics = ["pass_rate", "flaky_rate", "test_count", "session_count"]
sections = ["top_failures", "top_flaky", "performance_issues"]

[reports.stability]
enabled = true
threshold = 0.85  # Minimum pass rate to be considered stable
flaky_threshold = 0.05  # Maximum flaky rate to be considered stable
```

See the [configurable insights documentation](./configurable_insights.md) for more details.

### Environment Variables

For CI environments, you can use environment variables:

```bash
# Enable/disable reports
export PYTEST_INSIGHT_REPORTS_SUMMARY_ENABLED=true

# Set metrics to include
export PYTEST_INSIGHT_REPORTS_SUMMARY_METRICS="pass_rate,flaky_rate,test_count"

# Set performance threshold
export PYTEST_INSIGHT_REPORTS_PERFORMANCE_SLOW_TEST_THRESHOLD=2.0
```

## Legacy Dynamic CLI

The legacy dynamic CLI is still available and provides access to the entire pytest-insight API:

### Insights.tests

Commands for analyzing test-level insights:

- `insights-tests-correlation_analysis`: Analyze correlations between test outcomes
- `insights-tests-dependency_graph`: Analyze which tests tend to fail together
- `insights-tests-error_patterns`: Analyze common error patterns across test failures
- `insights-tests-flaky_tests`: Identify flaky tests across all sessions
- `insights-tests-outcome_distribution`: Analyze test outcome distribution
- `insights-tests-seasonal_patterns`: Analyze seasonal patterns in test failures
- `insights-tests-slowest_tests`: Identify the slowest tests
- `insights-tests-stability_timeline`: Generate test stability timeline data
- `insights-tests-test_health_score`: Calculate a composite health score for tests
- `insights-tests-test_patterns`: Analyze test name patterns

### Insights.sessions

Commands for analyzing session-level insights:

- `insights-sessions-environment_impact`: Analyze how different environments affect test results
- `insights-sessions-session_metrics`: Calculate comprehensive session metrics
- `insights-sessions-sut_comparison`: Compare metrics between different SUTs

### Insights.trends

Commands for analyzing trends over time:

- `insights-trends-duration_trends`: Analyze session duration trends over time
- `insights-trends-failure_trends`: Analyze test failure trends over time
- `insights-trends-time_comparison`: Compare test metrics between different time periods

### Query

Commands for querying test data:

- `query-after`: Filter sessions after given timestamp
- `query-before`: Filter sessions before given timestamp
- `query-date_range`: Filter sessions between two dates
- `query-execute`: Execute query and return results
- `query-filter_by_test`: Start building test-level filters
- `query-for_sut`: Filter sessions by SUT name
- `query-in_last_days`: Filter sessions from the last N days
- `query-in_last_hours`: Filter sessions from last N hours
- `query-in_last_minutes`: Filter sessions from last N minutes
- `query-in_last_seconds`: Filter sessions from last N seconds
- `query-test_nodeid_contains`: Filter sessions containing tests with nodeid matching pattern
- `query-to_dict`: Convert query to dictionary
- `query-with_outcome`: Filter sessions containing tests with specific outcome
- `query-with_profile`: Switch to a different storage profile for this query
- `query-with_reruns`: Filter sessions based on presence of test reruns
- `query-with_session_id_pattern`: Filter sessions by ID pattern
- `query-with_session_tag`: Filter sessions by session tag
- `query-with_warning`: Filter sessions by presence of warnings

### Compare

Commands for comparing test metrics:

- `compare-apply_to_both`: Apply the same filter function to both base and target queries
- `compare-between_suts`: Compare between two SUTs
- `compare-execute`: Execute comparison between base and target sessions
- `compare-with_base_profile`: Set the storage profile for the base query
- `compare-with_environment`: Filter sessions by environment tags
- `compare-with_performance_thresholds`: Set custom performance thresholds
- `compare-with_profiles`: Set storage profiles for both base and target queries
- `compare-with_target_profile`: Set the storage profile for the target query

### Analyze

Commands for analyzing test data:

- `analyze-calculate_average_duration`: Calculate the average test duration
- `analyze-calculate_pass_rate`: Calculate the overall pass rate
- `analyze-compare_health`: Compare health metrics between two sets of sessions
- `analyze-count_total_tests`: Count the total number of tests
- `analyze-health_report`: Generate a comprehensive health report
- `analyze-identify_consistently_failing_tests`: Identify consistently failing tests
- `analyze-identify_consistently_failing_tests_with_hysteresis`: Identify consistently failing tests with hysteresis
- `analyze-identify_flaky_tests`: Identify tests with inconsistent outcomes
- `analyze-identify_most_failing_tests`: Identify tests with the highest failure counts
- `analyze-identify_slowest_tests`: Identify the slowest tests
- `analyze-performance_report`: Generate a performance report
- `analyze-stability_report`: Generate a stability report
- `analyze-with_profile`: Set the storage profile for analysis
- `analyze-with_query`: Apply a query function to filter sessions

### Profile

Commands for managing storage profiles:

- `profile-create`: Create a new storage profile
- `profile-delete`: Delete an existing storage profile
- `profile-list`: List all available storage profiles
- `profile-merge`: Merge two or more storage profiles into a single profile
- `profile-rename`: Rename an existing storage profile

## Advanced Usage

### Combining Filters

You can combine multiple filters to narrow down your analysis:

```bash
insight generate_insights --sut my-system --days 7 --test "test_login*"
```

### Output Formats

Most commands support both text and JSON output formats:

```bash
insight generate_insights --format json
```

### Programmatic Configuration

When using the Python API, you can configure insights programmatically:

```python
from pytest_insight.core.core_api import InsightAPI

# Create an insights instance with custom configuration
api = InsightAPI()
insights = api.insights().with_config({
    "reports": {
        "summary": {
            "metrics": ["pass_rate", "flaky_rate"],
            "sections": ["top_failures"]
        }
    }
})

# Generate a report with the custom configuration
report = insights.summary_report()
```

## Extending the CLI

The CLI is designed to be modular and extensible. New subcommands can be added by extending the CLI implementation in `cli_dev.py`.

For the legacy dynamic CLI, it automatically discovers methods from the pytest-insight API. When new methods are added to the API, they will automatically be available in the CLI without any changes to the CLI code.
