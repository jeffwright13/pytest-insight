# pytest-insight

A pytest plugin for analyzing test health, performance, and patterns across test runs.

## Features

- **Test Health Analysis**: Track pass rates, flaky tests, and warning patterns
- **Pattern Matching**: Filter tests using glob patterns or regex
- **Cross-Version Comparison**: Compare test behavior across Python versions
- **Performance Analysis**: Identify slow tests and track runtime trends
- **Session Context**: Preserve test relationships and session metadata

## Quick Start

```bash
pip install pytest-insight
```

```python
from pytest_insight.query import Query

# Basic test health analysis
query = Query()
health = (query
    .for_sut("my-service")
    .in_last_days(7)
    .execute())

print(f"Pass rate: {health.pass_rate:.1%}")
print(f"Flaky rate: {health.flaky_rate:.1%}")

# Find slow tests with warnings
slow_tests = (query
    .with_warning(True)      # Session-level filter
    .filter_by_test()          # Test-level filter
    .with_duration_between(10.0, float("inf"))
    .apply()                   # Back to session context
    .execute())

# Pattern matching (glob or regex)
api_tests = (query
    .filter_by_test()
    .with_pattern("api")       # Matches test_api.py::test_get
    .apply()
    .execute())

regex_tests = (query
    .filter_by_test()
    .with_pattern(r"test_\w{3}$", use_regex=True)
    .apply()
    .execute())
```

## Documentation

- [User Guide](docs/user_guide.md): Detailed usage examples and best practices
- [API Reference](docs/api.md): Complete API documentation
- [Pattern Matching](docs/patterns.md): Pattern matching rules and examples
- [Examples](pytest_insight/playground.py): Interactive examples and playground

## Contributing

Contributions welcome! Please read our [Contributing Guide](CONTRIBUTING.md).

## License

MIT License - see [LICENSE](LICENSE) for details.
