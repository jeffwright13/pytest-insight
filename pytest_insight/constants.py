"""Constants and configuration for pytest-insight."""

from enum import Enum

class StorageType(Enum):
    LOCAL = "local"
    JSON = "json"
    REMOTE = "remote"
    DATABASE = "database"

DEFAULT_STORAGE_TYPE = StorageType.JSON
