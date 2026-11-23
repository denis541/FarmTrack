"""Small input-checking helpers shared by every class.

Keeping validation in one place means each rule is written once and every
class gets the same behaviour (DRY - Don't Repeat Yourself).
"""
from __future__ import annotations

import math
from datetime import date, datetime

from farmtrack.exceptions import InvalidInputError


def clean_text(value, field: str = "Value") -> str:
    """Return the text stripped of spaces; reject empty / non-text values."""
    if not isinstance(value, str) or not value.strip():
        raise InvalidInputError(f"{field} cannot be empty.")
    return value.strip()


def _check_number(value, field: str):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidInputError(f"{field} must be a number.")
    if not math.isfinite(value):
        raise InvalidInputError(f"{field} must be a real number.")


def positive_number(value, field: str = "Value"):
    """Number strictly greater than zero (amounts, quantities)."""
    _check_number(value, field)
    if value <= 0:
        raise InvalidInputError(f"{field} must be greater than zero.")
    return value


def non_negative_number(value, field: str = "Value"):
    """Number that may be zero but never negative (opening stock)."""
    _check_number(value, field)
    if value < 0:
        raise InvalidInputError(f"{field} cannot be negative.")
    return value


def positive_int(value, field: str = "Value") -> int:
    """Whole number greater than zero (number of animals)."""
    number = positive_number(value, field)
    if int(number) != number:
        raise InvalidInputError(f"{field} must be a whole number.")
    return int(number)


def to_date(value, field: str = "Date") -> date:
    """Accept a date, a datetime, or a 'YYYY-MM-DD' string; return a date."""
    if isinstance(value, datetime):  # check first: datetime is a subclass of date
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            raise InvalidInputError(f"{field} must be in YYYY-MM-DD format.") from None
    raise InvalidInputError(f"{field} must be a date.")
