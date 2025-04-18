# pytest-insight Conceptual Framework

This document explains the conceptual framework behind pytest-insight's layered architecture, helping you understand the distinct purpose of each layer and how they work together.

For technical details on the implementation of this architecture, see [02_ARCHITECTURE_OVERVIEW.md](./02_ARCHITECTURE_OVERVIEW.md).

## The Four Layers: A Conceptual Overview

pytest-insight is built on four foundational layers, each with a specific focus and responsibility:

1. **Query**: Finding and filtering relevant data
2. **Compare**: Identifying differences between datasets
3. **Analysis**: Calculating metrics and detecting patterns
4. **Insights**: Interpreting results and providing recommendations

Each layer builds upon the previous one, creating a progression from raw data to actionable intelligence.

## Key Concepts

### System Under Test (SUT) vs Testing System

pytest-insight makes an important distinction between:

- **System Under Test (SUT)**: The software being tested. This is the target of your test suite and the primary subject of analysis.
- **Testing System**: The environment running the tests. This includes the machine, CI system, or container that executes the test suite.

This distinction allows for:
- Identifying environment-specific test failures
- Comparing test results across different testing environments
- Detecting issues that only appear on specific testing systems
- Distinguishing between actual product bugs and testing infrastructure problems

### Test Sessions and Results

Test sessions represent a single execution of a test suite against a specific SUT, run on a specific testing system. Each session contains:

## Layer 1: Query - "Where" and "Which"

**Query** is about finding and filtering the right data. It answers questions like:
- Where is the test data stored?
- Which test sessions should we examine?
- Which tests match specific criteria?

Query is **data selection-centric** and focuses on retrieving the right subset of data for further processing.

### Real-World Analogy
Query is like searching for books in a library:
- You specify criteria (author, title, genre)
- You get back a set of books matching those criteria
- You haven't read the books yet, just identified which ones to examine

### Technical Implementation
```python
# Find test sessions from the last 7 days for a specific service
sessions = api.query().with_sut("api-service").in_last_days(7).execute()

# Find failed tests matching a specific pattern
sessions = api.query().filter_by_test().with_pattern("test_api*").with_outcome("failed").apply().execute()

# Find tests that fail on a specific testing system
sessions = api.query().with_testing_system("ci-runner-1").with_outcome("failed").execute()
```

## Layer 2: Compare - "What Changed" and "How Different"

**Compare** builds on Query to identify differences between datasets. It answers questions like:
- What changed between version A and version B?
- How different are the test results between environments?
- Which tests started failing or were fixed?

Compare is **difference-centric** and focuses on identifying changes between two sets of data.

### Real-World Analogy
Compare is like a diff tool for code:
- You have two versions of a file
- The tool highlights what was added, removed, or modified
- You see the changes but haven't analyzed their impact yet

### Technical Implementation
```python
# Compare test results between two versions of a service
comparison = api.compare().between_suts("sut-v1", "sut-v2")
results = comparison.execute()

# Access specific comparison metrics
new_failures = results.new_failures
fixed_tests = results.new_passes

# Compare test results between different testing systems
comparison = api.compare().between_testing_systems("ci-runner-1", "ci-runner-2")
results = comparison.execute()
```

## Layer 3: Analysis - "What" and "How"

**Analysis** builds on Query (and sometimes Compare) to calculate metrics and detect patterns. It answers questions like:
- What is the failure rate?
- How many tests are unreliable?
- What's the average duration?
- Which tests consistently fail together?

Analysis is **data-centric** and focuses on computation, statistical methods, and pattern detection. It transforms raw test data into meaningful metrics.

### Real-World Analogy
Analysis is like lab tests and measurements in healthcare:
- Blood pressure readings, cholesterol levels, heart rate
- BMI calculations, blood sugar measurements
- These are quantitative measurements without interpretation

