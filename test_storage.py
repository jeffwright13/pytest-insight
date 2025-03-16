import os
from pathlib import Path

# Set the environment variable for testing
test_path = Path("~/.pytest_insight/test_simple.json").expanduser()
print(f"Using test database: {test_path}")
os.environ["PYTEST_INSIGHT_DB_PATH"] = str(test_path)

# Create a clean file
with open(test_path, "w") as f:
    f.write("[]")

# Import after setting environment variable
from pytest_insight.storage import get_storage_instance

# Get a storage instance and try loading sessions
storage = get_storage_instance()
sessions = storage.load_sessions()
print(f"Loaded {len(sessions)} sessions")
