# pytest-insight Interactive Shell Tutorial

This document provides a practical guide to using the pytest-insight interactive shell for querying and analyzing test results. For a comprehensive overview of the pytest-insight architecture, please refer to [QUERY_COMPARE_ANALYZE.md](./QUERY_COMPARE_ANALYZE.md).

## 1. Building Basic Queries

In the shell, you can build queries incrementally. Each command maintains the state from previous commands:

```bash
# Start with a basic query
query.with_profile default

# Add a time filter
query.in_last_days 30

# Add a SUT filter
query.for_sut my-service

# Execute the query to get results
query.execute
```

## 2. Test-Level Filtering

You can switch to test-level filtering and back:

```bash
# Start with a session-level query
query.with_profile default

# Switch to test-level filtering
query.filter_by_test

# Add test-specific filters
query.with_outcome failed

# Go back to session context
query.apply

# Execute the query
query.execute
```

## 3. Examining Results

After executing a query, you can examine the results:

```bash
# Execute a query
query.with_profile default.in_last_days 7.execute

# View session details
session.list

# View details of a specific session
session.show SESSION_ID

# View failures in a session
session.failures SESSION_ID
```

## 4. Combining Multiple Filters

You can build complex queries by chaining multiple filters:

```bash
# Start with a basic query
query.with_profile default

# Add time constraints
query.in_last_days 14

# Add SUT filter
query.for_sut my-service

# Add session tag filter
query.with_session_tag production

# Switch to test-level filtering
query.filter_by_test

# Add test pattern filter
query.with_pattern test_api_*

# Back to session context
query.apply

# Execute the query
query.execute
```

## 5. Using Help and History

The shell provides help and history features:

```bash
# Get general help
help

# View command history
history

# Get help on specific commands
help query
help session
```

## 6. Saving and Loading Queries

You can save queries for later use:

```bash
# Build and execute a query
query.with_profile default.in_last_days 7.execute

# Save the query for later
save my_query

# Load a saved query
load my_query
```

## 7. Comparing Results

You can set up comparisons between different queries:

```bash
# Set up a base query
query.with_profile default.in_last_days 30.for_sut service-v1

# Save as base for comparison
comparison.with_base_query

# Set up target query
query.with_profile default.in_last_days 30.for_sut service-v2

# Execute comparison
comparison.execute
