"""
pytest-insight: A pytest plugin for test history analysis and insights.

This plugin tracks and analyzes test execution history across multiple test sessions
and system-under-test (SUT) configurations. It provides:

- Historical test execution tracking
- Multi-SUT support
- Test session management
- Performance trend analysis
- Statistical insights across test runs

Usage:
    pytest --insight [other-options] test_file.py
"""

from importlib.metadata import version

__version__ = version("pytest-insight")
