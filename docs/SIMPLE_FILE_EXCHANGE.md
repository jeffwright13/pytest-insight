# Simple File Exchange (SFE)

## Overview

The Simple File Exchange (SFE) feature in pytest-insight allows users to easily share test session data between different machines. This is particularly useful for teams working on the same project but using different development environments.

SFE provides a straightforward way to:
- Export test sessions to a file
- Import test sessions from a file
- Selectively clear test sessions

## Workflow

### Exporting Sessions

To export test sessions, use the `export_sessions` method of the JSONStorage class:

```python
from pytest_insight.core.storage import get_storage_instance

# Get the storage instance
storage = get_storage_instance()

# Export all sessions
export_path = "path/to/export.json"
count = storage.export_sessions(export_path)
print(f"Exported {count} sessions")

# Export sessions from the last 7 days
count = storage.export_sessions(export_path, days=7)
print(f"Exported {count} sessions from the last 7 days")

# Export sessions for a specific SUT
count = storage.export_sessions(export_path, sut_name="my-service")
print(f"Exported {count} sessions for my-service")

# Export sessions with combined filters
count = storage.export_sessions(export_path, days=7, sut_name="my-service")
print(f"Exported {count} sessions for my-service from the last 7 days")

### Importing Sessions

To import test sessions, use the `import_sessions` method of the JSONStorage class:

```python
from pytest_insight.core.storage import get_storage_instance

# Get the storage instance
storage = get_storage_instance()

# Import sessions from a file using default strategy (skip_existing)
import_path = "path/to/import.json"
stats = storage.import_sessions(import_path)
print(f"Imported {stats['added']} sessions, updated {stats['updated']} sessions, skipped {stats['skipped']} sessions")

# Import sessions with replace existing strategy
print(f"Imported {stats['imported']} sessions, replacing any existing ones")

# Import sessions with keep_both strategy
stats = storage.import_sessions(import_path, merge_strategy="keep_both")
print(f"Imported {stats['imported']} sessions, keeping both versions of duplicates")
```

Merge Strategies
When importing sessions, you can choose from three merge strategies:

skip_existing (default): Skip sessions that already exist in the storage
replace_existing: Replace existing sessions with imported ones
keep_both: Keep both versions, appending a suffix to imported session IDs

### Selectively Clearing Sessions

You can selectively clear sessions using the clear_sessions method:

```python
from pytest_insight.core.storage import get_storage_instance
from pytest_insight.core.query import Query

# Get the storage instance
storage = get_storage_instance()

# Clear all sessions
count = storage.clear_sessions()
print(f"Cleared {count} sessions")

# Selectively clear sessions using Query
query = Query(storage)
sessions_to_clear = query.for_sut("my-service").in_last_days(30).execute()
count = storage.clear_sessions(sessions_to_clear)
print(f"Cleared {count} sessions for my-service from the last 30 days")

## Common Use Cases

### Sharing Test Results Between Team Members

1. Developer A runs tests and exports the sessions:
   ```python
   storage.export_sessions("team_sessions.json")
   ```

2. Developer A shares the file with Developer B

3. Developer B imports the sessions:
   ```python
   storage.import_sessions("team_sessions.json")
   ```

### Backing Up Test Data

1. Export all sessions to a backup file:
   ```python
   storage.export_sessions("backup_sessions.json")
   ```

2. If needed, restore from backup:
   ```python
   storage.import_sessions("backup_sessions.json")
   ```

### Combining Test Data from Multiple Sources

1. Export sessions from each source:
   ```python
   # On machine 1
   storage.export_sessions("machine1_sessions.json")

   # On machine 2
   storage.export_sessions("machine2_sessions.json")
   ```

2. Import both files to a central location:
   ```python
   # On central machine
   storage.import_sessions("machine1_sessions.json")
   storage.import_sessions("machine2_sessions.json")
   ```

## API Reference

### export_sessions

```python
def export_sessions(export_path: str, days: Optional[int] = None,
                   sut_name: Optional[str] = None) -> int:
    """
    Export sessions to a file for sharing with other instances.

    Args:
        export_path: Path where to save the exported sessions
        days: Optional, only export sessions from the last N days
        sut_name: Optional, only export sessions for a specific SUT

    Returns:
        Number of sessions exported
    """
```

### import_sessions

```python
def import_sessions(import_path: str, merge_strategy: str = "skip_existing") -> Dict[str, int]:
    """
    Import sessions from a file exported by another instance.

    Args:
        import_path: Path to the file containing exported sessions
        merge_strategy: How to handle duplicate session IDs:
            - "skip_existing": Skip sessions that already exist (default)
            - "replace_existing": Replace existing sessions with imported ones
            - "keep_both": Keep both versions, appending a suffix to imported IDs

    Returns:
        Dictionary with import statistics:
            - total: Total number of sessions in the import file
            - imported: Number of sessions successfully imported
            - skipped: Number of sessions skipped
            - errors: Number of sessions with errors during import
    """
```

### clear_sessions

```python
def clear_sessions(sessions_to_clear: Optional[List[TestSession]] = None) -> int:
    """
    Remove stored sessions.

    Args:
        sessions_to_clear: Optional list of TestSession objects to remove.
                          If None, removes all sessions.

    Returns:
        Number of sessions removed
    """
```

## Integration with Query System

The SFE functionality integrates seamlessly with pytest-insight's query system. This allows you to:

1. Use queries to filter sessions for export:
   ```python
   from pytest_insight.core.storage import get_storage_instance
   from pytest_insight.core.query import Query

   storage = get_storage_instance()
   query = Query(storage)

   # Find sessions with failing tests
   failing_sessions = query.filter_by_test().with_outcome("failed").apply().execute()

   # You can then use the SUT names from these sessions to export
   sut_names = {session.sut_name for session in failing_sessions}
   for sut_name in sut_names:
       storage.export_sessions(f"{sut_name}_failing.json", sut_name=sut_name)
   ```

2. Use queries to select specific sessions for clearing:
   ```python
   # Select old sessions from a specific SUT
   old_sessions = query.for_sut("legacy-service").before_date("2025-01-01").execute()

   # Clear only those sessions
   storage.clear_sessions(old_sessions)
   ```

Remember that the query system always preserves the full session context, which makes it ideal for working with the SFE functionality.
