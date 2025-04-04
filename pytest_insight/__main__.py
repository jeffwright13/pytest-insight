#!/usr/bin/env python3
"""
Main entry point for pytest-insight CLI.
This allows running the package directly with: python -m pytest_insight
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import typer

from pytest_insight.core.storage import (
    create_profile,
    get_active_profile,
    get_profile_manager,
    get_storage_instance,
    list_profiles,
    switch_profile,
)
from pytest_insight.utils.db_generator import PracticeDataGenerator


# Create the main app
app = typer.Typer(
    name="insight",
    help="pytest-insight: Test analytics and insights for pytest",
    add_completion=False,
    context_settings={"help_option_names": ["--help", "-h"]}
)

# Create subcommand groups
profile_app = typer.Typer(
    help="Manage storage profiles",
    context_settings={"help_option_names": ["--help", "-h"]}
)
generate_app = typer.Typer(
    help="Generate practice test data",
    context_settings={"help_option_names": ["--help", "-h"]}
)
analyze_app = typer.Typer(
    help="Analyze test results",
    context_settings={"help_option_names": ["--help", "-h"]}
)

# Add subcommands to main app
app.add_typer(profile_app, name="profile")
app.add_typer(generate_app, name="generate")
app.add_typer(analyze_app, name="analyze")


# Profile management commands
@profile_app.command("list")
def list_all_profiles():
    """List all available storage profiles."""
    profiles = list_profiles()
    active = get_active_profile().name
    
    typer.echo("Available storage profiles:")
    for name, profile in profiles.items():
        active_marker = "* " if name == active else "  "
        typer.echo(f"{active_marker}{name} ({profile.storage_type}): {profile.file_path}")


@profile_app.command("create")
def create_new_profile(
    name: str = typer.Argument(..., help="Name for the new profile"),
    storage_type: str = typer.Option(
        "json", "--type", "-t", help="Storage type (json, memory)"
    ),
    file_path: Optional[str] = typer.Option(
        None, "--path", "-p", help="Custom file path for storage"
    ),
    activate: bool = typer.Option(
        False, "--activate", "-a", help="Set as active profile after creation"
    ),
):
    """Create a new storage profile."""
    try:
        profile = create_profile(name, storage_type, file_path)
        typer.echo(f"Created profile '{name}' ({profile.storage_type}): {profile.file_path}")
        
        if activate:
            switch_profile(name)
            typer.echo(f"Activated profile '{name}'")
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


@profile_app.command("switch")
def switch_to_profile(
    name: str = typer.Argument(..., help="Name of the profile to switch to")
):
    """Switch to a different storage profile."""
    try:
        profile = switch_profile(name)
        typer.echo(f"Switched to profile '{profile.name}'")
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


@profile_app.command("active")
def show_active_profile():
    """Show the currently active storage profile."""
    profile = get_active_profile()
    typer.echo(f"Active profile: {profile.name} ({profile.storage_type})")
    typer.echo(f"Storage path: {profile.file_path}")


@profile_app.command("delete")
def delete_existing_profile(
    name: str = typer.Argument(..., help="Name of the profile to delete"),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force deletion without confirmation"
    ),
):
    """Delete a storage profile."""
    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete profile '{name}'?")
        if not confirm:
            typer.echo("Operation cancelled.")
            return
    
    try:
        get_profile_manager().delete_profile(name)
        typer.echo(f"Deleted profile '{name}'")
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


# Generate data commands
@generate_app.command("practice")
def generate_practice_data(
    storage_profile: Optional[str] = typer.Option(
        None,
        "--profile",
        "-p",
        help="Storage profile to use for data generation (preferred over output path)",
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path for generated data (ignored if profile is specified)",
    ),
    days: int = typer.Option(
        7,
        "--days",
        "-d",
        help="Number of days to generate data for",
    ),
    targets: int = typer.Option(
        5,
        "--targets",
        "-t",
        help="Number of test targets per base",
    ),
    start_date: Optional[str] = typer.Option(
        None,
        "--start-date",
        "-s",
        help="Start date for generated data (YYYY-MM-DD format)",
    ),
    pass_rate: float = typer.Option(
        0.85,
        "--pass-rate",
        help="Target pass rate for generated tests (0.0-1.0)",
    ),
    flaky_rate: float = typer.Option(
        0.05,
        "--flaky-rate",
        help="Target flaky rate for generated tests (0.0-1.0)",
    ),
    warning_rate: float = typer.Option(
        0.1,
        "--warning-rate",
        help="Target warning rate for generated tests (0.0-1.0)",
    ),
    sut_filter: Optional[str] = typer.Option(
        None,
        "--sut-filter",
        help="System under test filter pattern",
    ),
    categories: Optional[str] = typer.Option(
        None,
        "--categories",
        "-c",
        help="Comma-separated list of test categories to include (api,ui,db,auth,integration,performance)",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress detailed output, only show essential information",
    ),
):
    """Generate practice test data with configurable parameters."""
    try:
        # Parse start date if provided
        parsed_start_date = None
        if start_date:
            try:
                # Use datetime(2023, 1, 1) as base like conftest.py
                base = datetime(2023, 1, 1, tzinfo=ZoneInfo("UTC"))
                parsed_date = datetime.strptime(start_date, "%Y-%m-%d")
                parsed_start_date = base + timedelta(
                    days=(parsed_date - datetime(2023, 1, 1)).days
                )
            except ValueError as e:
                if "format" in str(e):
                    raise typer.BadParameter("Start date must be in YYYY-MM-DD format")
                raise typer.BadParameter(str(e))

        # Parse test categories if provided
        test_categories = None
        if categories:
            test_categories = [cat.strip() for cat in categories.split(",")]
            valid_categories = {"api", "ui", "db", "auth", "integration", "performance"}
            invalid = set(test_categories) - valid_categories
            if invalid:
                raise typer.BadParameter(
                    f"Invalid categories: {', '.join(invalid)}. "
                    f"Valid categories are: {', '.join(sorted(valid_categories))}"
                )

        # Create generator instance
        generator = PracticeDataGenerator(
            storage_profile=storage_profile,
            target_path=Path(output) if output else None,
            days=days,
            targets_per_base=targets,
            start_date=parsed_start_date,
            pass_rate=pass_rate,
            flaky_rate=flaky_rate,
            warning_rate=warning_rate,
            sut_filter=sut_filter,
            test_categories=test_categories,
        )

        # Generate practice data
        generator.generate_practice_data()

        if not quiet:
            if storage_profile:
                typer.echo(f"Generated practice data for {days} days using profile '{storage_profile}'")
            else:
                typer.echo(f"Generated practice data for {days} days")
            typer.echo(f"Data saved to: {generator.target_path}")

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


# Analyze commands
@analyze_app.command("insights")
def analyze_insights(
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Storage profile to analyze"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file for analysis results"
    ),
):
    """Analyze test results and generate insights."""
    typer.echo("Analyzing test results...")
    
    # This is a placeholder for the actual implementation
    # In the future, this would use the Query/Analysis/Insights classes
    
    if profile:
        typer.echo(f"Using profile: {profile}")
        # Get the storage instance for the profile
        try:
            storage = get_storage_instance(profile)
            sessions = storage.load_sessions()
            typer.echo(f"Loaded {len(sessions)} test sessions")
            
            # Basic analysis
            typer.echo("\nBasic Statistics:")
            typer.echo(f"Total sessions: {len(sessions)}")
            
            # More detailed analysis would go here
            
        except Exception as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(code=1)
    else:
        typer.echo("No profile specified. Using active profile.")
        profile = get_active_profile()
        typer.echo(f"Active profile: {profile.name}")
        # Similar analysis would go here


# Main entry point
if __name__ == "__main__":
    app()
