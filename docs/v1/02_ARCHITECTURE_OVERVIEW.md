# The pytest-insight Architecture: Query, Compare, Analyze, and Insights

This document explains the layered architecture of pytest-insight, built around four fundamental components that work together to provide a comprehensive test analysis solution.

For a conceptual understanding of the four layers, please refer to [01_CONCEPTUAL_FRAMEWORK.md](./01_CONCEPTUAL_FRAMEWORK.md).

For details on how pytest-insight stores and manages test data, see [03_STORAGE.md](./03_STORAGE.md).

For a practical guide on using the pytest-insight interactive shell, please refer to [05_INTERACTIVE_SHELL_TUTORIAL.md](./05_INTERACTIVE_SHELL_TUTORIAL.md).

For exploring and documenting the REST API, you can use the API Explorer. See [07_API_EXPLORER.md](./07_API_EXPLORER.md) for details.

## The Layered Architecture

pytest-insight is designed with a layered architecture where each layer builds upon the previous one:

1. **Query Layer** - The foundation for finding and filtering test data
2. **Comparison Layer** - Builds on Query to identify differences between test runs
3. **Analysis Layer** - Uses Query results to calculate metrics and detect patterns
4. **Insights Layer** - Builds on Analysis to provide interpretations and recommendations

Each layer has a specific focus and responsibility, creating a clean separation of concerns while maintaining a cohesive API.

## Layer 1: Query - Finding the Right Data

The Query component is the foundation of pytest-insight, responsible for retrieving and filtering test data.

### Key Concepts

- **Two-Level Filtering**: Session-level and test-level filters with preserved context
- **Fluent Interface**: Method chaining for intuitive query building
- **Profile Support**: Storage profile integration for flexible data access

### Core Classes

- **Query**: Main entry point for building and executing queries
- **TestFilter**: Protocol defining the interface for test filters
- **QueryResult**: Container for query results with metadata

### Example Usage

```python
from pytest_insight.core.core_api import InsightAPI, query

# Method 1: Using the InsightAPI class (recommended)
api = InsightAPI(profile_name="my_profile")

# Session-level filtering
sessions = api.query().with_sut("api-service").in_last_days(7).execute()

# Test-level filtering (still returns sessions)
sessions = api.query().filter_by_test().with_pattern("test_api*").with_outcome("failed").apply().execute()

# Method 2: Using the standalone query function
q = query(profile_name="my_profile")
sessions = q.with_sut("api-service").in_last_days(7).execute()
```

### Design Principles

1. **Preserve Session Context**: Always return complete TestSession objects, not isolated tests
2. **Accumulate Filters**: Filters combine with AND logic when chaining methods
3. **Flexible Pattern Matching**: Support for glob patterns and regex
4. **Storage Profile Integration**: Query specific storage profiles

## Layer 2: Comparison - Understanding Differences

The Comparison component builds upon Query to identify differences between test runs.

### Key Concepts

- **Base vs. Target**: Compare a base (reference) session against a target (current) session
- **Dual Queries**: Independent configuration of base and target queries
- **Change Categories**: Categorization of test changes (new failures, performance changes, etc.)

### Core Classes

- **Comparison**: Builder for comparison operations with dual query support
- **ComparisonResult**: Container for comparison results with categorized changes

### Example Usage

```python
from pytest_insight.core.core_api import InsightAPI

# Initialize API with a specific profile
api = InsightAPI(profile_name="my_profile")

# Compare test results between two SUTs
comparison = api.compare().between_suts("sut-v1", "sut-v2")

# Get the comparison results
results = comparison.execute()

# Access specific comparison metrics
new_failures = results.new_failures
fixed_tests = results.new_passes
```

### Design Principles

1. **Build on Query**: Leverage the Query system for flexible filtering
2. **Independent Configuration**: Allow separate configuration of base and target queries
3. **Comprehensive Categorization**: Track multiple types of changes
4. **Profile Support**: Compare across different storage profiles

## Layer 3: Analysis - Calculating Metrics

The Analysis component builds upon Query results to calculate metrics and detect patterns.

### Key Concepts

