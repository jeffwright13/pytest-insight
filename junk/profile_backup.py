"""
Profile Backup and Recovery Implementation

This file contains the implementation for adding backup and recovery functionality
to the ProfileManager class in pytest-insight.
"""

import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Example of how the ProfileManager class should be modified
# Copy these methods into the ProfileManager class in storage.py


def _save_profiles(self) -> None:
    """Save profiles to configuration file."""
    # Create a backup before saving
    if self.config_path.exists():
        self.backup_profiles()

    data = {
        "profiles": {name: profile.to_dict() for name, profile in self.profiles.items()},
        "active_profile": self.active_profile_name,
    }

    # Create a temporary file in the same directory
    temp_dir = self.config_path.parent
    temp_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(mode="w", dir=temp_dir, delete=False) as temp_file:
        # Write data to the temporary file
        json.dump(data, temp_file, indent=2)
        temp_path = Path(temp_file.name)

    try:
        # Rename is atomic on POSIX systems
        temp_path.replace(self.config_path)
    except Exception as e:
        print(f"Warning: Failed to save profiles to {self.config_path}: {e}")
        if temp_path.exists():
            temp_path.unlink()  # Clean up temp file
        raise


def backup_profiles(self) -> Optional[Path]:
    """Create a timestamped backup of the profiles file.

    Returns:
        Path to the created backup file, or None if backup couldn't be created
    """
    if not self.config_path.exists():
        print("No profiles file to backup")
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = self.config_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    backup_path = backup_dir / f"profiles_backup_{timestamp}.json"
    try:
        shutil.copy2(self.config_path, backup_path)
        print(f"Created profiles backup: {backup_path}")

        # Keep only the 10 most recent backups
        self._cleanup_old_backups(max_backups=10)

        return backup_path
    except Exception as e:
        print(f"Failed to create backup: {e}")
        return None


def _cleanup_old_backups(self, max_backups: int = 10) -> None:
    """Remove old backups, keeping only the most recent ones.

    Args:
        max_backups: Maximum number of backups to keep
    """
    backup_dir = self.config_path.parent / "backups"
    if not backup_dir.exists():
        return

    backups = sorted(backup_dir.glob("profiles_backup_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    # Remove older backups beyond the max limit
    for old_backup in backups[max_backups:]:
        try:
            old_backup.unlink()
            print(f"Removed old backup: {old_backup}")
        except Exception as e:
            print(f"Failed to remove old backup {old_backup}: {e}")


def list_backups(self) -> List[Dict[str, Any]]:
    """List all available profile backups.

    Returns:
        List of dictionaries with backup information (path, timestamp, size)
    """
    backup_dir = self.config_path.parent / "backups"
    if not backup_dir.exists():
        return []

    backups = []
    for backup_path in backup_dir.glob("profiles_backup_*.json"):
        try:
            # Extract timestamp from filename
            timestamp_str = backup_path.stem.replace("profiles_backup_", "")
            timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

            # Get file size
            size_bytes = backup_path.stat().st_size

            backups.append(
                {
                    "path": str(backup_path),
                    "timestamp": timestamp,
                    "size_bytes": size_bytes,
                    "filename": backup_path.name,
                }
            )
        except Exception as e:
            print(f"Error processing backup {backup_path}: {e}")

    # Sort by timestamp (newest first)
    return sorted(backups, key=lambda b: b["timestamp"], reverse=True)


def restore_from_backup(self, backup_path: Union[str, Path]) -> bool:
    """Restore profiles from a backup file.

    Args:
        backup_path: Path to the backup file to restore from

    Returns:
        True if restore was successful, False otherwise

    Raises:
        FileNotFoundError: If the backup file doesn't exist
    """
    backup_path = Path(backup_path) if isinstance(backup_path, str) else backup_path

    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    try:
        # Create a backup of the current state before restoring
        if self.config_path.exists():
            self.backup_profiles()

        # Copy the backup to the profiles location
        shutil.copy2(backup_path, self.config_path)

        # Reload the profiles
        self._load_profiles()

        print(f"Successfully restored profiles from {backup_path}")
        return True
    except Exception as e:
        print(f"Failed to restore from backup {backup_path}: {e}")
        return False


# Example usage:
"""
# Create a profile manager
profile_manager = ProfileManager()

# Create a manual backup
backup_path = profile_manager.backup_profiles()

# List all available backups
backups = profile_manager.list_backups()
for backup in backups:
    print(f"{backup['filename']} - {backup['timestamp']}")

# Restore from a specific backup
if backups:
    profile_manager.restore_from_backup(backups[0]['path'])
"""
