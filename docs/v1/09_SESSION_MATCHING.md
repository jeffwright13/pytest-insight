# Implementing Reliable Session Matching in pytest-insight

## Current Challenge

Currently, the comparison functionality in pytest-insight relies primarily on session ID patterns to match test runs across different versions or environments. This approach has limitations:

1. It assumes a predictable naming convention for session IDs
2. It doesn't handle cases where test names change between versions
3. It lacks flexibility for different comparison scenarios

## Proposed Solution

The "Implement reliable session matching" task involves creating a more robust system for identifying corresponding test sessions across different runs. Here's what this would entail:

### Core Components

1. **Multiple Matching Strategies**:
   - **Timestamp-based matching**: Pair sessions that ran at similar times
   - **Metadata-based matching**: Use test metadata like git commit, version tags, or custom markers
   - **Content-based matching**: Compare test names and structures to find corresponding tests
   - **Explicit mapping**: Allow users to explicitly define which sessions to compare

2. **Smart Test Identification**:
   - Detect renamed tests by analyzing similarities in test paths and parameters
   - Track tests across versions using unique identifiers that persist despite name changes
   - Use fuzzy matching algorithms to handle minor changes in test names or paths

3. **Configurable Matching Rules**:
   - Allow users to define custom rules for session matching
   - Provide confidence scores for matches to indicate reliability
   - Support fallback strategies when primary matching methods fail

## Implementation Approach

1. **Create a SessionMatcher interface**:
   ```python
   class SessionMatcher:
       def find_matching_sessions(self, base_sessions, target_sessions, **criteria):
           """Find matching sessions between base and target collections."""
           pass
   ```

2. **Implement specific matchers**:
   ```python
   class TimestampMatcher(SessionMatcher):
       def __init__(self, max_time_difference=timedelta(hours=1)):
           self.max_time_difference = max_time_difference

       def find_matching_sessions(self, base_sessions, target_sessions, **criteria):
           # Match sessions based on timestamp proximity
           pass

   class MetadataMatcher(SessionMatcher):
       def find_matching_sessions(self, base_sessions, target_sessions, **criteria):
           # Match sessions based on metadata like version, git commit, etc.
           pass
   ```

3. **Create a composite matcher**:
   ```python
   class CompositeSessionMatcher(SessionMatcher):
       def __init__(self, matchers, strategy="best_match"):
           self.matchers = matchers
           self.strategy = strategy

       def find_matching_sessions(self, base_sessions, target_sessions, **criteria):
           # Use multiple matchers and combine results based on strategy
           pass
   ```

## Integration with Storage Profiles

This feature would integrate well with our new storage profiles system:

```python
# Compare sessions across different profiles
from pytest_insight.core.comparison import Comparison

comparison = Comparison()
result = comparison.between_profiles("production", "development")
                  .with_matcher(TimestampMatcher())
                  .execute()
```

## Benefits

1. **More accurate comparisons**: Better matching leads to more meaningful comparisons
2. **Flexibility**: Support for different matching strategies accommodates various use cases
3. **Robustness**: Handles edge cases like renamed tests or structural changes
4. **User control**: Allows users to customize matching behavior for their specific needs

## Detailed Implementation Specifications

### Matching Strategies

#### Timestamp-based Matching

This strategy matches sessions based on when they were executed:

```python
class TimestampMatcher(SessionMatcher):
    def __init__(self, max_time_difference=timedelta(hours=1)):
        self.max_time_difference = max_time_difference

    def find_matching_sessions(self, base_sessions, target_sessions, **criteria):
        matches = []
        for base_session in base_sessions:
            best_match = None
            min_diff = self.max_time_difference

            for target_session in target_sessions:
                time_diff = abs(base_session.timestamp - target_session.timestamp)
                if time_diff < min_diff:
                    min_diff = time_diff
                    best_match = target_session

            if best_match:
                matches.append((base_session, best_match, 1.0 - (min_diff / self.max_time_difference)))

        return matches
```

#### Metadata-based Matching

This strategy uses session metadata to find matches:

```python
class MetadataMatcher(SessionMatcher):
    def __init__(self, metadata_keys=None):
        self.metadata_keys = metadata_keys or ["version", "git_commit", "environment"]

    def find_matching_sessions(self, base_sessions, target_sessions, **criteria):
        matches = []
        for base_session in base_sessions:
            for target_session in target_sessions:
                score = self._calculate_metadata_similarity(base_session, target_session)
                if score > 0.7:  # Configurable threshold
                    matches.append((base_session, target_session, score))

        return matches

    def _calculate_metadata_similarity(self, session1, session2):
        # Calculate similarity score based on metadata
        # Returns a value between 0.0 and 1.0
        pass
```

#### Content-based Matching

This strategy analyzes the actual test content:

```python
class ContentMatcher(SessionMatcher):
    def find_matching_sessions(self, base_sessions, target_sessions, **criteria):
        matches = []
        for base_session in base_sessions:
            for target_session in target_sessions:
                score = self._calculate_content_similarity(base_session, target_session)
                if score > 0.8:  # Configurable threshold
                    matches.append((base_session, target_session, score))

        return matches

    def _calculate_content_similarity(self, session1, session2):
        # Compare test names, counts, and structures
        # Returns a value between 0.0 and 1.0
        pass
```

