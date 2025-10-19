"""Math helper utilities."""
from __future__ import annotations


def safe_div(num: int, den: int) -> float:
    return round(num / den, 2) if den else 0.0
