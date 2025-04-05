# Pytest-Insight Backward-Compatible Wrapper

This document explains the backward-compatible wrapper for the pytest-insight API.

## Overview

The `analyze_test_data_new.py` script provides a backward-compatible wrapper around the new pytest-insight API, maintaining the same command-line interface as the original `analyze_test_data.py` script while delegating to the new Insights API methods.

## Usage

```bash
python -m pytest_insight.utils.analyze_test_data_new [OPTIONS]
```

### Options

The wrapper supports the same options as the original `analyze_test_data.py` script:

- `--data-path, -d`: Path to test data
- `--sut, -s`: Filter by system under test
- `--days`: Filter by number of days
- `--test, -t`: Filter by test name pattern
- `--profile, -p`: Storage profile to use
- `--format, -f`: Output format (text or json)

## Migration Guide

### Using the Wrapper

If you're currently using the original `analyze_test_data.py` script, you can switch to the wrapper by changing your import:

```bash
# Original
python -m pytest_insight.utils.analyze_test_data [OPTIONS]

# New wrapper
python -m pytest_insight.utils.analyze_test_data_new [OPTIONS]
```

### Migrating to the New CLI

While the wrapper provides backward compatibility, we recommend migrating to the new CLI for access to the full range of features:

```bash
# Using the wrapper
python -m pytest_insight.utils.analyze_test_data_new --sut my-system

# Using the new CLI
python -m pytest_insight.utils.insights_cli insights-tests-error_patterns --sut my-system
```

## Feature Mapping

The following table shows how features from the original script map to the new API:

| Original Feature | New API Method |
|------------------|---------------|
| Error patterns analysis | `insights.tests.error_patterns()` |
| Flaky tests identification | `insights.tests.flaky_tests()` |
| Slowest tests identification | `insights.tests.slowest_tests()` |
| Test outcome distribution | `insights.tests.outcome_distribution()` |
| Session metrics | `insights.sessions.session_metrics()` |
| SUT comparison | `insights.sessions.sut_comparison()` |
| Duration trends | `insights.trends.duration_trends()` |
| Failure trends | `insights.trends.failure_trends()` |

## Implementation Details

The wrapper script:

1. Parses command-line arguments using the same interface as the original script
2. Creates an instance of the Insights API
3. Applies filters based on the provided arguments
4. Calls the appropriate Insights API methods
5. Formats and displays the results

This approach ensures that existing scripts and workflows continue to work while providing access to the improved functionality of the new API.

## Benefits of the New API

While the wrapper provides backward compatibility, the new API offers several advantages:

- **More comprehensive analysis**: Access to a wider range of analysis methods
- **Better organization**: Methods are organized by category (tests, sessions, trends)
- **More flexible filtering**: More options for filtering test data
- **Better extensibility**: Easier to add new analysis methods
- **Improved performance**: More efficient implementation of analysis methods

We recommend migrating to the new CLI for new projects and gradually updating existing projects to use the new API.