- **Session Analysis**: Session-level metrics and trends
- **Test Analysis**: Test-level stability and performance metrics
- **Metrics Calculation**: Statistical analysis of test data

### Core Classes

- **Analysis**: Top-level entry point for analysis operations
- **SessionAnalysis**: Session-level analytics with failure rate calculation
- **TestAnalysis**: Test-level analytics with stability metrics

### Example Usage

```python
from pytest_insight.core.core_api import InsightAPI

# Initialize API with a specific profile
api = InsightAPI(profile_name="my_profile")

# Create an analysis instance
analysis = api.analyze()

# Get flaky tests
flaky_tests = analysis.identify_flaky_tests()

# Get performance metrics
slowest_tests = analysis.get_slowest_tests(limit=10)

# Get consistently failing tests
failing_tests = analysis.identify_consistently_failing_tests()
```

### Design Principles

1. **Build on Query**: Use Query results as input for analysis
2. **Preserve Context**: Maintain session context during analysis
3. **Statistical Rigor**: Apply proper statistical methods
4. **Profile Support**: Analyze data from specific storage profiles

## Layer 4: Insights - Interpreting Results

The Insights component builds upon Analysis to provide interpretations and recommendations.

### Key Concepts

- **Test Insights**: Advanced patterns and trends from test data
- **Session Insights**: Session-level analytics and health metrics
- **Visualization**: Human-readable presentation of insights
- **Recommendations**: Actionable suggestions based on analysis

### Core Classes

- **Insights**: Top-level entry point for insights operations
- **TestInsights**: Test-level insights and analytics
- **SessionInsights**: Session-level insights and analytics

### Example Usage

```python
from pytest_insight.core.core_api import InsightAPI

# Initialize API with a specific profile
api = InsightAPI(profile_name="my_profile")

# Create an insights instance
insights = api.insights()

# Get a comprehensive summary report
summary = insights.summary_report()

# Get specific insights
stability = insights.test_insights().stability_timeline()
patterns = insights.test_insights().error_patterns()
```

### Design Principles

1. **Build on Analysis**: Use Analysis results as input for insights
2. **Focus on Interpretation**: Translate metrics into meaningful insights
3. **Actionable Recommendations**: Provide clear next steps
4. **Human-Readable Output**: Format results for easy consumption

## API Architecture: Two-Tier Approach

pytest-insight implements a two-tier API architecture that provides both flexibility for power users and convenience for common use cases.

### Key Concepts

- **Lower Tier**: Core introspective API providing direct access to all functionality
- **Higher Tier**: Specialized endpoints and UI components for common workflows
- **Separation of Concerns**: Clear boundaries between tiers while maintaining cohesion
- **Multiple Entry Points**: Different interfaces for different user needs

### Architecture Tiers

1. **Core Python API**
   - The foundation: Query-Compare-Analyze-Insight (Q-C-A-I)
   - Well-tested, feature-complete Python methods
   - Provides the full Query/Filter system with fluent interface
   - Used directly by Python developers for maximum flexibility

2. **Introspective REST API**
   - A thin REST wrapper around the core Python API
   - Automatically generated from the Python API via introspection
   - Exposes all methods and parameters from the core API
   - Provides a stable foundation for building higher-level functionality
   - Accessed via FastAPI endpoints
   - Explored through the API Explorer (see [07_API_EXPLORER.md](./07_API_EXPLORER.md))

3. **Higher-Level API**
   - Built on top of the introspective API
   - Provides "canned" reports and specialized endpoints for common use cases
   - Offers pre-built insights, metrics, and visualizations
   - Handles common workflows like comparing SUTs or analyzing trends

4. **User Interfaces**
   - Various interfaces built on top of either API tier:
     - CLI tools for command-line usage (see [04_CLI_GUIDE.md](./04_CLI_GUIDE.md))
     - Interactive shell for building queries (see [05_INTERACTIVE_SHELL_TUTORIAL.md](./05_INTERACTIVE_SHELL_TUTORIAL.md))
     - Web dashboards for browser-based visualization (see [06_DASHBOARD_GUIDE.md](./06_DASHBOARD_GUIDE.md))

