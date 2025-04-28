"""
Sandbox: End-to-end walkthrough for generating, loading, and analyzing historical test data with pytest-insight.

This script demonstrates:
- Generating synthetic historical data (JSON profile)
- Loading the data into Insights (v2)
- Running all major insight facets (summary, tests, sessions, trends, etc.)
- Printing results for exploration

Run this file as a standalone script.
"""

import random
from collections import defaultdict
from pathlib import Path

from pytest_insight.core.insights import Insights
from pytest_insight.core.query import SessionQuery
from pytest_insight.core.storage import ProfileManager, get_storage_instance
from pytest_insight.facets.summary import SummaryInsight
from pytest_insight.utils.history_generator import HistoryDataGenerator

# 1. Generate synthetic historical data and save as a profile (JSON)
# profile_path = Path("practice_profile.json")
# generator = HistoryDataGenerator(
#     days=30, sessions_per_day=5, trend_strength=0.8, anomaly_rate=0.1, correlation_groups=4
# )
# sessions = generator.generate()
# generator.save_profile(sessions, profile_path)
# print(f"Generated {len(sessions)} sessions and saved to {profile_path}")

# Load sessions from a specific profile by name
storage = get_storage_instance(profile_name="default")
sessions = storage.load_sessions()

from pytest_insight.core.storage import switch_profile
switch_profile("default")

from pytest_insight.core.storage import get_profile_manager
pm = get_profile_manager()
active_name = pm.active_profile_name
active_profile = pm.get_active_profile()
print(f"Active profile: {active_name}")
print(f"Profile file path: {active_profile.file_path}")
print(f"Storage type: {active_profile.storage_type}")

# 2. Load the generated data into Insights (v2)
insights = Insights(sessions=sessions)

# === HIGHLIGHT ALL NEW ANALYTICS CONTENT ===
print("\n=== SUMMARY REPORT ===")
sumr = SummaryInsight(sessions).aggregate_stats()
print(f"Total Sessions: {sumr['total_sessions']}")
print(f"Total Tests: {sumr['total_tests']}")
print(f"Reliability: {sumr['reliability']:.2%}")

# Print outcome breakdown in a human-readable way
if 'outcome_counts' in sumr and 'outcome_percentages' in sumr:
    print("Outcome Breakdown:")
    print(f"{'Outcome':<10} | {'Count':>6} | {'Percent':>7}")
    print("-" * 30)
    for outcome, count in sumr['outcome_counts'].items():
        percent = sumr['outcome_percentages'][outcome]
        print(f"{outcome.capitalize():<10} | {count:>6} | {percent:>6.2f}%")

print("\n=== TEST INSIGHTS ===")
test_insights = insights.tests.key_insights()
metrics = test_insights["test_reliability_metrics"]
if not metrics:
    print("No test reliability data.")
else:
    # Use 'unreliable_rate' to compute reliability
    reliabilities = [1 - v["unreliable_rate"] for v in metrics.values() if v["runs"] > 0]
    avg_reliability = sum(reliabilities) / len(reliabilities) if reliabilities else 0.0
    print(f"Avg Test Reliability: {avg_reliability:.2%} across {len(metrics)} tests")
    slowest = test_insights["slowest_tests"]
    print("Top 5 slowest tests:")
    for nodeid, duration in slowest:
        print(f"  {nodeid}: {duration:.2f}s")

print("\n=== SESSION INSIGHTS ===")
session_metrics = insights.sessions.key_metrics()
for m in list(session_metrics.items())[:5]:
    print(f"{m[0]}: {m[1]}")
if len(session_metrics) > 5:
    print(f"...and {len(session_metrics)-5} more metrics.")

print("\n=== TREND INSIGHTS ===")
trend = insights.trends.key_trends()
for k, v in trend.items():
    print(f"{k}: {v}")

print("\n=== PREDICTIVE INSIGHTS ===")
try:
    predictive = getattr(insights, "predictive", None)
    if predictive:
        pred = predictive.insight()
        print(pred)
    else:
        print("Predictive analytics not available in orchestrator API.")
except Exception as e:
    print(f"Predictive analytics error: {e}")

print("\n=== META INSIGHTS ===")
try:
    meta = getattr(insights, "meta", None)
    if meta:
        meta_summary = meta.insight()
        print(meta_summary)
    else:
        print("Meta analytics not available in orchestrator API.")
except Exception as e:
    print(f"Meta analytics error: {e}")

# --- DEBUG: Failure and Duration Trends Root Cause ---
from collections import defaultdict

fail_by_day = defaultdict(int)
total_by_day = defaultdict(int)
dur_by_day = defaultdict(list)
for s in sessions:
    dt = getattr(s, "session_start_time", None)
    dur = getattr(s, "duration", None)
    for t in getattr(s, "test_results", []):
        if dt:
            total_by_day[str(dt.date())] += 1
            if getattr(t, "outcome", None) == "failed":
                fail_by_day[str(dt.date())] += 1
    if dt and dur:
        dur_by_day[str(dt.date())].append(dur)
