# 🚦 Project Status: On Hiatus (as of 2025-05-02)

**This project is currently paused.**

- The codebase is in an exploratory, partially complete state.
- Many features are present, but some are unfinished or experimental.
- This document and others in `/docs/v1/` have been updated for future contributors.

## 🧭 Guide for Future Contributors / Maintainers

**If you're picking this up for the first time:**

1. **Read this file fully.**
2. **Review the following in order:**
   - [01_CONCEPTUAL_FRAMEWORK.md](./01_CONCEPTUAL_FRAMEWORK.md): Design philosophy and layers
   - [02_ARCHITECTURE_OVERVIEW.md](./02_ARCHITECTURE_OVERVIEW.md): Technical architecture
   - [03_STORAGE.md](./03_STORAGE.md): Storage/profile system
   - [04_CLI_GUIDE.md](./04_CLI_GUIDE.md): CLI usage

**Project Highlights:**
- Fluent, chainable API for querying, comparing, and analyzing pytest data
- Storage profile system for flexible data management (see `core/storage.py`)
- Interactive CLI and Streamlit dashboard
- Predictive analytics and advanced test health metrics

**What’s Incomplete or Experimental:**
- Some analysis and insights features are stubs or prototypes
- REST API is not fully unified with Python API (see `/web_api`)
- Dashboard is functional but not fully polished
- Some advanced metrics and federated analysis are planned but not implemented

## 📌 State of the Project / Next Steps

- Most architectural decisions are documented in [01_CONCEPTUAL_FRAMEWORK.md](./01_CONCEPTUAL_FRAMEWORK.md) and [02_ARCHITECTURE_OVERVIEW.md](./02_ARCHITECTURE_OVERVIEW.md).
- Open questions and roadmap ideas are at the end of major docs.
- See `README.md` in the project root for a quick summary and contact info.

**Contact:**
- Original author: jwr003
- Last update: 2025-05-02

---

# pytest-insight Documentation

This is the documentation for pytest-insight, a pytest plugin for collecting, analyzing, and visualizing test and test-session metrics.

## Documentation Reading Guide

For the best understanding of pytest-insight, we recommend reading the documentation in the following order:

### Core Concepts

1. [Conceptual Framework](./01_CONCEPTUAL_FRAMEWORK.md) - Overview of the analytics-driven, insight-centric philosophy
2. [Architecture Overview](./02_ARCHITECTURE_OVERVIEW.md) - Technical implementation of the analytics and insight layers
3. [Storage System](./03_STORAGE.md) - How pytest-insight stores and manages test data

### User Interfaces

4. [Command Line Interface](./04_CLI_GUIDE.md) - Using the pytest-insight CLI
5. [Interactive Shell Tutorial](./05_INTERACTIVE_SHELL_TUTORIAL.md) - Building analytics and insights interactively
6. [Dashboard Guide](./06_DASHBOARD_GUIDE.md) - Using the Streamlit dashboard
7. [API Explorer](./07_API_EXPLORER.md) - Exploring the REST API

### Advanced Topics

8. [API Reference](./08_API.md) - Detailed API documentation
9. [Session Matching](./09_SESSION_MATCHING.md) - How pytest-insight matches test sessions
10. [Metric Style Guide](./10_METRIC_STYLE_GUIDE.md) - Guidelines for metric design
