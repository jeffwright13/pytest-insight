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
- Custom file path via storage profile
- Default location: `~/.pytest_insight/{profile_name}.json`

### InMemoryStorage

The in-memory storage backend keeps all data in memory without persisting to disk. It's useful for:

- Testing and development
- Temporary data analysis
- Tutorial and demonstration scenarios

Data is lost when the application exits or when the storage instance is destroyed.

## Storage Profiles

Storage profiles provide a way to manage multiple storage configurations and easily switch between them. **As of the latest version, profiles are now the recommended and primary way to configure storage in pytest-insight.**

### Profile Components

Each profile contains:
- **name**: Unique identifier for the profile
- **storage_type**: The type of storage to use ("json" or "memory")
- **file_path**: Optional custom path for file-based storage (defaults to `~/.pytest_insight/{profile_name}.json`)

### Profile Management

```python
from pytest_insight.core.storage import create_profile, switch_profile, list_profiles, get_active_profile

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

### CLI Profile Management

pytest-insight provides a command-line interface for managing storage profiles:

```bash
# List all profiles
insight profile list

# List profiles by type
insight profile list --type json
insight profile list --type memory

# List profiles by name pattern
insight profile list --pattern "test-*"

# Combine filters
insight profile list --type json --pattern "prod*"

# Create a new profile
insight profile create my-profile --type json

# Switch to a profile
insight profile switch my-profile

# Delete a single profile
insight profile delete old-profile

# Bulk delete profiles
insight profile clean  # Deletes all memory profiles by default

# Bulk delete with pattern matching
insight profile clean --pattern "test-*"  # Deletes memory profiles matching pattern

# Bulk delete with type filtering
insight profile clean --type json --pattern "temp-*"  # Deletes JSON profiles matching pattern

# Preview which profiles would be deleted (dry run)
insight profile clean --pattern "test-*" --dry-run

# Skip confirmation prompt
insight profile clean --pattern "test-*" --force

# Merge sessions from multiple profiles into a target profile
insight profile merge source1,source2 target-profile --create --strategy keep_both

# Merge with filtering
insight profile merge source1,source2 target-profile --filter "test_*" --strategy replace_existing
```

In-memory profiles are not persisted to the configuration file, which helps prevent accumulation of unnecessary profiles. The `clean` command is particularly useful for removing temporary profiles that may have been created during testing or development.

### Automatic Profile Creation

When using pytest with the `--insight-profile` option, if the specified profile doesn't exist, it will be automatically created with default settings (JSON storage type and default file path). This allows you to easily create and use new profiles on the fly:

```bash
# This will automatically create a new profile named "new-profile" if it doesn't exist
pytest --insight --insight-profile=new-profile
```

### Using Profiles with Storage

```python
from pytest_insight.core.storage import get_storage_instance

# Get storage using the active profile
storage = get_storage_instance()

# Get storage using a specific profile
storage = get_storage_instance(profile_name="demo")
```

### Environment Variable Override

You can override the active profile using the `PYTEST_INSIGHT_PROFILE` environment variable:

```bash
# Use the demo profile for this session
export PYTEST_INSIGHT_PROFILE=demo
```

This is particularly useful in CI/CD environments like Jenkins jobs running in Docker containers, where you can set different profiles for different jobs.

## Profile Merging

The profile merge command allows you to combine test sessions from multiple source profiles into a target profile. This is useful for:

1. **Consolidating Data**: Combine test results from multiple environments or test runs
2. **Creating Aggregated Views**: Build comprehensive profiles that include data from various sources
3. **Data Migration**: Move specific sessions between profiles while applying filters
4. **Backup and Restore**: Create merged backups of critical test data

### Merge Command Syntax

```bash
insight profile merge SOURCE_PROFILES TARGET_PROFILE [OPTIONS]
```

Where:
- `SOURCE_PROFILES`: Comma-separated list of source profile names
- `TARGET_PROFILE`: Name of the target profile to merge into

### Merge Options

| Option | Description |
|--------|-------------|
| `--create, -c` | Create target profile if it doesn't exist |
| `--type, -t` | Storage type for target profile if creating new ('json' or 'memory') |
| `--strategy, -s` | How to handle duplicate sessions: 'skip_existing', 'replace_existing', or 'keep_both' |
| `--filter, -f` | Only merge sessions matching this pattern |
| `--dry-run` | Show what would be merged without actually merging |

### Merge Strategies

The merge command supports three strategies for handling duplicate sessions:

1. **skip_existing** (default): Skip sessions that already exist in the target profile
2. **replace_existing**: Replace existing sessions in the target with those from the source profiles
3. **keep_both**: Keep both versions by renaming the imported sessions with a unique suffix

### Examples

```bash
# Basic merge from two profiles into a third
insight profile merge profile1,profile2 combined-profile

