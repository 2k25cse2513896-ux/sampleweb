"""round_rupees uses round-half-up and never returns a float."""

from decimal import Decimal

from app.core.money import percent_of_rupees, round_rupees


def test_half_up_goes_away_from_zero() -> None:
    assert round_rupees(Decimal("10.5")) == 11
    assert round_rupees(Decimal("19.5")) == 20
    assert round_rupees(Decimal("19.4")) == 19


def test_percent_of_199_at_10_is_20() -> None:
    # 10 percent of 199 is 19.9, which rounds to 20 rupees.
    assert percent_of_rupees(199, 10) == 20


def test_results_are_int() -> None:
    value = percent_of_rupees(1000, 15)
    assert type(value) is int
    assert value == 150
