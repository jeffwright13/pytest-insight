import os
import shutil
from datetime import datetime

import typer
from quantiphy import Quantity
from rich import box
from rich.console import Console
from rich.table import Table

from pytest_insight.core.storage import get_profile_manager, get_profile_metadata
from pytest_insight.utils.utils import NormalizedDatetime

app = typer.Typer(help="Manage storage profiles", no_args_is_help=True)
console = Console()


def mid_truncate(text, max_length=32, ellipsis="..."):
    """Truncate long strings in the middle, preserving start and end."""
    if not text or len(text) <= max_length:
        return text
    keep = max_length - len(ellipsis)
    left = keep // 2
    right = keep - left
    return f"{text[:left]}{ellipsis}{text[-right:]}"


@app.command()
def create(
    name: str,
    type: str = typer.Option(..., help="Type of storage (e.g., sqlite, json)"),
    path: str = typer.Option(None, help="Storage path or URI"),
):
    """Create a new storage profile."""
    pm = get_profile_manager()
    try:
        profile = pm._create_profile(name, type, path)
        typer.echo(
            f"[profile] Created profile '{name}' of type '{type}' at '{profile.file_path}'"
        )
    except Exception as e:
        typer.secho(f"[profile] Error creating profile: {e}", fg=typer.colors.RED)


@app.command()
def list():
    """List all available storage profiles."""
    pm = get_profile_manager()
    active = pm.active_profile_name
    meta = get_profile_metadata()
    profiles = None
    if isinstance(meta, dict):
        if "profiles" in meta:
            profiles = meta["profiles"]
        else:
            if all(isinstance(v, dict) for v in meta.values()):
                profiles = meta
    if not profiles:
        typer.echo("[profile] No profiles found.")
        return
    # Dynamically determine path column width based on terminal size
    term_width = shutil.get_terminal_size((120, 20)).columns
    # Minimum widths for other columns: mark(2), name(10), type(8), size(8), created(22), modified(22), padding (~12)
    min_other = 2 + 10 + 8 + 8 + 22 + 22 + 12
    path_col_width = max(10, term_width - min_other)
    table = Table(
        title="Pytest-Insight Storage Profiles", box=box.ROUNDED, show_lines=False
    )
    table.add_column("", justify="center", style="bold green", no_wrap=True)
    table.add_column("Name", style="bold", no_wrap=True)
    table.add_column("Type", style="cyan", no_wrap=True)
    table.add_column("Path", style="magenta", no_wrap=False, width=path_col_width)
    table.add_column("Created / by", style="dim", no_wrap=True)
    table.add_column("Modified / by", style="dim", no_wrap=True)
    table.add_column("Size", style="yellow", justify="right", no_wrap=True)
    for name, info in profiles.items():
        mark = "*" if name == active else ""
        file_path = info.get("file_path")
        storage_type = str(info.get("storage_type", "?"))
        size = "-"
        shown_path = "-"
        # Try to infer file_path for json/sqlite profiles if not present
        if storage_type in ("json", "sqlite"):
            if not file_path:
                # Try common locations: ~/.pytest_insight/profiles/{name}.json or .sqlite
                ext = ".json" if storage_type == "json" else ".sqlite"
                candidate = os.path.expanduser(
                    f"~/.pytest_insight/profiles/{name}{ext}"
                )
                if os.path.isfile(candidate):
                    file_path = candidate
            if file_path and os.path.isfile(file_path):
                shown_path = mid_truncate(str(file_path), path_col_width)
                try:
                    size_bytes = os.path.getsize(file_path)
                    size = Quantity(size_bytes, "B").render(prec=2, strip_zeros=False)
                except Exception:
                    size = "?"
            else:
                shown_path = "-"
        created = info.get("created")
        if created:
            if isinstance(created, datetime):
                created_fmt = created.strftime("%Y-%m-%d %H:%M:%S")
            else:
                created_fmt = str(NormalizedDatetime(created))[:19]
        else:
            created_fmt = "-"
        created_by = info.get("created_by", "-")
        modified = info.get("last_modified")
        if modified:
            if isinstance(modified, datetime):
                modified_fmt = modified.strftime("%Y-%m-%d %H:%M:%S")
            else:
                modified_fmt = str(NormalizedDatetime(modified))[:19]
        else:
            modified_fmt = "-"
        modified_by = info.get("last_modified_by", "-")
        table.add_row(
            mark,
            name,
            storage_type,
            shown_path,
            f"{created_fmt}\n{created_by}",
            f"{modified_fmt}\n{modified_by}",
            size,
        )
    console.print(table)


@app.command()
def delete(name: str):
    """Delete a storage profile."""
    pm = get_profile_manager()
    try:
        pm.delete_profile(name)
        typer.echo(f"[profile] Deleted profile '{name}'")
    except Exception as e:
        typer.secho(f"[profile] Error deleting profile: {e}", fg=typer.colors.RED)


@app.command()
def set(name: str):
    """Set the active/default storage profile."""
    pm = get_profile_manager()
    try:
        pm.switch_profile(name)
        typer.echo(f"[profile] Set profile '{name}' as active/default")
    except Exception as e:
        typer.secho(f"[profile] Error setting active profile: {e}", fg=typer.colors.RED)