### Composite Matching

The composite matcher combines results from multiple strategies:

```python
class CompositeSessionMatcher(SessionMatcher):
    def __init__(self, matchers, strategy="weighted"):
        self.matchers = matchers
        self.strategy = strategy
        self.weights = {
            "timestamp": 0.3,
            "metadata": 0.5,
            "content": 0.2
        }

    def find_matching_sessions(self, base_sessions, target_sessions, **criteria):
        all_matches = {}

        # Collect matches from all matchers
        for matcher in self.matchers:
            matcher_name = matcher.__class__.__name__.lower().replace("matcher", "")
            matcher_matches = matcher.find_matching_sessions(base_sessions, target_sessions, **criteria)

            for base_session, target_session, score in matcher_matches:
                key = (base_session.id, target_session.id)
                if key not in all_matches:
                    all_matches[key] = {}
                all_matches[key][matcher_name] = score

        # Combine scores based on strategy
        final_matches = []
        for (base_id, target_id), scores in all_matches.items():
            base_session = next(s for s in base_sessions if s.id == base_id)
            target_session = next(s for s in target_sessions if s.id == target_id)

            if self.strategy == "weighted":
                final_score = sum(scores.get(name, 0) * weight
                                 for name, weight in self.weights.items()) / sum(
                                     weight for name, weight in self.weights.items()
                                     if name in scores)
            elif self.strategy == "best_match":
                final_score = max(scores.values())
            elif self.strategy == "average":
                final_score = sum(scores.values()) / len(scores)

            final_matches.append((base_session, target_session, final_score))

        return sorted(final_matches, key=lambda m: m[2], reverse=True)
```

### Test Identification Across Versions

To handle renamed tests, we need a way to identify the same test across different versions:

```python
class TestIdentifier:
    def __init__(self, fuzzy_matching=True, similarity_threshold=0.8):
        self.fuzzy_matching = fuzzy_matching
        self.similarity_threshold = similarity_threshold

    def find_matching_tests(self, base_tests, target_tests):
        matches = []
        for base_test in base_tests:
            best_match = None
            best_score = 0

            for target_test in target_tests:
                score = self._calculate_test_similarity(base_test, target_test)
                if score > best_score:
                    best_score = score
                    best_match = target_test

            if best_match and best_score >= self.similarity_threshold:
                matches.append((base_test, best_match, best_score))

        return matches

    def _calculate_test_similarity(self, test1, test2):
        # Calculate similarity between tests based on:
        # - Path similarity
        # - Function name similarity
        # - Parameter similarity
        # - Module similarity
        # Returns a value between 0.0 and 1.0
        pass
```

## API Design

The session matching functionality would be exposed through a clean, fluent API:

```python
from pytest_insight.core.comparison import Comparison, matchers

# Basic usage with default matcher
comparison = Comparison()
result = comparison.between_suts("service-v1", "service-v2").execute()

# Custom matcher configuration
timestamp_matcher = matchers.TimestampMatcher(max_time_difference=timedelta(minutes=30))
metadata_matcher = matchers.MetadataMatcher(metadata_keys=["version", "environment"])

result = comparison.between_suts("service-v1", "service-v2")
                  .with_matcher(matchers.CompositeMatcher([timestamp_matcher, metadata_matcher]))
                  .execute()

# Profile-based comparison
result = comparison.between_profiles("production", "staging")
                  .with_test_identifier(matchers.TestIdentifier(fuzzy_matching=True))
                  .execute()

# Explicit session mapping
result = comparison.between_sessions(base_session_id, target_session_id)
                  .execute()
```

## Integration with Existing Components

The session matching system would integrate with:

1. **Storage Profiles**: Allow comparing data across different storage profiles
2. **Query System**: Use query results as input for comparison
3. **Analysis API**: Feed comparison results into analysis for deeper insights

Example of integration with the query system:

```python
from pytest_insight import query, comparison

# Query for specific sessions
base_sessions = query.for_sut("service-v1").in_last_days(7).execute()
target_sessions = query.for_sut("service-v2").in_last_days(7).execute()

# Compare the query results
comp = comparison.Comparison()
result = comp.between_sessions(base_sessions, target_sessions)
              .with_default_matcher()
              .execute()

# Analyze the comparison results
analysis = result.analyze()
print(analysis.summary())
```

## Implementation Phases

1. **Phase 1**: Implement basic session matching interface and simple matchers
2. **Phase 2**: Add composite matching and confidence scoring
3. **Phase 3**: Implement test identification across versions
4. **Phase 4**: Integrate with storage profiles and query system
5. **Phase 5**: Add advanced matching strategies and user customization

This enhancement would significantly improve the reliability and usefulness of the comparison functionality in pytest-insight, making it a more powerful tool for analyzing test results across different environments and versions.
