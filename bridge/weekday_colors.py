"""Shared weekday-coloring setting values for the bridge and Studio."""

VALUES = (
    "sunday",
    "sunday_holiday",
    "weekend_holiday",
    "all_weekdays",
    "all_holidays",
)
DEFAULT = "all_holidays"


def validate(value):
    if value not in VALUES:
        raise ValueError("invalid weekday coloring")
    return value
