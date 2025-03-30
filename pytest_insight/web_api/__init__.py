"""Web API package for pytest-insight.

This package contains the web API components for pytest-insight, including:
- REST API endpoints for accessing pytest-insight functionality
- Interactive dashboard for exploring TestSessions
- API introspection for dynamically generating endpoints

The web API follows the same core operations as the Python API:
1. Query - Finding and filtering test sessions
2. Compare - Comparing between versions/times
3. Analyze - Extracting insights and metrics
"""

# Make key components available at the package level
from pytest_insight.web_api.web_api import app
from pytest_insight.web_api.web_api_introspect import introspected_app, main