### Implementation Structure

The API implementation follows this structure:

```
pytest_insight/
├── core/                      # Core Python API
│   ├── query.py
│   ├── comparison.py
│   ├── analysis.py
│   └── insights.py
├── rest_api/                  # REST API implementation
│   ├── introspective_api.py   # Lower-tier API
│   ├── high_level_api.py      # Higher-tier API
│   └── templates/             # UI templates
└── web/                       # Web UI components
    └── dashboard.py           # Streamlit dashboard
```

### Benefits of Two-Tier Architecture

This multi-tiered approach gives users the flexibility to work at whatever level of abstraction makes sense for their needs:

- **Power users** can use the core Python API directly
- **Developers** can use the introspective API for custom integrations
- **Most users** can rely on the higher-level API for day-to-day needs
- **Everyone** can benefit from the reference UI implementations

The separation between tiers ensures that:
1. The core functionality remains clean and focused
2. Higher-level components can evolve independently
3. Users can choose the appropriate level of abstraction
4. New interfaces can be built on a stable foundation

## Component Dependencies and Data Flow

The pytest-insight architecture follows a clear dependency chain:

```
Storage → Query → Comparison
                ↘
                  Analysis → Insights
```

Data flows through the system as follows:

1. **Storage** provides raw test data
2. **Query** retrieves and filters the data
3. **Comparison** identifies differences between query results
4. **Analysis** calculates metrics from query results
5. **Insights** interprets analysis results and provides recommendations

## The InsightAPI: A Unified Interface

The `InsightAPI` class provides a unified interface to all components:

```python
from pytest_insight.core.core_api import InsightAPI

# Create an API instance with a specific profile
api = InsightAPI(profile_name="my_profile")

# Access all components through the API
query_result = api.query().for_sut("service").execute()
comparison_result = api.compare().between_suts("v1", "v2").execute()
analysis_result = api.analyze().health_report()
insights_result = api.insights().summary_report()
```

This unified interface maintains the separation of concerns while providing a consistent entry point for all operations.

## Practical Usage Patterns

### 1. Basic Health Check

```python
api = InsightAPI(profile_name="my_profile")
health = api.analyze().health_report()
print(f"Pass rate: {health.pass_rate:.1%}")
print(f"Flaky rate: {health.flaky_rate:.1%}")
```

### 2. Finding Problematic Tests

```python
api = InsightAPI(profile_name="my_profile")
slow_tests = (api.query()
    .with_warning(True)         # Session-level filter
    .filter_by_test()           # Test-level filter
    .with_duration_between(10.0, float("inf"))
    .apply()                    # Back to session context
    .execute())
```

### 3. Comparing Versions

```python
api = InsightAPI(profile_name="my_profile")
diff = api.compare().between_suts("v1.0", "v1.1").execute()
print(f"New failures: {len(diff.new_failures)}")
print(f"Fixed tests: {len(diff.new_passes)}")
```

### 4. Deep Insights

```python
api = InsightAPI(profile_name="my_profile")
insights = api.insights()
patterns = insights.test_insights().error_patterns()
dependencies = insights.test_insights().dependency_graph()
```

## Profile-Based Approach

All components support a profile-based approach for storage configuration:

1. You specify a profile name instead of storage details
2. All operations use the specified profile
3. Profiles can be managed via the storage API
4. Environment variables can override the active profile

This simplifies usage, especially in CI/CD environments where you can set the `PYTEST_INSIGHT_PROFILE` environment variable to control which profile is used.

## Conclusion

The layered architecture of pytest-insight provides a clean separation of concerns while maintaining a cohesive API. Each component has a specific focus and responsibility, building upon the previous layer to provide a comprehensive test analysis solution.

By understanding this architecture, you can effectively leverage pytest-insight to gain valuable insights into your test data and improve the quality of your testing process.

For more information on how to use pytest-insight in your testing workflow, please refer to [04_USING_PYTEST_INSIGHT.md](./04_USING_PYTEST_INSIGHT.md). For details on the pytest-insight REST API, see [06_REST_API.md](./06_REST_API.md).
