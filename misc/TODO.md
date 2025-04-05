# pytest-insight TODO List

This document outlines the planned improvements and enhancements for the pytest-insight project, organized by priority and component.

## 1. Comparison API Enhancements

### High Priority
- [ ] **Implement reliable session matching**
  - Create methods to identify corresponding test runs across versions
  - Support matching based on timestamps, tags, or metadata
  - Handle edge cases like renamed tests

- [ ] **Design ComparisonResult class**
  - Define a comprehensive structure for comparison results
  - Include all comparison categories with clear access methods
  - Support serialization/deserialization for persistence

- [ ] **Create fluent interface**
  - Implement a chainable API similar to the Query component
  - Methods should chain naturally and be self-descriptive
  - Example: `comparison.between_suts("base-sut", "target-sut").with_session_id_pattern("base-*", "target-*").execute()`

- [ ] **Add basic comparison categories**
  - Implement core categories (new failures, fixed tests, flaky tests)
  - Ensure proper classification of test results
  - Support filtering by category

### Medium Priority
- [ ] **Expand comparison categories**
  - Add performance regressions/improvements detection
  - Implement warning changes tracking (new warnings, fixed warnings)
  - Add test stability metrics (flakiness score)

- [ ] **Support multi-version comparison**
  - Allow comparing more than two versions at once
  - Track trends across multiple versions/runs
  - Provide historical context for test behavior

- [ ] **Implement combined filtering**
  - Support filtering on both base and target sessions with different criteria
  - Enable complex queries like "tests that failed in target but passed in base AND took longer than X seconds"
  - Maintain consistency with the existing Query API

## 2. Analysis API Improvements

### High Priority
- [ ] **Enhance health report**
  - Add trend data to show changes over time
  - Include actionable recommendations
  - Add parameterization (include_trends, include_recommendations, min_score_threshold)

- [ ] **Improve stability report**
  - Add filtering by flakiness level (min_flaky_rate)
  - Control outcome pattern visibility (include_patterns)
  - Limit the number of returned tests (max_tests)

- [ ] **Upgrade performance report**
  - Add duration filtering (min_duration)
  - Include trend data visualization (include_trends)
  - Limit the number of returned tests (max_tests)

### Medium Priority
- [ ] **Create trend report**
  - Track metrics over time with customizable intervals (day/week/month)
  - Show duration trends, failure trends, pass rate trends, and test count trends
  - Identify patterns and changes in test behavior over time

- [ ] **Develop regression report**
  - Compare recent test runs to a baseline period
  - Identify new failures, fixed tests, performance regressions, and improvements
  - Provide an overall assessment of the test suite's direction

- [ ] **Add statistical analysis**
  - Implement significance testing for duration changes
  - Calculate confidence intervals for flakiness metrics
  - Provide trend analysis for test stability over time

## 3. Storage Profiles Integration

### High Priority
- [ ] **Integrate comparison with profiles**
  - Allow comparing data across different storage profiles
  - Support profile specification in comparison API
  - Handle profile switching during comparison operations

- [ ] **Add profile-aware analysis**
  - Make analysis components work with the active profile
  - Support specifying profile in analysis API calls
  - Ensure consistent behavior across different profiles

- [ ] **Support cross-profile operations**
  - Enable operations that span multiple profiles
  - Implement profile-to-profile data transfer
  - Create utilities for profile management in analysis workflows

## 4. Documentation and Testing

### High Priority
- [ ] **Create comparison API documentation**
  - Document all comparison methods with examples
  - Explain the relationship between comparison categories
  - Provide guidance on interpreting comparison results

- [ ] **Write comprehensive tests**
  - Create dedicated test files for comparison functionality
  - Test all comparison categories
  - Test edge cases (empty sessions, all tests changed, etc.)

- [ ] **Document profile integration**
  - Update documentation to reflect profile-aware operations
  - Add examples of using profiles with comparison and analysis
  - Document environment variable configuration for profiles

### Medium Priority
- [ ] **Add tutorial examples**
  - Create step-by-step examples for common use cases
  - Provide sample code for typical workflows
  - Include real-world scenarios and solutions

- [ ] **Document API relationships**
  - Explain how Query, Comparison, and Analysis components interact
  - Document the data flow between components
  - Provide diagrams of the architecture and component relationships

## 5. CLI and Integration

### Medium Priority
- [ ] **Enhance CLI commands**
  - Add commands for comparison operations
  - Implement profile management via CLI
  - Support generating reports from the command line

- [ ] **Improve CI/CD integration**
  - Make it easier to use pytest-insight in continuous integration
  - Add examples for popular CI systems
  - Create documentation for CI integration patterns

## Implementation Strategy

Given our recent work on storage profiles, we recommend the following approach:

1. First, ensure the storage profiles are fully integrated with the existing Query system
2. Then, focus on building the Comparison API with a similar fluent interface design
3. Enhance the Analysis API to work with both profiles and comparison results
4. Document each component as it's completed
5. Add comprehensive tests for all new functionality

This approach builds on our recent storage profiles work while addressing the most critical gaps in the pytest-insight functionality.