### Technical Implementation
```python
# Calculate metrics from test data
analysis = api.analyze()
unreliable_tests = analysis.identify_unreliable_tests()
slowest_tests = analysis.get_slowest_tests(limit=10)
failure_rate = analysis.calculate_failure_rate()

# Analyze system-specific failures
system_specific_failures = analysis.identify_system_specific_failures()
```

## Layer 4: Insights - "Why" and "What Next"

**Insights** builds on Analysis to provide interpretation, recommendations, and actionable information. It answers questions like:
- Why are these tests failing together?
- What should be fixed first?
- How is the test health trending?
- What actions would improve stability?

Insights is **action-centric** and focuses on interpretation, visualization, and recommendations. It turns metrics into decisions.

### Real-World Analogy
Insights is like a doctor's diagnosis and treatment plan:
- "Your blood pressure is high because of stress"
- "You should exercise more and reduce salt intake"
- "If you don't make these changes, you risk heart disease"

### Technical Implementation
```python
# Get insights and recommendations
insights = api.insights()
recommendations = insights.test_insights().maintenance_recommendations()
stability_forecast = insights.test_insights().stability_forecast(days=30)
error_patterns = insights.test_insights().error_patterns()

# Get testing system-specific insights
system_insights = insights.test_insights().testing_system_insights()
```

## The Progressive Nature of the Layers

Each layer builds upon and depends on the previous layers:

1. **Query** provides the foundation by selecting the right data
2. **Compare** uses Query results to identify differences
3. **Analysis** processes Query results to calculate metrics
4. **Insights** interprets Analysis results to provide recommendations

This progression creates a natural flow from data to intelligence:

```
Raw Data → Selected Data → Differences → Metrics → Recommendations
  Storage     Query        Compare     Analysis    Insights
```

## Practical Application: When to Use Each Layer

### Use Query When:
- You need to find specific test sessions or tests
- You want to filter data based on criteria
- You're preparing data for further processing

### Use Compare When:
- You need to identify what changed between versions
- You want to track improvements or regressions
- You're analyzing the impact of code changes

### Use Analysis When:
- You need to calculate metrics from test data
- You want to detect patterns in test results
- You're measuring test suite health

### Use Insights When:
- You need recommendations for improvement
- You want to understand the "why" behind metrics
- You're planning maintenance priorities

## Example Workflow

Here's how the four layers might work together in a typical workflow:

1. **Query**: Find all test sessions for the payment service in the last month
2. **Compare**: Identify differences between the current and previous version
3. **Analysis**: Calculate stability metrics and identify unreliable tests
4. **Insights**: Get recommendations for which tests to fix first and why

```python
# Complete workflow example
api = InsightAPI(profile_name="production")

# 1. Query - Find relevant test sessions
sessions = api.query().with_sut("payment-service").in_last_days(30).execute()

# 2. Compare - Identify changes between versions
comparison = api.compare().between_versions("v1.0", "v1.1").execute()
print(f"New failures: {len(comparison.new_failures)}")

# 3. Analysis - Calculate metrics
analysis = api.analyze()
unreliable_tests = analysis.identify_unreliable_tests()
print(f"Found {len(unreliable_tests)} unreliable tests")

# 4. Insights - Get recommendations
insights = api.insights()
recommendations = insights.test_insights().maintenance_recommendations()
print(f"Top priority: {recommendations[0].test_id} - {recommendations[0].reason}")

# Analyze testing system-specific issues
system_specific_issues = analysis.identify_system_specific_failures()
print(f"Found {len(system_specific_issues)} testing system-specific issues")
```

## Conclusion

Understanding the conceptual framework behind pytest-insight's layered architecture helps you use the right tool for the right job. By recognizing the distinct purpose of each layer, you can more effectively:

- Find the data you need (Query)
- Identify important changes (Compare)
- Calculate meaningful metrics (Analysis)
- Make informed decisions (Insights)

This separation of concerns not only makes the API more intuitive but also allows for a more maintainable and extensible codebase.

For a deeper dive into the technical implementation of this architecture, see [02_ARCHITECTURE_OVERVIEW.md](./02_ARCHITECTURE_OVERVIEW.md).
