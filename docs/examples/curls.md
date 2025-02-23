# pytest-insight API Examples

## Health and Status Checks
```bash
# Basic health check
curl http://localhost:8000/health

# Root endpoint test
curl http://localhost:8000/
```

## Test Outcome Metrics
```bash
# Get passed tests
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"target": "test.outcome.passed"}'

# Get failed tests
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"target": "test.outcome.failed"}'

# Get skipped tests
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"target": "test.outcome.skipped"}'

# Get xfailed tests
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"target": "test.outcome.xfailed"}'

# Get xpassed tests
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"target": "test.outcome.xpassed"}'

# Get rerun tests
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"target": "test.outcome.rerun"}'

# Get error tests
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"target": "test.outcome.error"}'
```

## Test Duration Metrics
```bash
# Get elapsed duration
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"target": "test.duration.elapsed"}'

# Get duration trends
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"target": "test.duration.trend"}'

# Get average durations
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"target": "test.duration.average"}'

# Get maximum durations
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"target": "test.duration.maximum"}'

# Get minimum durations
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"target": "test.duration.minimum"}'
```

## Warning Metrics
```bash
# Get warning occurrences
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"target": "test.warning.occurred"}'

# Get warning counts
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"target": "test.warning.count"}'

# Get warning messages
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"target": "test.warning.message"}'
```

## Pattern Metrics
```bash
# Get slowed tests
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"target": "test.pattern.slowed"}'

# Get fluctuating tests
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"target": "test.pattern.fluctuated"}'

# Get frequently failing tests
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"target": "test.pattern.failed_often"}'

# Get recovered tests
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"target": "test.pattern.recovered"}'

# Get flaky tests
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"target": "test.pattern.flaked"}'
```

## Session Metrics
```bash
# Get session starts
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"target": "session.metric.started"}'

# Get session completions
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"target": "session.metric.completed"}'

# Get session durations
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"target": "session.metric.duration"}'

# Get session counts
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"target": "session.metric.count"}'

# Get tagged sessions
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"target": "session.metric.tagged"}'
```

## Using Filters
```bash
# Filter by SUT and time window
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "target": "test.outcome.failed",
    "filters": {
      "sut": "my-service",
      "days": 7,
      "has_warnings": true
    }
  }'

# Filter by test name pattern
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "target": "test.duration.trend",
    "filters": {
      "days": 30,
      "nodeid_contains": "api"
    }
  }'
```

## List Available Metrics
```bash
# Get complete metric list
curl http://localhost:8000/search
```
