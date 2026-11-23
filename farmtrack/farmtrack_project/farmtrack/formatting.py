"""Display helpers."""

CURRENCY = "KES"


def money(amount: float) -> str:
    """12500 -> 'KES 12,500.00'   -300 -> '-KES 300.00'"""
    sign = "-" if amount < 0 else ""
    return f"{sign}{CURRENCY} {abs(amount):,.2f}"
