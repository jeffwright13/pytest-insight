"""Constants and configuration for pytest-insight."""

from enum import Enum
from pathlib import Path


class StorageType(Enum):
    LOCAL = "local"
    JSON = "json"
    REMOTE = "remote"
    DATABASE = "database"


DEFAULT_STORAGE_TYPE = StorageType.JSON

DEFAULT_STORAGE_PATH = Path.home() / ".pytest_insight" / "practice.json"
