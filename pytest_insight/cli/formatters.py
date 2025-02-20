from typing import Dict, Any
from colorama import Fore, Style

def format_metrics(metrics: Dict[str, Any]) -> str:
    """Format metrics for CLI display."""
    return "\n".join([
        f"{key}: {value:.2f}" if isinstance(value, float) else f"{key}: {value}"
        for key, value in metrics.items()
    ])

def format_trend_direction(trend: str) -> str:
    """Format trend direction with color."""
    if trend == "increasing":
        return f"{Fore.RED}↑ {trend}{Style.RESET_ALL}"
    elif trend == "decreasing":
        return f"{Fore.GREEN}↓ {trend}{Style.RESET_ALL}"
    return f"{Fore.YELLOW}→ {trend}{Style.RESET_ALL}"
