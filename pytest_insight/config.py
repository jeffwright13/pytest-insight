import json
import os
from pathlib import Path
from typing import Any, Dict

_config_cache = None


def get_config() -> Dict[str, Any]:
    """Get application configuration from file or environment variables."""
    global _config_cache

    if _config_cache is not None:
        return _config_cache

    # Try to load from config file first
    config_path = Path(__file__).parent.parent / "config.json"
    config = {}

    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
                print(f"[CONFIG] Loaded from {config_path}")
        except Exception as e:
            print(f"[CONFIG] Error loading config: {e}")

    # Environment variables override file config
    if os.environ.get("PYTEST_INSIGHT_DB_PATH"):
        config["db_path"] = os.environ.get("PYTEST_INSIGHT_DB_PATH")
        print(f"[CONFIG] Using DB path from environment: {config['db_path']}")

    _config_cache = config
    return config
