# Pytest-Insight: Analytics & Insight Classes

This document enumerates the core Insight classes provided by `pytest-insight`, describing their purpose, available analytics, and example usage. Use this as a reference for surfacing actionable patterns and trends in your test results.

---

## 1. SummaryInsight
**Purpose:** Aggregate statistics and suite-level metrics.

**Available Insights:**
- `summary` (default): Total sessions, total tests, pass/fail rate, reliability, outcome counts.
- `aggregate_stats()`: Detailed outcome counts and percentages.
- `suite_level_metrics()`: Average session duration.

**Example Usage:**
```python
SummaryInsight(sessions).insight(kind="summary")
SummaryInsight(sessions).aggregate_stats()
SummaryInsight(sessions).suite_level_metrics()
```

---

## 2. SessionInsight
**Purpose:** Session-level analytics and metrics.

**Available Insights:**
- `health` / `summary`: Delegates to SummaryInsight.
- `metrics`: Per-session metrics (reliability, outcome counts, avg duration, etc.).
- `key_metrics`: Distribution of reliability, suspicious sessions, top unreliable sessions.

**Example Usage:**
```python
SessionInsight(sessions).insight(kind="health")
SessionInsight(sessions).insight(kind="metrics")
SessionInsight(sessions).insight(kind="key_metrics")
```

---

## 3. TestInsight
**Purpose:** Metrics focused on individual tests.

**Available Insights:**
- `reliability`: Reliability report per test nodeid.
- `detailed`: Test-level reliability, slowest tests, unreliable tests.
- `filter`: Filter sessions by nodeid, outcome, min/max duration, etc.

**Example Usage:**
```python
TestInsight(sessions).insight(kind="reliability")
TestInsight(sessions).insight(kind="detailed")
TestInsight(sessions).filter(nodeid="test_login").insight(kind="reliability")
```

---

## 4. TrendInsight
**Purpose:** Detect and highlight emerging patterns and trends.

**Available Insights:**
- `trend`: Duration and failure trends by day.
- `emerging_patterns`: Sudden increases in failures, slowdowns, correlated issues.
- `filter`: Filter by SUT or nodeid.

**Example Usage:**
```python
TrendInsight(sessions).insight(kind="trend")
TrendInsight(sessions).emerging_patterns()
TrendInsight(sessions).filter(sut="myservice").insight(kind="trend")
```

---

## 5. PredictiveInsight
**Purpose:** Predictive analytics and future reliability.

**Available Insights:**
- `predictive_failure`: Forecasts future reliability, trend, and warnings.

**Example Usage:**
```python
PredictiveInsight(sessions).insight(kind="predictive_failure")
```

---

## 6. ComparativeInsight
**Purpose:** Compare across SUTs, versions, etc.

**Available Insights:**
- `regression`: Reliability comparison between SUTs.

**Example Usage:**
```python
ComparativeInsight(sessions).insight(kind="regression")
ComparativeInsight(sessions).compare_suts("SUT_A", "SUT_B")
```

---

## 7. TemporalInsight
**Purpose:** How things change over time.

**Available Insights:**
- `trend`: Time series of reliability (or other metric) grouped by interval.

**Example Usage:**
```python
TemporalInsight(sessions).insight(kind="trend")
TemporalInsight(sessions).trend_over_time(metric="reliability", interval="day")
```

---

## 8. MetaInsight
**Purpose:** Insights about the test process itself (maintenance burden, stability).

**Available Insights:**
- `meta`: Unique tests, total sessions, tests per session.

**Example Usage:**
```python
MetaInsight(sessions).insight(kind="meta")
MetaInsight(sessions).maintenance_burden()
```

---

## Notes
- All Insight classes expect a list of `TestSession` objects as input (`sessions`).
- These APIs can be used directly in Python, or via CLI/dashboard integrations.
- Rendering functions (e.g., `render_summary`, `render_test`) call these APIs for terminal output.
