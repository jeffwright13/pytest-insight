# pytest-insight Storage System

The storage system in pytest-insight is responsible for persisting test session data and providing access to historical test results. This document describes the storage architecture, available storage backends, and how to configure and use the storage system effectively.

## Storage Architecture

### Core Components

The storage system consists of several key components:

1. **BaseStorage**: Abstract interface defining the core storage operations
2. **Storage Implementations**: Concrete implementations of the storage interface
   - **JSONStorage**: File-based storage using JSON format
   - **InMemoryStorage**: Volatile in-memory storage for testing and demos
3. **StorageProfile**: Configuration for storage type and location
4. **ProfileManager**: Management of multiple storage profiles

### Data Flow

┌─────────────┐     ┌────────────────┐     ┌────────────────┐
│ Test Runner │────▶│ Storage System │────▶│ Storage Backend│
└─────────────┘     └────────────────┘     └────────────────┘
                           │                       │
                           ▼                       ▼
                    ┌──────────────┐        ┌─────────────┐
                    │ Test Session │        │ Persistence │
                    │    Data      │        │   Medium    │
                    └──────────────┘        └─────────────┘

## Storage Backends

### JSONStorage

The default storage backend uses JSON files to store test session data. It provides:

- Persistent storage across application restarts
- Human-readable data format
- Atomic file operations for data integrity
- Automatic backup on data corruption

Configuration options:
- Custom file path via `file_path` parameter
- Default location: `~/.pytest_insight/sessions.json`

### InMemoryStorage

The in-memory storage backend keeps all data in memory without persisting to disk. It's useful for:

- Testing and development
- Temporary data analysis
- Tutorial and demonstration scenarios

Data is lost when the application exits or when the storage instance is destroyed.

## Storage Profiles

Storage profiles provide a way to manage multiple storage configurations and easily switch between them.

### Profile Components

Each profile contains:
- **name**: Unique identifier for the profile
- **storage_type**: The type of storage to use ("json" or "memory")
- **file_path**: Optional custom path for file-based storage

### Profile Management

```python
from pytest_insight.storage import create_profile, switch_profile, list_profiles, get_active_profile

# Create profiles for different purposes
create_profile("production", "json", "/path/to/production/data.json")
create_profile("demo", "json", "/path/to/demo/data.json")
create_profile("tutorial", "memory")  # In-memory storage for tutorials

# Switch to a specific profile
switch_profile("demo")

# List all available profiles
profiles = list_profiles()

# Get the currently active profile
active_profile = get_active_profile()
```

### Using Profiles with Storage

```python
from pytest_insight.storage import get_storage_instance

# Get storage using the active profile
storage = get_storage_instance()

# Get storage using a specific profile
storage = get_storage_instance(profile_name="demo")

# Profile settings override direct parameters
storage = get_storage_instance(profile_name="demo", storage_type="memory")  # Uses demo profile's storage_type
```

### Environment Variable Override

You can override the active profile using the `PYTEST_INSIGHT_PROFILE` environment variable:

```bash
# Use the demo profile for this session
export PYTEST_INSIGHT_PROFILE=demo
```

## Simple File Exchange (SFE)

The Simple File Exchange functionality allows importing and exporting test session data between different storage instances or applications.

### Export Operations

```python
# Export all sessions
storage.export_sessions("/path/to/export.json")

# Export sessions from the last 7 days
storage.export_sessions("/path/to/recent.json", days=7)

# Export in CSV format
storage.export_sessions("/path/to/export.csv", output_format="csv")
```

### Import Operations

```python
# Import sessions with default settings (skip existing)
storage.import_sessions("/path/to/import.json")

# Import with custom merge strategy
storage.import_sessions("/path/to/import.json", merge_strategy="replace_existing")
```

Available merge strategies:
- **skip_existing**: Skip sessions that already exist (default)
- **replace_existing**: Replace existing sessions with imported ones
- **keep_both**: Keep both versions, appending a suffix to imported IDs

## Storage Profiles and SFE Integration

Storage profiles integrate seamlessly with the Simple File Exchange functionality, enabling powerful data management workflows:

### Profile-Specific Import/Export

Each storage profile can have its own import/export settings and data:

```python
# Export from production profile
switch_profile("production")
storage = get_storage_instance()
storage.export_sessions("/tmp/export.json")

# Import to demo profile
switch_profile("demo")
storage = get_storage_instance()
storage.import_sessions("/tmp/export.json")
```

### Use Cases

1. **Environment Isolation**: Keep production, testing, and demo data separate
2. **Data Migration**: Move data between different storage locations
3. **Controlled Data Sharing**: Export specific subsets of data from one profile to another
4. **Environment Bootstrapping**: Quickly set up new environments with initial data
5. **Backup and Restore**: Create backups of specific profiles before making changes
6. **Collaboration**: Share specific test results with team members

## Configuration

### Default Settings

- Default storage type: JSON
- Default file path: `~/.pytest_insight/sessions.json`
- Default profile: "default"
- Profiles configuration: `~/.pytest_insight/profiles.json`

### Environment Variables

- `PYTEST_INSIGHT_STORAGE_TYPE`: Override the default storage type
- `PYTEST_INSIGHT_DB_PATH`: Override the default file path
- `PYTEST_INSIGHT_PROFILE`: Override the active profile

## API Reference

### Storage Instance

```python
from pytest_insight.storage import get_storage_instance

# Get storage with defaults
storage = get_storage_instance()

# Specify storage type
storage = get_storage_instance(storage_type="json")

# Specify file path
storage = get_storage_instance(file_path="/custom/path.json")

# Specify profile
storage = get_storage_instance(profile_name="demo")
```

### Storage Operations

```python
# Save a test session
storage.save_session(test_session)

# Load all sessions
sessions = storage.load_sessions()

# Get the most recent session
latest = storage.get_last_session()

# Get a session by ID
session = storage.get_session_by_id("session-123")

# Clear all sessions
storage.clear_sessions()

# Clear specific sessions
storage.clear_sessions(sessions_to_clear=[session1, session2])
```

### Profile Management

```python
from pytest_insight.storage import (
    create_profile,
    switch_profile,
    list_profiles,
    get_active_profile,
    ProfileManager
)

# Create a profile
profile = create_profile("name", "storage_type", "file_path")

# Switch profiles
active = switch_profile("profile_name")

# List all profiles
profiles = list_profiles()

# Get active profile
active = get_active_profile()

# Advanced: Direct ProfileManager usage
manager = ProfileManager()
manager.create_profile("custom", "json", "/path/to/file.json")
manager.delete_profile("old-profile")
```

## Integration with Query System

The storage system integrates with the pytest-insight query system to provide a fluent interface for finding and filtering test sessions:

```python
from pytest_insight import query

# Query using the active profile's storage
results = query.for_sut("service").in_last_days(7).execute()

# Query with test-level filtering
results = query.filter_by_test().with_outcome("failed").apply().execute()
```

This integration follows the core pytest-insight API design principles of providing a fluent interface for Query, Compare, and Analyze operations, while keeping the implementation details abstracted away from the user.
