# Shared date parsing for routes that accept ISO dates from the browser.
from datetime import date


def parse_date(value):
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError:
        return None


def parse_int(value):
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
