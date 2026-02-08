"""Utility functions for common operations."""

import re
from typing import Any


def convert_time_to_seconds(time_str: str) -> int:
    """
    Convert XmYs format to seconds.

    Examples:
        "5m30s" -> 330
        "1h15m20s" -> 3720

    Args:
        time_str: Time string in XmYs format (e.g., "5m30s", "1h15m20s")

    Returns:
        Total seconds as integer
    """
    seconds = 0
    time_str = time_str

    # Handle hours
    if "h" in time_str:
        parts = time_str.split("h")
        seconds += int(parts[0]) * 3600
        time_str = parts[1]

    # Handle minutes
    if "m" in time_str:
        parts = time_str.split("m")
        seconds += int(parts[0]) * 60
        time_str = parts[1]

    # Handle seconds
    if "s" in time_str:
        seconds_str = time_str.replace("s", "").strip()
        if seconds_str:
            seconds += int(float(seconds_str))

    return seconds


def convert_seconds_to_time(seconds: int) -> str:
    """
    Convert seconds to XmYs format.

    Examples:
        330 -> "5m30s"
        3720 -> "1h15m20s"

    Args:
        seconds: Total seconds

    Returns:
        Time string in XmYs format
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    time_parts = []
    if hours > 0:
        time_parts.append(f"{hours}h")
    if minutes > 0 or hours > 0:
        time_parts.append(f"{minutes}m")
    time_parts.append(f"{secs}s")

    return "".join(time_parts)
