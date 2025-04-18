# pytest_insight/rest_api/__init__.py
from pytest_insight.rest_api.high_level_api import app as high_level_app
from pytest_insight.rest_api.introspective_api import introspected_app

__all__ = ["high_level_app", "introspected_app"]
