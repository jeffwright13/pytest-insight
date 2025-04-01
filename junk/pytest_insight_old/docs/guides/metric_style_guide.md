# pytest-insight Metric Style Guide

## Overview
This guide defines the naming conventions and structure for pytest-insight metrics.

## Metric Path Structure
```
<entity>.<category>.<metric>
```

### Components
- **entity**: Primary object being measured (always singular)
- **category**: Measurement grouping (singular for states, plural for collections)
- **metric**: Specific measurement (past tense for outcomes)

## Standard Entities
```
test/     # Individual test measurements
session/  # Session-level aggregates
rerun/    # Rerun-specific metrics
```

## Categories and Metrics

### Test Outcome
```
test.outcome/            # Singular, represents single test state
├── passed              # Past tense, matching pytest reporting
├── failed              # Test did not pass
├── skipped             # Test was not run
├── xfailed             # Expected failure occurred
├── xpassed             # Unexpected pass
├── rerun              # Test was rerun
└── error              # Test execution error
```

### Test Duration
```
test.duration/          # Singular, represents time measurement
├── elapsed            # Past tense, completed measurement
├── trend              # Present tense, ongoing pattern
├── average            # Statistical aggregation
├── maximum            # Peak value observed
└── minimum            # Lowest value observed
```

### Test Warning
```
test.warning/          # Singular, represents warning state
├── occurred          # Past tense, warning happened
├── count             # Quantity measurement
└── message          # Content descriptor
```

### Test Pattern
```
test.pattern/          # Singular, represents behavior pattern
├── slowed            # Past tense, performance degraded
├── fluctuated        # Past tense, showed variance
├── failed_often      # Past tense, compound descriptor
├── recovered         # Past tense, improved after failure
└── flaked           # Past tense, showed inconsistency
```

### Session Metric
```
session.metric/       # Singular, represents session measurements
├── started          # Past tense, session began
├── completed        # Past tense, session finished
├── duration         # Time measurement
├── count            # Quantity of sessions
└── tagged          # Session metadata present
```

### SUT Metrics
```
sut.metric/               # System Under Test measurements
├── count                # Number of SUTs
├── latest              # Most recent SUT data
└── active              # Currently running tests
```

### Rerun Metrics
```
rerun.metric/            # Rerun-specific measurements
├── attempted           # Past tense, rerun was tried
├── succeeded          # Past tense, rerun passed
├── count              # Number of reruns
└── recovered          # Test passed after rerun
```

### History Metrics
```
history.metric/          # Historical trend measurements
├── collected           # Past tense, data gathered
├── duration            # Time span of history
├── trend               # Pattern over time
└── compared            # Past tense, comparison made
```

### Group Metrics
```
group.metric/           # Test grouping measurements
├── formed             # Past tense, group created
├── size               # Number of tests in group
├── duration           # Group execution time
└── pattern            # Group behavior pattern
```

## Implementation Examples

### Time Series Data Format
```python
{
    "target": "<entity>.<category>.<metric>",
    "datapoints": [
        [value, timestamp_in_ms]
    ]
}
```

### FastAPI Implementation
```python
@app.get("/search")
async def search():
    """Return all available metrics following style guide."""
    return [
        # Test Outcomes
        "test.outcome.passed",
        "test.outcome.failed",

        # Test Duration
        "test.duration.elapsed",
        "test.duration.trend",

        # Test Warning
        "test.warning.occurred",
        "test.warning.count",

        # Test Pattern
        "test.pattern.slowed",
        "test.pattern.flaked",

        # Session Metric
        "session.metric.started",
        "session.metric.count",

        # SUT Metrics
        "sut.metric.count",
        "sut.metric.latest",

        # Rerun Metrics
        "rerun.metric.attempted",
        "rerun.metric.succeeded",

        # History Metrics
        "history.metric.collected",
        "history.metric.trend",

        # Group Metrics
        "group.metric.formed",
        "group.metric.size"
    ]
```

## Style Rules

### Correct Usage
```python
"test.outcome.passed"      # Singular entity and category
"test.duration.elapsed"    # Past tense for completed measurement
"test.warning.occurred"    # Past tense for event
"test.pattern.slowed"      # Past tense for observed pattern
"session.metric.started"   # Past tense for event
```

### Incorrect Usage
```python
"tests.outcomes.pass"      # Plural entity and category
"test_duration_trend"      # Wrong separator
"test.warnings.total"      # Plural category
"test.patterns.slow"       # Wrong tense, plural category
"sessionMetricCount"       # Wrong casing and structure
```

## Implementation Guidelines
1. Use consistent separators (dots)
2. Use lowercase throughout
3. Follow hierarchy strictly
4. Use past tense for completed states
5. Use present tense for ongoing measurements
6. Use adjectives for patterns
7. Use underscores for compound metrics
```
