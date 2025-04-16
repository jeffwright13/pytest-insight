"""Performance monitoring utilities for pytest-insight."""

import functools
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

# Global performance metrics storage
_performance_metrics = {}


def reset_metrics():
    """Reset all collected performance metrics."""
    global _performance_metrics
    _performance_metrics = {}


@contextmanager
def measure_performance(operation_name: str):
    """Context manager to measure the execution time of a code block.

    Args:
        operation_name: Name of the operation being measured
    """
    start_time = time.time()
    try:
        yield
    finally:
        end_time = time.time()
        duration = end_time - start_time
        _record_metric(operation_name, duration)


def performance_monitor(func):
    """Decorator to monitor the performance of a function or method.

    Args:
        func: The function to monitor

    Returns:
        Wrapped function with performance monitoring
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        operation_name = f"{func.__module__}.{func.__qualname__}"
        with measure_performance(operation_name):
            return func(*args, **kwargs)

    return wrapper


def _record_metric(operation_name: str, duration: float):
    """Record a performance metric.

    Args:
        operation_name: Name of the operation
        duration: Duration in seconds
    """
    global _performance_metrics

    if operation_name not in _performance_metrics:
        _performance_metrics[operation_name] = {
            "call_count": 0,
            "total_duration": 0.0,
            "min_duration": float("inf"),
            "max_duration": 0.0,
            "durations": [],
        }

    metrics = _performance_metrics[operation_name]
    metrics["call_count"] += 1
    metrics["total_duration"] += duration
    metrics["min_duration"] = min(metrics["min_duration"], duration)
    metrics["max_duration"] = max(metrics["max_duration"], duration)
    metrics["durations"].append(duration)
    metrics["avg_duration"] = metrics["total_duration"] / metrics["call_count"]


def get_performance_metrics() -> Dict[str, Dict[str, Any]]:
    """Get all collected performance metrics.

    Returns:
        Dictionary of performance metrics by operation name
    """
    return _performance_metrics


def get_sorted_metrics(
    sort_by: str = "total_duration", limit: Optional[int] = None
) -> List[tuple]:
    """Get performance metrics sorted by a specific field.

    Args:
        sort_by: Field to sort by (total_duration, call_count, avg_duration, etc.)
        limit: Optional limit on number of results

    Returns:
        List of (operation_name, metrics) tuples sorted by the specified field
    """
    sorted_ops = sorted(
        _performance_metrics.items(), key=lambda x: x[1].get(sort_by, 0), reverse=True
    )

    if limit:
        sorted_ops = sorted_ops[:limit]

    return sorted_ops


def get_slowest_operations(limit: int = 10) -> List[tuple]:
    """Get the slowest operations by total duration.

    Args:
        limit: Number of operations to return

    Returns:
        List of (operation_name, metrics) tuples for the slowest operations
    """
    return get_sorted_metrics(sort_by="total_duration", limit=limit)


def get_most_called_operations(limit: int = 10) -> List[tuple]:
    """Get the most frequently called operations.

    Args:
        limit: Number of operations to return

    Returns:
        List of (operation_name, metrics) tuples for the most called operations
    """
    return get_sorted_metrics(sort_by="call_count", limit=limit)
