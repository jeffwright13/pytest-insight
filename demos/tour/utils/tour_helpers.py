"""Tour helper utilities for consistent formatting and user interaction.

This module provides common utilities used across the tour:
1. Output formatting with colors and styles
2. State management for tour progress
3. Notebook launching and management
"""

import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any

class Style(Enum):
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    INFO = '\033[94m'
    SUCCESS = '\033[92m'
    WARNING = '\033[93m'
    ERROR = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

@dataclass
class TourState:
    """Track state and progress through the tour."""
    current_section: str
    completed_sections: set[str]
    api_instance: Any  # InsightAPI instance
    last_results: Dict[str, Any]

class TourHelper:
    def __init__(self):
        self.state = TourState(
            current_section="",
            completed_sections=set(),
            api_instance=None,
            last_results={}
        )

    def format_output(self, text: str, style: Style = Style.INFO) -> str:
        """Format text with color and style."""
        return f"{style.value}{text}{Style.END.value}"

    def print_header(self, text: str) -> None:
        """Print a formatted header."""
        print(f"\n{self.format_output('=== ' + text + ' ===', Style.HEADER)}")

    def print_success(self, text: str) -> None:
        """Print a success message."""
        print(self.format_output(f"✓ {text}", Style.SUCCESS))

    def print_error(self, text: str) -> None:
        """Print an error message."""
        print(self.format_output(f"❌ {text}", Style.ERROR))

    def print_warning(self, text: str) -> None:
        """Print a warning message."""
        print(self.format_output(f"⚠ {text}", Style.WARNING))

    def print_code(self, code: str) -> None:
        """Print code snippet with proper formatting."""
        print(self.format_output("\nExample code:", Style.BOLD))
        print(code)

    def launch_notebook(self, topic: str) -> bool:
        """Launch a Jupyter notebook for the given topic."""
        notebook_path = Path("notebooks") / f"{topic}_deep_dive.ipynb"

        if not notebook_path.exists():
            self.print_error(f"Notebook for {topic} not found!")
            return False

        try:
            subprocess.run(["jupyter", "notebook", str(notebook_path)])
            return True
        except Exception as e:
            self.print_error(f"Failed to launch notebook: {str(e)}")
            return False

    def update_state(self, section: str, results: Optional[Dict[str, Any]] = None) -> None:
        """Update tour state with current section and results."""
        self.state.current_section = section
        self.state.completed_sections.add(section)
        if results:
            self.state.last_results[section] = results

    def get_last_results(self, section: str) -> Optional[Dict[str, Any]]:
        """Get results from the last run of a section."""
        return self.state.last_results.get(section)

    def is_section_completed(self, section: str) -> bool:
        """Check if a section has been completed."""
        return section in self.state.completed_sections
