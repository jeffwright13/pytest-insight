# Pytest-Insight CLI

This directory contains two CLI implementations for pytest-insight:

1. `insights_cli.py` - The new, dynamic CLI implementation based on Typer
2. `analyze_test_data_new.py` - A backward-compatible wrapper around the new CLI

## New CLI: `insights_cli.py`

The new CLI is built with [Typer](https://typer.tiangolo.com/) and dynamically discovers methods in the Insights API. This means that as new methods are added to the API, they automatically become available in the CLI without requiring any changes to the CLI code.

### Features

- **Dynamic Command Discovery**: Automatically discovers and exposes methods from the Insights API
- **Rich Output Formatting**: Uses the [rich](https://rich.readthedocs.io/) library for beautiful terminal output
- **Type Annotations**: Leverages Python type hints for parameter validation and help text generation
- **Comprehensive Help**: Provides detailed help text for all commands and parameters

### Usage

```bash
# Get help
python -m pytest_insight.utils.insights_cli --help

# List all available commands
python -m pytest_insight.utils.insights_cli list-commands

# Generate a summary report
python -m pytest_insight.utils.insights_cli summary --days 7

# Run a specific analysis
python -m pytest_insight.utils.insights_cli tests-error-patterns --sut my-service

# Output in JSON format
python -m pytest_insight.utils.insights_cli tests-test-health-score --format json
```

## Backward Compatibility: `analyze_test_data_new.py`

This is a simplified wrapper around the new CLI that maintains backward compatibility with the original `analyze_test_data.py` implementation. It provides the same interface as the original implementation but delegates to the new Insights API.

### Usage

```bash
# Get help
python -m pytest_insight.utils.analyze_test_data_new --help

# Run analysis with filtering
python -m pytest_insight.utils.analyze_test_data_new --sut my-service --days 7

# Output in JSON format
python -m pytest_insight.utils.analyze_test_data_new --format json
```

## Migration Guide

If you're currently using `analyze_test_data.py`, you can switch to the new implementation by:

1. Replacing imports:
   ```python
   # Old
   from pytest_insight.utils.analyze_test_data import analyze_test_data
   
   # New
   from pytest_insight.utils.analyze_test_data_new import analyze_test_data
   ```

2. For CLI usage, use the new script:
   ```bash
   # Old
   python -m pytest_insight.utils.analyze_test_data --sut my-service
   
   # New
   python -m pytest_insight.utils.analyze_test_data_new --sut my-service
   ```

For new projects, we recommend using the new `insights_cli.py` directly, as it provides more features and better integration with the Insights API.

## Implementation Details

The new CLI uses Python's introspection capabilities to discover methods in the Insights API classes. It then generates Typer commands based on these methods, using docstrings and type annotations to generate help text and parameter validation.

This approach has several advantages:

1. **Maintainability**: As the API evolves, the CLI automatically adapts without requiring manual updates
2. **Consistency**: The CLI interface directly reflects the API structure, making it easier to understand and use
3. **Extensibility**: New features can be added to the API and automatically become available in the CLI

The implementation follows the same pattern as the Introspective Web API, where endpoints are automatically discovered and exposed based on the underlying API structure.
