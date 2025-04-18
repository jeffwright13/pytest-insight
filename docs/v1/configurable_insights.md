# Configurable Insights in pytest-insight

This document explains how to configure and customize insights in pytest-insight.

## Overview

The pytest-insight configurable insights system allows you to:

1. Specify which metrics and sections to include in reports
2. Set thresholds for various analyses
3. Customize the behavior of insights generation
4. Support different environments (local development, CI)

## Configuration Sources

Configurations can be specified in multiple ways, with the following precedence (highest to lowest):

1. Command-line arguments
2. Environment variables
3. Project configuration file (`pytest-insight.toml`)
4. `pyproject.toml` (in the `[tool.pytest-insight]` section)
5. Default configuration

## Configuration File

The main configuration file is `pytest-insight.toml` in your project root. Here's an example:

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

## Command-Line Options

When using the CLI, you can override configuration settings:

```bash
# Use a specific configuration file
insight generate_insights --config-file=my-config.toml

# Include only specific metrics
insight generate_insights --include-metrics="pass_rate,flaky_rate"

# Exclude specific sections
insight generate_insights --exclude-sections="performance_issues"
```

## Environment Variables

For CI environments, you can use environment variables:

```bash
# Enable/disable reports
export PYTEST_INSIGHT_REPORTS_SUMMARY_ENABLED=true

# Set metrics to include
export PYTEST_INSIGHT_REPORTS_SUMMARY_METRICS="pass_rate,flaky_rate,test_count"

# Set performance threshold
export PYTEST_INSIGHT_REPORTS_PERFORMANCE_SLOW_TEST_THRESHOLD=2.0
```

## Available Configuration Options

### Summary Report

```toml
[reports.summary]
enabled = true
metrics = ["pass_rate", "flaky_rate", "test_count", "session_count"]
sections = ["top_failures", "top_flaky", "performance_issues"]
```

### Stability Analysis

```toml
[reports.stability]
enabled = true
threshold = 0.85  # Minimum pass rate to be considered stable
flaky_threshold = 0.05  # Maximum flaky rate to be considered stable
```

### Performance Analysis

```toml
[reports.performance]
enabled = true
slow_test_threshold = 1.0  # Tests taking longer than this (in seconds) are considered slow
```

### Pattern Analysis

```toml
[reports.patterns]
enabled = true
min_frequency = 2  # Minimum occurrences to identify a pattern
```

### Trend Analysis

```toml
[reports.trends]
enabled = true
window_size = 7  # Days to include in each trend point
```

### Dependency Analysis

```toml
[reports.dependencies]
enabled = true
min_correlation = 0.5  # Minimum correlation to consider a dependency
```

## Programmatic Configuration

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

## Best Practices

1. **Start with defaults**: The default configuration provides a good starting point
2. **Version control**: Include your configuration file in version control
3. **CI configuration**: Use environment variables for CI-specific settings
4. **Documentation**: Document any custom configurations for your team
