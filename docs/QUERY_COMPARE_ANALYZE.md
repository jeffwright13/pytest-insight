
## Content for docs/QUERY_COMPARE_ANALYZE.md

```markdown
# Query, Compare, Analyze: The pytest-insight Workflow

This document explains the core workflow of pytest-insight, built around three fundamental operations: Query, Compare, and Analyze.

## The Three Core Operations

pytest-insight is designed around a simple yet powerful workflow:

1. **Query** - Find and filter relevant test sessions
2. **Compare** - Identify differences between test runs
3. **Analyze** - Extract insights and metrics from test data

Each operation builds on the previous one, allowing you to progressively refine your understanding of test results.

## Query: Finding the Right Data

The Query operation is your starting point for working with test data. It allows you to find and filter test sessions based on various criteria.

### Two-Level Filtering Design

The Query API uses a two-level filtering approach:

1. **Session-Level Filtering**: Filter entire test sessions based on properties like SUT name, time range, or presence of warnings.
2. **Test-Level Filtering**: Filter by individual test properties while preserving the session context.

### Key Concept: Preserving Session Context

An important aspect of the Query API is that both levels of filtering return complete `TestSession` objects, not individual test results. This preserves the valuable session context, including:

- Warnings that occurred during the session
- Rerun patterns for flaky tests
- Relationships between tests
- Environmental factors

### Example Workflow

```python
from pytest_insight.query import Query

# Create a query from all available sessions
query = Query.from_storage()

# Session-level filtering
sessions = query.for_sut("api-service").in_last_days(7).execute()

# Test-level filtering (still returns sessions)
sessions = query.filter_by_test().with_pattern("test_api*").with_outcome(TestOutcome.FAILED).apply().execute()
