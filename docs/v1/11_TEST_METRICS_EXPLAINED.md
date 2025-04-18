# Test Metrics Explained

This document provides detailed explanations of the test metrics used in pytest-insight. Understanding these metrics will help you interpret the dashboard and CLI output more effectively.

## Core Test Health Metrics

### Reliability Index

**Definition**: The percentage of tests with consistent outcomes out of all tests.

**Calculation**:
1. A test is considered unstable if it requires reruns
2. Reliability Index = 100% - (Number of Unstable Tests / Total Number of Unique Tests) * 100%

**Interpretation**:
- Higher reliability index indicates more stable test suites
- A healthy test suite should have a reliability index above 95%
- Tests with low reliability require more attention as they are less predictable

### Rerun Recovery Rate

**Definition**: The percentage of tests that passed after being rerun.

**Calculation**:
- Rerun Recovery Rate = (Number of Tests That Passed After Rerun / Total Number of Rerun Tests) * 100%

**Interpretation**:
- Higher rerun recovery rates indicate more flaky tests rather than genuine failures
- This metric helps distinguish between flaky tests and actual bugs
- A high recovery rate with a low reliability index suggests environmental or timing issues

### Flaky Rate (Legacy Metric)

**Definition**: The percentage of tests that exhibit flaky behavior out of all tests.

**Calculation**:
1. A test is considered flaky if it has been rerun and eventually passed
2. Overall Flaky Rate = (Number of Flaky Tests / Total Number of Unique Tests) * 100%
3. For individual tests, Flake Rate = (1 - Pass Rate) * 100%, where Pass Rate is the ratio of sessions where the test eventually passed to the total number of runs (including reruns)

**Interpretation**:
- Higher flaky rates indicate less stable test suites
- Tests with high individual flake rates require more attention as they are less reliable
- A healthy test suite should have a flaky rate below 5%

### Failure Rate

**Definition**: The percentage of tests that failed out of all tests.

**Calculation**:
- Failure Rate = (Number of Failed Tests / Total Number of Tests) * 100%

**Interpretation**:
- Higher failure rates indicate more issues in the codebase or test suite
- A healthy test suite should have a failure rate below 10%

### Pass Rate

**Definition**: The percentage of tests that passed on the first attempt.

**Calculation**:
- Pass Rate = (Number of Passed Tests / Total Number of Tests) * 100%

**Interpretation**:
- Higher pass rates indicate a healthier codebase and test suite
- A healthy test suite should have a pass rate above 85%

### Rerun Success Rate

**Definition**: The percentage of tests that passed after being rerun.

**Calculation**:
- Rerun Success Rate = (Number of Tests That Passed After Rerun / Total Number of Rerun Tests) * 100%

**Interpretation**:
- Higher rerun success rates indicate more flaky tests rather than genuine failures
- This metric helps distinguish between flaky tests and actual bugs

## Test Stability Metrics

### Test Stability Score

**Definition**: A composite score (0-100) that measures the overall stability of tests.

**Calculation**:
- Based on a weighted formula that considers:
  - Pass rate (50% weight)
  - Flakiness (20% weight)
  - Duration stability (15% weight)
  - Failure pattern (15% weight)

**Interpretation**:
- Higher scores indicate more stable test suites
- Scores below 60 indicate significant stability issues
- Scores above 80 indicate a healthy, stable test suite

### Flakiness Delta

**Definition**: The change in flakiness rate over time.

**Calculation**:
- Flakiness Delta = Current Period Flaky Rate - Previous Period Flaky Rate

**Interpretation**:
- Negative values indicate improving stability
- Positive values indicate degrading stability
- Values close to zero indicate stable flakiness

## Performance Metrics

### Average Duration

**Definition**: The average time taken to execute a test.

**Calculation**:
- Average Duration = Total Test Execution Time / Number of Tests

**Interpretation**:
- Lower average durations indicate more efficient tests
- Sudden increases may indicate performance regressions

### Test Suite Duration Trend

**Definition**: The trend of total test suite execution time over time.

**Calculation**:
- Calculated by comparing the average test suite duration over consecutive time periods

**Interpretation**:
- Upward trends indicate decreasing performance
- Downward trends indicate improving performance
- Stable trends indicate consistent performance

## Advanced Metrics

### Regression Rate

**Definition**: The rate at which previously passing tests start failing.

**Calculation**:
- Regression Rate = (Number of Tests That Changed from Pass to Fail / Total Number of Previously Passing Tests) * 100%

**Interpretation**:
- Higher rates indicate more code changes breaking existing functionality
- Lower rates indicate more stable code changes

### Environment Impact

**Definition**: How much test outcomes vary across different environments.

**Calculation**:
- Based on the variance of pass rates across different environments

**Interpretation**:
- Higher values indicate environment-dependent test results
- Lower values indicate consistent test results across environments
