# Pytest-Insight CLI

A dynamic command-line interface for the pytest-insight API.

## Overview

The Pytest-Insight CLI provides a comprehensive interface to the entire pytest-insight API, allowing you to:

- Analyze test data for insights
- Query test results with flexible filters
- Compare test metrics between different systems under test
- Generate detailed reports and visualizations
- Manage storage profiles and test sessions

The CLI is designed to be dynamic, automatically discovering and exposing methods from the entire pytest-insight API, including:

- **Insights API**: TestInsights, SessionInsights, TrendInsights
- **Query API**: Filtering and querying test data
- **Comparison API**: Comparing test metrics between different systems
- **Analysis API**: Generating comprehensive reports and analyses

## Installation

The CLI is included with the pytest-insight package. No additional installation is required.

## Usage

### Basic Usage

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

### Available Commands

To see a list of all available commands:

```bash
python -m pytest_insight.utils.insights_cli list-commands
```

### Command Categories

#### Insights.tests

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

#### Insights.sessions

Commands for analyzing session-level insights:

- `insights-sessions-environment_impact`: Analyze how different environments affect test results
- `insights-sessions-session_metrics`: Calculate comprehensive session metrics
- `insights-sessions-sut_comparison`: Compare metrics between different SUTs

#### Insights.trends

Commands for analyzing trends over time:

- `insights-trends-duration_trends`: Analyze session duration trends over time
- `insights-trends-failure_trends`: Analyze test failure trends over time
- `insights-trends-time_comparison`: Compare test metrics between different time periods

#### Query

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

#### Compare

Commands for comparing test metrics:

- `compare-apply_to_both`: Apply the same filter function to both base and target queries
- `compare-between_suts`: Compare between two SUTs
- `compare-execute`: Execute comparison between base and target sessions
- `compare-with_base_profile`: Set the storage profile for the base query
- `compare-with_environment`: Filter sessions by environment tags
- `compare-with_performance_thresholds`: Set custom performance thresholds
- `compare-with_profiles`: Set storage profiles for both base and target queries
- `compare-with_target_profile`: Set the storage profile for the target query

#### Analyze

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

#### Profile

Commands for managing storage profiles:

- `profile-create`: Create a new storage profile
- `profile-delete`: Delete an existing storage profile
- `profile-list`: List all available storage profiles
- `profile-merge`: Merge two or more storage profiles into a single profile
- `profile-rename`: Rename an existing storage profile

### Examples

### Analyze Error Patterns

```bash
python -m pytest_insight.utils.insights_cli insights-tests-error_patterns --sut my-system
```

### Identify Flaky Tests

```bash
python -m pytest_insight.utils.insights_cli insights-tests-flaky_tests --days 30
```

### Generate a Health Report

```bash
python -m pytest_insight.utils.insights_cli analyze-health_report --format json
```

### Compare Two Systems Under Test

```bash
python -m pytest_insight.utils.insights_cli compare-between_suts --sut system1 --target-sut system2
```

### Merge Storage Profiles

```bash
python -m pytest_insight.utils.insights_cli profile-merge --profile profile1 --target-profile profile2
```

## Backward Compatibility

For backward compatibility with the original `analyze_test_data.py` script, a wrapper script is provided:

```bash
python -m pytest_insight.utils.analyze_test_data_new [OPTIONS]
```

This wrapper provides the same interface as the original script but delegates to the new Insights API methods.

## Advanced Usage

### Combining Filters

You can combine multiple filters to narrow down your analysis:

```bash
python -m pytest_insight.utils.insights_cli insights-tests-error_patterns --sut my-system --days 7 --test "test_login*"
```

### Output Formats

Most commands support both text and JSON output formats:

```bash
python -m pytest_insight.utils.insights_cli insights-tests-error_patterns --format json
```

## Extending the CLI

The CLI is designed to be dynamic, automatically discovering methods from the pytest-insight API. When new methods are added to the API, they will automatically be available in the CLI without any changes to the CLI code.
