from pytest_insight.core.analysis import Analysis
from pytest_insight.core.comparison import Comparison
from pytest_insight.core.models import (
    RerunTestGroup,
    TestOutcome,
    TestResult,
    TestSession,
)
from pytest_insight.core.query import InvalidQueryParameterError, Query, QueryTestFilter
from pytest_insight.core.storage import JSONStorage, get_storage_instance
from pytest_insight.utils.constants import DEFAULT_STORAGE_TYPE, StorageType

__all__ = [
    # Core models
    "TestOutcome",
    "TestResult",
    "TestSession",
    "RerunTestGroup",
    # Storage
    "get_storage_instance",
    "JSONStorage",
    "StorageType",
    "DEFAULT_STORAGE_TYPE",
    # Query system (two-level filtering)
    "Query",
    "QueryTestFilter",
    "InvalidQueryParameterError",
    # Comparison
    "Comparison",
    # Analysis
    "Analysis",
    # Version
    "__version__",
]

# Import version at the end to avoid circular imports
import importlib.metadata

__version__ = importlib.metadata.version("pytest-insight")
