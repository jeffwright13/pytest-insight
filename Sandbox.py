"""
Sandbox: End-to-end walkthrough for generating, loading, and analyzing historical test data with pytest-insight.

This script demonstrates:
- Generating synthetic historical data (JSON profile)
- Loading the data into InsightAPI
- Running all major insight facets (summary, trends, comparisons, predictive, meta, etc.)
- Printing results for exploration

Run this file as a standalone script.
"""

from pathlib import Path
from pprint import pprint

from pytest_insight.insight_api import InsightAPI
from pytest_insight.utils.history_generator import HistoryDataGenerator

# 1. Generate synthetic historical data and save as a profile (JSON)
profile_path = Path("practice_profile.json")
generator = HistoryDataGenerator(days=30, sessions_per_day=5, trend_strength=0.8, anomaly_rate=0.1, correlation_groups=4)
sessions = generator.generate()
generator.save_profile(sessions, profile_path)
print(f"Generated {len(sessions)} sessions and saved to {profile_path}")

# 2. Load the generated data into InsightAPI
#    (Assume InsightAPI can take a list of TestSession objects directly)
api = InsightAPI(sessions=sessions)

# 3. Run all major insight facets and print results
print("\n=== SUMMARY INSIGHT ===\n# Aggregate stats: total sessions, tests, reliability, outcomes")
pprint(api.summary().aggregate_stats())

print("\n# Suite-level metrics: average session duration")
pprint(api.summary().suite_level_metrics())

print("\n=== SESSION INSIGHT ===\n# Per-session health metrics")
pprint(api.session().insight("health"))

print("\n=== TEST INSIGHT ===\n# Per-test reliability report")
pprint(api.test().insight("reliability"))

print("\n=== TEMPORAL INSIGHT ===\n# Time series of reliability (by day)")
pprint(api.temporal().trend_over_time())

print("\n=== COMPARATIVE INSIGHT ===\n# Compare reliability between SUTs")
pprint(api.comparative().compare_suts("api-service", "ui-service"))

print("\n=== TREND INSIGHT ===\n# Detect emerging patterns (e.g., long failures)")
pprint(api.trend().emerging_patterns())

print("\n=== PREDICTIVE INSIGHT ===\n# Forecast future reliability (stub)")
pprint(api.predictive().forecast())

print("\n=== META INSIGHT ===\n# Test process maintenance burden")
pprint(api.meta().maintenance_burden())

print("\n=== FLUENT INSIGHT API DEMO ===\n")

print("Session-level filter, then get a health insight:")
pprint(api.session().for_sut("api-service").in_last_days(7).insight("health"))

print("Test-level filter, then get reliability insight:")
pprint(api.test().with_name("test_login").with_duration(10.0, float("inf")).insight("reliability"))

print("Chain test-level filter, then return to session context and get summary:")
pprint(api.session().filter_by_test().with_duration(5, 20).apply().insight("summary"))
pass
# 4. (Optional) Advanced: Filter, compare, or chain queries as needed
# Example (uncomment to try):
# filtered_sessions = api.test().filter_by_test().with_duration(10.0, float("inf")).apply().execute()
# pprint(filtered_sessions)