print("[DEBUG] Failed tests by day:", dict(fail_by_day))
print("[DEBUG] Total tests by day:", dict(total_by_day))
print("[DEBUG] Sessions with duration by day:", {k: len(v) for k,v in dur_by_day.items()})
print("[DEBUG] Example durations:", {k: v[:3] for k,v in dur_by_day.items() if v})

# --- DEMO: Fluent Query API ---
print("\n=== DEMO: Fluent Query API ===")
# Example: Session-level filtering (exact)
sq = SessionQuery(sessions)
print()
sessions_last_week = SessionQuery(sessions).for_sut("auth-service").in_last_days(7).execute()
print(f"Sessions for SUT 'auth-service' (exact) in last 7 days: {len(sessions_last_week)}")

# Example: Session-level filtering (substring)
sessions_auth_any = SessionQuery(sessions).for_sut("auth", match_type="substring").execute()
print(f"Sessions for SUT containing 'auth': {len(sessions_auth_any)}")

# Example: Session-level filtering (regex)
sessions_regex = SessionQuery(sessions).for_sut(r"^auth.*", match_type="regex").execute()
print(f"Sessions for SUT matching regex '^auth.*': {len(sessions_regex)}")

# Example: Tag filtering (substring)
sessions_tagged = SessionQuery(sessions).with_tags({"env": "prod"}, match_type="substring").execute()
print(f"Sessions with tag env containing 'prod': {len(sessions_tagged)}")

# Example: Test-level filtering (preserves session context)
test_filtered = SessionQuery(sessions).filter_by_test().with_duration(10.0, float('inf')).apply().execute()
print(f"Sessions with tests >10s: {len(test_filtered)}")

# Show a few session IDs and their test counts for demonstration
for s in test_filtered[:3]:
    print(f"Session: {s.session_id} | SUT: {getattr(s, 'sut_name', '')} | Tests: {len(s.test_results)}")

# --- DEMO: Context-preserving filtering ---
if hasattr(sessions[0], 'sut_name'):
    suts = sorted(set(s.sut_name for s in sessions if hasattr(s, 'sut_name')))
    sut = random.choice(suts)
else:
    sut = None
if sut:
    print(f"\n[Context Demo] All sessions for SUT '{sut}' in last 7 days:")
    sut_sessions = SessionQuery(sessions).for_sut(sut).in_last_days(7).execute()
    for session in sut_sessions:
        print(f"Session {session.session_id}: {[t.nodeid for t in session.test_results]}")

    print(f"\n[Context Demo] Sessions with unreliable tests for SUT '{sut}':")
    sut_unreliable = SessionQuery(sessions).for_sut(sut).in_last_days(14).with_unreliable().execute()
    for session in sut_unreliable:
        failed = [t.nodeid for t in session.test_results if getattr(t, 'unreliable', False)]
        if failed:
            print(f"Session {session.session_id}: Unreliable: {failed}")

    print(f"\n[Context Demo] Sessions with reruns for SUT '{sut}':")
    sut_reruns = SessionQuery(sessions).for_sut(sut).in_last_days(14).with_reruns().execute()
    for session in sut_reruns:
        print(f"Session {session.session_id} had reruns: {len(session.rerun_test_groups)} groups")

print("\n[Context Demo] Test-level filter (duration > 10s) with session context:")
test_filtered_sessions = SessionQuery(sessions).filter_by_test().with_duration(10.0, float("inf")).apply().execute()
for session in test_filtered_sessions[:5]:
    slowtests = [t.nodeid for t in session.test_results if getattr(t, 'duration', 0) > 10.0]
    if slowtests:
        print(f"Session {session.session_id}: {slowtests}")
if len(test_filtered_sessions) > 5:
    print(f"...and {len(test_filtered_sessions)-5} more sessions.")

print("\n[Context Demo] Correlated failures (multiple failures in a session):")
for session in sessions[:10]:
    failed = [t.nodeid for t in session.test_results if getattr(t, "outcome", None) == "failed"]
    if len(failed) > 1:
        print(f"Session {session.session_id}: Correlated failures: {failed}")

print("\n[Context Demo] Performance trends (unreliable rate by day):")
by_day = defaultdict(lambda: {"unreliable": 0, "total": 0})
for s in sessions:
    dt = getattr(s, "session_start_time", None)
    for t in getattr(s, "test_results", []):
        if dt:
            by_day[str(dt.date())]["total"] += 1
            if getattr(t, "unreliable", False):
                by_day[str(dt.date())]["unreliable"] += 1
trend = {d: v["unreliable"] / v["total"] if v["total"] else 0.0 for d, v in by_day.items()}
for d, v in sorted(trend.items()):
    print(f"{d}: {v:.2%}")

# --- End of Sandbox ---