# Create the target profile if it doesn't exist
insight profile merge profile1,profile2 new-profile --create --type json

# Replace existing sessions in the target
insight profile merge profile1,profile2 target --strategy replace_existing

# Keep both versions of duplicate sessions
insight profile merge profile1,profile2 target --strategy keep_both

# Only merge sessions matching a pattern
insight profile merge profile1,profile2 target --filter "test_api_*"

# Preview what would be merged without making changes
insight profile merge profile1,profile2 target --dry-run
```

### Programmatic Merging

While the CLI provides a convenient interface for merging profiles, you can also perform similar operations programmatically:

```python
from pytest_insight.core.storage import load_sessions, get_profile_manager

# Load sessions from source profiles
source1_sessions = load_sessions("profile1")
source2_sessions = load_sessions("profile2")

# Get the profile manager
profile_manager = get_profile_manager()

# Merge sessions into target profile
for session_id, session in source1_sessions.items():
    profile_manager.save_session("target", session, session_id)
    
for session_id, session in source2_sessions.items():
    profile_manager.save_session("target", session, session_id)
```

## Simple File Exchange (SFE)

The Simple File Exchange functionality allows importing and exporting test session data between different storage instances or applications.

### Export Operations

```python
# Export all sessions to a file
storage.export_sessions("/path/to/export.json")

# Export with filtering
storage.export_sessions(
    "/path/to/export.json",
    filter_func=lambda session: session.sut_name == "my-service"
)

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
7. **CI/CD Integration**: Use different profiles for different Jenkins jobs or environments

## Configuration

### Default Settings

- Default storage type: JSON
- Default file path: `~/.pytest_insight/{profile_name}.json`
- Default profile: "default"
- Profiles configuration: `~/.pytest_insight/profiles.json`

### Environment Variables

- `PYTEST_INSIGHT_PROFILE`: Override the active profile

## API Reference

### Storage Instance

```python
from pytest_insight.core.storage import get_storage_instance

# Get storage with defaults (uses active profile)
storage = get_storage_instance()

# Get storage using a specific profile
storage = get_storage_instance(profile_name="demo")
```

### Storage Operations

```python
# Save a test session
storage.save_session(test_session)

# Load all sessions
sessions = storage.load_sessions()

# Get a session by ID
session = storage.get_session_by_id("session-123")

# Clear all sessions
storage.clear_sessions()

# Clear specific sessions
storage.clear_sessions(sessions_to_clear=[session1, session2])
```

### Profile Management

```python
from pytest_insight.core.storage import (
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
manager._create_profile("custom", "json", "/path/to/file.json")
manager.delete_profile("old-profile")
```

## Integration with Core API

The storage system integrates with the pytest-insight core API to provide a fluent interface for finding and filtering test sessions:

```python
from pytest_insight.core.core_api import InsightAPI, query

# Initialize API with a specific profile
api = InsightAPI(profile_name="my_profile")

# Query using the profile's storage
results = api.query().with_sut("service").in_last_days(7).execute()

# Standalone query function (uses active or specified profile)
results = query(profile_name="my_profile").with_outcome("failed").execute()
```

This integration follows the core pytest-insight API design principles of providing a fluent interface for Query, Compare, and Analyze operations, while keeping the implementation details abstracted away from the user.
