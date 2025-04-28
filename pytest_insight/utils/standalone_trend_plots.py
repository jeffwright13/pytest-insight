import json
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt

# 1) Load & flatten
json_path = Path("/Users/jwr003/.pytest_insight/practice.json")
with open(json_path) as f:
    raw = json.load(f)

records = []
for sess in raw["sessions"]:
    for t in sess["test_results"]:
        records.append({
            "time": pd.to_datetime(t["start_time"]),
            "test":  t["nodeid"],
            "outcome": t["outcome"],
            "duration": t["duration"],
        })
df = pd.DataFrame(records)

# 2) Trend plot: daily pass rate + 7-day rolling, with IQR outliers
daily = (df.set_index("time")
           .groupby(pd.Grouper(freq="D"))["outcome"]
           .apply(lambda x: (x=="passed").mean()))
rolling7 = daily.rolling(7).mean()

q1, q3 = daily.quantile(0.25), daily.quantile(0.75)
iqr = q3 - q1
outliers = daily[(daily < q1 - 1.5*iqr) | (daily > q3 + 1.5*iqr)]

fig, ax = plt.subplots()
ax.plot(daily.index, daily, label="Daily Pass Rate")
ax.plot(rolling7.index, rolling7, label="7-Day Rolling Avg")
ax.scatter(outliers.index, outliers.values, marker="x", s=100, label="IQR Outliers")
ax.set_title("Daily Pass Rate Trend")
ax.set_xlabel("Date")
ax.set_ylabel("Pass Rate")
ax.legend()
plt.show()

# 3) Test-level metrics + manual “clusters”
metrics = (df.groupby("test")
             .agg(total_runs=("outcome","size"),
                  pass_rate=("outcome", lambda x: (x=="passed").mean()),
                  avg_dur=("duration","mean"))
             .reset_index())

# Define clusters by simple thresholds
dur75 = metrics["avg_dur"].quantile(0.75)
def assign_cluster(r):
    if r["pass_rate"] < 0.80:          return "low-stability"
    if r["avg_dur"] > dur75:           return "slow"
    return "stable-fast"

metrics["cluster"] = metrics.apply(assign_cluster, axis=1)

# Anomaly via IQR on both dimensions
def iqr_flag(s):
    q1, q3 = s.quantile([0.25,0.75])
    iqr = q3 - q1
    return (s < q1 - 1.5*iqr) | (s > q3 + 1.5*iqr)

metrics["anomaly"] = iqr_flag(metrics["pass_rate"]) | iqr_flag(metrics["avg_dur"])

# 4) Scatter plot
markers = {"stable-fast":"o", "slow":"s", "low-stability":"^"}
fig2, ax2 = plt.subplots()
for cl, m in markers.items():
    sub = metrics[metrics["cluster"]==cl]
    ax2.scatter(sub["avg_dur"], sub["pass_rate"], marker=m, label=cl)
anom = metrics[metrics["anomaly"]]
ax2.scatter(anom["avg_dur"], anom["pass_rate"], marker="x", s=100, label="Anomaly")
ax2.set_title("Test Clusters & Anomalies")
ax2.set_xlabel("Avg. Duration (s)")
ax2.set_ylabel("Pass Rate")
ax2.legend()
plt.show()
