"""Whole-rupee money helpers. Prices are integers. Never use floats. Never use paise."""

from decimal import Decimal, ROUND_HALF_UP


def round_rupees(value: Decimal) -> int:
    """
    Round a Decimal amount to a whole rupee using round-half-up (0.5 becomes 1).

    Percent discounts must go through this function so the stored total stays an integer.
    Example: 10 percent of 199 is 19.9, which becomes 20 rupees.
    """
    if isinstance(value, Decimal) is False:
        # String conversion avoids binary float noise if a caller passes int.
        value = Decimal(str(value))
    rounded = value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(rounded)


def percent_of_rupees(amount_rupees: int, percent: int) -> int:
    """
    Take an integer rupee amount and an integer percent, return integer rupees.

    Uses Decimal only for the division, then round_rupees().
    """
    if amount_rupees < 0:
        return 0
    if percent < 0:
        return 0
    raw = Decimal(amount_rupees) * Decimal(percent) / Decimal(100)
    return round_rupees(raw)
