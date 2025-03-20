Pattern Matching in pytest-insight
pytest-insight provides powerful pattern matching capabilities to filter test results based on specific criteria. Here's a detailed guide on how to use these features effectively.

1. Shell Pattern Matching (Substring)
Usage: Matches simple substrings within a specified field.
Example:
```python
query.filter_by_test().with_pattern("get", field_name="nodeid").apply()
```
This will match any test with "get" in its nodeid.
2. Regex Pattern Matching
Usage: Utilizes regular expressions for more complex pattern matching.
Example:
```python
query.filter_by_test().with_pattern("test_.*", field_name="nodeid", use_regex=True).apply()
```
This matches any nodeid that starts with "test_" followed by any characters.
3. Combining Patterns
Usage: Combine multiple patterns using logical operators like | for OR.
Example:
```python
query.filter_by_test().with_pattern("get|query", field_name="nodeid", use_regex=True).apply()
```
This matches any nodeid containing either "get" or "query".
4. Field Name Validation
Ensure that the field_name is a valid attribute of the test result, such as nodeid, caplog, capstdout, etc.
Invalid field names will raise an InvalidQueryParameterError.
Best Practices
Use Substring Matching for Simplicity: When possible, use simple substring matching for efficiency.
Leverage Regex for Complex Patterns: Use regex when you need to match complex patterns or multiple criteria.
Validate Field Names: Always ensure the field name is valid to avoid errors.
