"""Farm: the object that HOLDS everything else (COMPOSITION).

A Farm "has" enterprises and "has" inventory items. It does not inherit from
them: the relationship is HAS-A, not IS-A.
"""
from __future__ import annotations

from farmtrack.enterprises import Enterprise
from farmtrack.exceptions import (DuplicateItemError, InvalidInputError,
                                  ItemNotFoundError)
from farmtrack.models import InventoryItem
from farmtrack.validators import clean_text, positive_number


class Farm:
    def __init__(self, name: str = "My Farm"):
        self._name = clean_text(name, "Farm name")
        self._enterprises: dict = {}    # lower-case name -> Enterprise
        self._inventory: dict = {}      # lower-case name -> InventoryItem

    @staticmethod
    def _key(name: str) -> str:
        return clean_text(name, "Name").lower()   # 'Maize' == 'maize'

    @property
    def name(self) -> str:
        return self._name

    # ---- enterprises ------------------------------------------------------
    @property
    def enterprises(self) -> list:
        return list(self._enterprises.values())

    def add_enterprise(self, enterprise: Enterprise) -> Enterprise:
        if not isinstance(enterprise, Enterprise):
            raise InvalidInputError("Only Enterprise objects can be added.")
        key = self._key(enterprise.name)
        if key in self._enterprises:
            raise DuplicateItemError(f"'{enterprise.name}' already exists.")
        self._enterprises[key] = enterprise
        return enterprise

    def get_enterprise(self, name: str) -> Enterprise:
        try:
            return self._enterprises[self._key(name)]
        except KeyError:
            raise ItemNotFoundError(f"No enterprise named '{name}'.") from None

    def remove_enterprise(self, name: str) -> Enterprise:
        enterprise = self.get_enterprise(name)
        del self._enterprises[self._key(name)]
        return enterprise

    # ---- inventory --------------------------------------------------------
    @property
    def inventory(self) -> list:
        return list(self._inventory.values())

    def add_inventory_item(self, item: InventoryItem) -> InventoryItem:
        if not isinstance(item, InventoryItem):
            raise InvalidInputError("Only InventoryItem objects can be added.")
        key = self._key(item.name)
        if key in self._inventory:
            raise DuplicateItemError(f"'{item.name}' is already in inventory.")
        self._inventory[key] = item
        return item

    def get_item(self, name: str) -> InventoryItem:
        try:
            return self._inventory[self._key(name)]
        except KeyError:
            raise ItemNotFoundError(f"No inventory item named '{name}'.") from None

    def low_stock_items(self) -> list:
        return [item for item in self._inventory.values() if item.is_low]

    def use_input(self, item_name: str, quantity: float,
                  enterprise_name: str | None = None, cost: float | None = None):
        """Use stock and (optionally) charge its cost to an enterprise.

        Everything is validated BEFORE anything changes, so a failure never
        leaves the farm half-updated (stock reduced but no expense recorded).
        """
        item = self.get_item(item_name)
        enterprise = self.get_enterprise(enterprise_name) if enterprise_name else None
        if cost is not None:
            positive_number(cost, "Cost")
        item.use(quantity)
        if enterprise is not None and cost is not None:
            enterprise.record_expense(
                cost, f"{quantity:g} {item.unit} of {item.name}", "inputs")

    # ---- whole-farm figures ----------------------------------------------
    def total_profit(self) -> float:
        return sum(e.calculate_profit() for e in self._enterprises.values())

    def upcoming_tasks(self, days_ahead: int = 14, today=None) -> list:
        """POLYMORPHISM in action: we call the same method on every
        enterprise without caring whether it is a Maize plot or a cow."""
        tasks = []
        for enterprise in self._enterprises.values():
            tasks.extend(enterprise.get_upcoming_tasks(days_ahead, today))
        return sorted(tasks)

    # ---- saving / loading -------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "farm_name": self._name,
            "enterprises": [e.to_dict() for e in self._enterprises.values()],
            "inventory": [i.to_dict() for i in self._inventory.values()],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Farm":
        farm = cls(data.get("farm_name", "My Farm"))
        for entry in data.get("enterprises", []):
            farm.add_enterprise(Enterprise.from_dict(entry))
        for entry in data.get("inventory", []):
            farm.add_inventory_item(InventoryItem.from_dict(entry))
        return farm
