"""Validate saved Unix-nanosecond times before formatting them in the UI."""

from datetime import datetime


def valid_unix_ns(value):
    if type(value) is not int:
        return False
    try:
        datetime.fromtimestamp(value / 1_000_000_000)
    except (OverflowError, OSError, ValueError):
        return False
    return True
