# pytest-insight Consistency Guide

This guide documents the principles, terminology, and interface standards that ensure a unified and professional user experience across all of pytest-insight's interfaces.

## Why Consistency Matters
Consistency across CLI, dashboard, API, terminal output, and reports builds user trust, reduces cognitive load, and makes insights actionable regardless of entry point. Every user should see the same core metrics and terminology, whether in a console, web UI, or exported report.

---

## Core Principles
- **One Engine, Many Views:** All interfaces are powered by the same backend logic and data structures.
- **Consistent Terminology:** The same words mean the same things everywhere.
- **Core Metrics Everywhere:** Every interface displays the same essential insights, with richer interfaces offering more detail or interactivity.
- **Actionability:** Every summary or report highlights what the user should do next.
- **Progressive Disclosure:** Start with a summary, allow deeper drilldown in richer interfaces.

---

## Always-Show Core Metrics & Insights

```
| Section             | Shown In All? | Console Output | Dashboard/HTML | API/Swagger | Notes                       |
|---------------------|--------------|---------------|---------------|-------------|-----------------------------|
| Last Session        | Yes          | Table         | Pie, Table    | JSON        | Always summary, more detail |
| All Sessions        | Yes          | Table         | Timeline      | JSON        | Trend/sparkline if possible |
| Outcome Breakdown   | Yes          | Table         | Pie/Stacked   | JSON        | Per session & aggregate     |
| Rerun Info          | Yes          | Table         | Bar/Timeline  | JSON        | Reruns, success rates       |
| Health Summary      | Yes          | Badge/Text    | Badge/Chart   | JSON        | A–F or 0–100                |
| Actionable Items    | Yes          | List          | Cards/List    | JSON        | Top 1–3 recommendations     |
```

---

## Interface Roles & Consistency Table

```
| Interface       | Role                            | Core Metrics? | Extra Detail?    | User/Integration Entry   |
|-----------------|---------------------------------|--------------|------------------|-------------------------|
| CLI             | Command center, automation      | Yes          | Subcommands      | Terminal, scripts       |
| API/Swagger     | Universal backend, integration  | Yes          | All endpoints    | Swagger UI, HTTP        |
| Dashboard       | Visual, interactive exploration | Yes          | Tabs, charts     | Browser                 |
| Terminal Output | Immediate feedback post-test    | Yes          | No               | pytest run              |
| HTML Report     | Archival/sharing                | Yes          | Graphs, tables   | File                    |
```

---

## Terminology Guidance (from Metric Style Guide)

- **System Under Test (SUT):** Always use "SUT" to refer to the entity being tested. Avoid "project" or "suite" unless context requires.
- **Profile:** Use "profile" or "storage profile" for configuration contexts. Be consistent.
- **Test Session:** Prefer "session" for a single test run. Avoid mixing with "run" or "execution" unless clarifying.
- **Health Metric:** Use specific terms ("health", "stability", "reliability", "repeatability") for metrics. Use "metric" only when referring generically.
- **Impact:** Use "impact" or "criticality" consistently. If both are needed, define each clearly.
- **Analysis/Insight:** Use "insight" for actionable findings, "analysis" for the process, and "report" for the output artifact.
- **Tag/Label:** Use "tag" for user-defined labels, "marker" only in pytest context.
- **Unreliable:** In pytest-insight, "unreliable" is used to refer to tests with low reliability or repeatability.
    - **Reliability**: The rate at which a test passes on its first attempt.
    - **Repeatability**: The consistency of test outcomes across multiple runs.
    - **Unstable Test**: A test with low reliability or repeatability.

*We avoid using "flaky" as a generic label or metric to ensure clarity and alignment with the broader pytest ecosystem.*

*See docs/10_METRIC_STYLE_GUIDE.md for further details and examples.*

---

## Key Terminology Changes:

- Flaky → Unreliable
- Flakiness → Reliability
- Flaky Tests → Unreliable Tests

**Metrics and Visualizations:**

- Flaky Rate → Reliability Rate
- Flakiness Delta → Reliability Delta
- Most Flaky → Most Unreliable

**API and CLI:**

- All API endpoints, method names, and CLI commands now use the new terminology.

**Testing and Recommendations:**

- Test assertions and recommendations updated to reference unreliable tests and reliability.

**Documentation:**

- All documentation, guides, and tooltips now reflect the new terminology.

---

## Unreliable Test Example

If a test is unreliable, it may pass or fail inconsistently across runs.

Old: `flaky_tests = analysis.identify_flaky_tests()`
New: `unreliable_tests = analysis.identify_unreliable_tests()`

Old: `print(f"Found {len(flaky_tests)} flaky tests")`
New: `print(f"Found {len(unreliable_tests)} unreliable tests")`

---

## Implementation Checklist
- [ ] All interfaces show the core metrics in their summary views
- [ ] Terminology is consistent in code, docs, and UI
- [ ] API/CLI/dashboard all use the same backend logic for metrics/insights
- [ ] Console/terminal output is concise but matches dashboard/report in content
- [ ] Richer interfaces (dashboard, HTML) offer drilldown/detail, not different core data

---

## Feedback & Evolution
This document should evolve with the project. Contributors: please update this guide whenever you add a new interface, metric, or terminology.

---

*Last updated: 2025-04-14*
