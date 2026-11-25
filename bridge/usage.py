"""Format the account usage values actually reported by each provider."""
import math
import re
from datetime import datetime, timezone


def percentage(value):
    return type(value) in (float, int) and 0 <= value <= 100


def reset_epoch(value):
    return type(value) is int and 0 < value < 253402300800


def quota_windows(left, resets):
    windows = []
    for window in left.split(" / "):
        period, _, percent = window.rpartition(" ")
        if percent.endswith("%") and (period or period in resets):
            at = resets.get(period)
            deadline = datetime.fromtimestamp(at, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if reset_epoch(at) else "?"
            window += " リセット " + deadline
        windows.append(window)
    return " / ".join(windows)


def budget_used(used, limit, unit):
    def number(value):
        if type(value) not in (str, int, float):
            return None
        text = str(value)
        return text if len(text)<=64 and re.fullmatch(r"[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?", text) else None

    amount, ceiling = number(used), number(limit)
    if amount is None:
        return None
    return (f"{amount} / {ceiling}" if ceiling is not None else amount) + " " + unit


def claude_statusline(raw):
    fields, parts, resets = {}, [], {}
    for key, label in (("five_hour", "5h"), ("seven_day", "7d")):
        window = raw.get(key) or {}
        if percentage(window.get("used_percentage")):
            parts.append(f'{label} {100-window["used_percentage"]:g}%')
            if reset_epoch(window.get("resets_at")):
                resets[label] = window["resets_at"]
    if parts:
        fields["1.left"] = " / ".join(parts)
    data = {"fields": fields}
    if resets:
        data["resets"] = resets
    spend = raw.get("spend_limit") or {}
    amount = budget_used(spend.get("used_usd"), spend.get("limit_usd"), "USD")
    percent = spend.get("used_percentage")
    if amount is not None:
        fields["1.budget"] = "予算 約" + amount
    elif type(percent) in (int, float) and math.isfinite(percent) and percent >= 0:
        fields["1.budgetPercent"] = f"予算 {percent:g}%使用"
    if reset_epoch(spend.get("resets_at")):
        data["budgetReset"] = spend["resets_at"]
    return data
