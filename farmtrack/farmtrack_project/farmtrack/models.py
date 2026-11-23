"""Supporting classes: Transaction and InventoryItem.

Both demonstrate ENCAPSULATION: data is stored in private attributes
(leading underscore) and exposed only through read-only properties and
validated methods, so an object can never be put into an invalid state.
"""
from __future__ import annotations

from datetime import date

from farmtrack.exceptions import InsufficientStockError, InvalidInputError
from farmtrack.validators import (
    clean_text,
    non_negative_number,
    positive_number,
    to_date,
)


class Transaction:
    """One money movement: an expense (money out) or a sale (money in)."""

    EXPENSE = "expense"
    SALE = "sale"

    def __init__(self, kind: str, amount: float, description: str,
                 category: str = "general", when=None):
        if kind not in (self.EXPENSE, self.SALE):
            raise InvalidInputError("Transaction kind must be 'expense' or 'sale'.")
        self._kind = kind
        self._amount = positive_number(amount, "Amount")
        self._description = clean_text(description, "Description")
        self._category = clean_text(category, "Category")
        self._date = date.today() if when is None else to_date(when)

    # Read-only properties: there is NO setter, so a recorded transaction
    # cannot be silently changed later.
    @property
    def kind(self) -> str:
        return self._kind

    @property
    def amount(self) -> float:
        return self._amount

    @property
    def description(self) -> str:
        return self._description

    @property
    def category(self) -> str:
        return self._category

    @property
    def date(self) -> date:
        return self._date

    def to_dict(self) -> dict:
        return {
            "kind": self._kind,
            "amount": self._amount,
            "description": self._description,
            "category": self._category,
            "date": self._date.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Transaction":
        return cls(data["kind"], data["amount"], data["description"],
                   data.get("category", "general"), data["date"])

    def __str__(self) -> str:
        return (f"{self._date.isoformat()}  {self._kind:<7}  "
                f"{self._amount:,.2f}  {self._category}: {self._description}")


class InventoryItem:
    """A stock item: seed, fertiliser, feed, chemicals..."""

    def __init__(self, name: str, category: str, quantity: float,
                 unit: str, low_stock_threshold: float = 0):
        self._name = clean_text(name, "Item name")
        self._category = clean_text(category, "Category")
        self._quantity = non_negative_number(quantity, "Quantity")
        self._unit = clean_text(unit, "Unit")
        self._low_stock_threshold = non_negative_number(
            low_stock_threshold, "Low-stock threshold")

    @property
    def name(self) -> str:
        return self._name

    @property
    def category(self) -> str:
        return self._category

    @property
    def quantity(self) -> float:
        return self._quantity

    @property
    def unit(self) -> str:
        return self._unit

    @property
    def low_stock_threshold(self) -> float:
        return self._low_stock_threshold

    @property
    def is_low(self) -> bool:
        return self._quantity <= self._low_stock_threshold

    # The ONLY ways to change the quantity are these two methods, and both
    # validate. `item.quantity = 5` raises AttributeError (no setter).
    def use(self, amount: float) -> None:
        amount = positive_number(amount, "Amount used")
        if amount > self._quantity:
            raise InsufficientStockError(
                f"Only {self._quantity:g} {self._unit} of {self._name} left; "
                f"cannot use {amount:g}.")
        self._quantity -= amount

    def restock(self, amount: float) -> None:
        self._quantity += positive_number(amount, "Amount added")

    def to_dict(self) -> dict:
        return {
            "name": self._name,
            "category": self._category,
            "quantity": self._quantity,
            "unit": self._unit,
            "low_stock_threshold": self._low_stock_threshold,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "InventoryItem":
        return cls(data["name"], data["category"], data["quantity"],
                   data["unit"], data.get("low_stock_threshold", 0))

    def __str__(self) -> str:
        flag = "  [LOW STOCK]" if self.is_low else ""
        return f"{self._name} ({self._category}): {self._quantity:g} {self._unit}{flag}"
