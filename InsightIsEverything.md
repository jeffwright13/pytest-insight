if you treat everything as an “Insight,” and make the InsightAPI the single, unified entry point, you can present a spectrum of insights spanning from the most granular (single session/test) to the most abstract (trends, comparisons, predictions). This would make the system more discoverable, less deterministic, and more user-intuitive, while still retaining the composability you love in the Query system.

High-Level Redesign Proposal: “Everything is an Insight”
1. InsightAPI as the Sole Entry Point
•	All analytics, queries, comparisons, and reports are accessed via InsightAPI.
•	The API exposes a set of “insight types” or “lenses” (e.g., Session, Test, Temporal, Comparative, Trend, Predictive).
2. Insight Types / Lenses
•	Each insight type corresponds to a way of looking at the data:
•	Session Insight: Metrics and health for a single session or group of sessions.
•	Test Insight: Focus on individual tests, their flakiness, reliability, etc.
•	Temporal Insight: How things change over time (trends, regressions, improvements).
•	Comparative Insight: Compare across SUTs, code versions, environments, etc.
•	Trend Insight: Detect and highlight emerging patterns.
•	Predictive Insight: Machine learning-driven forecasts or anomaly detection.
•	Meta Insight: Insights about the test process itself (e.g., maintenance burden, stability over time).
3. Fluent, Composable API
•	Users can compose queries and then “ask for” a particular insight:
```python
api = InsightAPI(profile="myprofile")
api.session("2025-04-16").insight("health")
api.tests().filter(name="test_login").insight("flakiness")
api.sut("serviceA").over_time(days=30).insight("trend")
api.compare(sut="A", sut="B").insight("regression")
```
4. Discoverable, Extensible, Intuitive
•	All capabilities are discoverable from the single API.
•	New insight types can be added as new “lenses” or methods.
•	The user doesn’t have to know up front if they want “analysis,” “comparison,” or “trend”—they just ask for an insight on the data they care about.
•	We do not use the word "flaky" because that is reserved for the pytet-rerunfailures plugin. Instead we use the related words "reliable", "unreliable", "reliability", etc.
