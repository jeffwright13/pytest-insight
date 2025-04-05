I've expanded the API with several new canned reports and enhanced the parametrization of existing endpoints. Here's a summary of the improvements:

Enhanced Existing Endpoints
Health Report (/api/analysis/health)
Added include_trends parameter to optionally exclude trend data
Added include_recommendations parameter to control recommendation visibility
Added min_score_threshold parameter to only return reports below a certain health score
Stability Report (/api/analysis/stability)
Added min_flaky_rate parameter to filter tests by flakiness level
Added max_tests parameter to limit the number of returned tests
Added include_patterns parameter to control outcome pattern visibility
Performance Report (/api/analysis/performance)
Added min_duration parameter to filter by test duration
Added max_tests parameter to limit the number of returned tests
Added include_trends parameter to control trend data visibility
Comparison Endpoint (/api/compare)
Added include_tests parameter to control detailed test result visibility
Added min_duration_change parameter to filter performance changes by significance
Added include_metrics parameter to include high-level metric comparisons
New Canned Reports
Trend Report (/api/analysis/trends)
Tracks metrics over time with customizable intervals (day/week/month)
Shows duration trends, failure trends, pass rate trends, and test count trends
Helps identify patterns and changes in test behavior over time
Coverage Report (/api/analysis/coverage)
Analyzes test distribution across modules, packages, or directories
Shows coverage by test markers
Identifies potentially uncovered areas in the codebase
Regression Report (/api/analysis/regression)
Compares recent test runs to a baseline period
Identifies new failures, fixed tests, performance regressions, and improvements
Provides an overall assessment of the test suite's direction
Quality Report (/api/analysis/quality)
Evaluates the test suite design and organization
Analyzes test distribution, complexity, and isolation
Provides a quality score and actionable recommendations for improvement
These new endpoints provide a comprehensive set of "80/20" reports that cover the most common test analysis needs while still allowing for parametrization to customize the results. The enhanced parametrization gives users more control over the data they receive without requiring them to build complex queries.

Would you like me to explain any of these reports in more detail or add any additional canned reports?
