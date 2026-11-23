"""Enterprises: the things a farm earns money from (crops and livestock).

Class hierarchy (INHERITANCE):

    Enterprise (abstract)
    |-- Crop (abstract)         -> Maize, Beans, Tomatoes
    `-- Livestock (abstract)    -> DairyCow, Poultry

Enterprise defines WHAT every enterprise must be able to do (ABSTRACTION).
Each subclass decides HOW (POLYMORPHISM).
"""
from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, timedelta

from farmtrack.exceptions import InvalidInputError
from farmtrack.formatting import money
from farmtrack.models import Transaction
from farmtrack.validators import clean_text, positive_int, positive_number, to_date


@dataclass(frozen=True, order=True)
class Task:
    """A reminder. order=True means tasks sort by due date automatically."""
    due_date: date
    description: str
    enterprise: str = ""

    def __str__(self) -> str:
        return f"{self.due_date.isoformat()}  {self.enterprise}: {self.description}"


# --------------------------------------------------------------------------
# Abstract base class
# --------------------------------------------------------------------------
class Enterprise(ABC):
    """Anything the farm produces. Cannot be instantiated directly."""

    _registry: dict = {}          # class name -> class (filled automatically)
    size_label = "Size"           # text the menu uses when asking for the size

    def __init_subclass__(cls, **kwargs):
        """Runs every time someone subclasses Enterprise: register the new
        class so it can be re-created when loading the JSON file. This is why
        adding a new crop needs ONE new subclass and no changes elsewhere."""
        super().__init_subclass__(**kwargs)
        Enterprise._registry[cls.__name__] = cls

    @classmethod
    def available_types(cls) -> dict:
        """Concrete (instantiable) enterprise types, e.g. {'Maize': Maize}."""
        return {name: klass for name, klass in Enterprise._registry.items()
                if not inspect.isabstract(klass)}

    # ---- shared data (ENCAPSULATION) -------------------------------------
    def __init__(self, name: str, start_date=None):
        self._name = clean_text(name, "Enterprise name")
        self._start_date = date.today() if start_date is None else to_date(
            start_date, "Start date")
        self._transactions: list[Transaction] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def start_date(self) -> date:
        return self._start_date

    @property
    def transactions(self) -> tuple:
        """A tuple COPY: outside code cannot add or remove transactions
        behind our back; it must use record_expense / record_sale."""
        return tuple(self._transactions)

    # ---- shared behaviour (inherited as-is by every subclass) -------------
    def add_transaction(self, transaction: Transaction) -> None:
        if not isinstance(transaction, Transaction):
            raise InvalidInputError("Only Transaction objects can be added.")
        self._transactions.append(transaction)

    def record_expense(self, amount, description, category="general", when=None):
        txn = Transaction(Transaction.EXPENSE, amount, description, category, when)
        self.add_transaction(txn)
        return txn

    def record_sale(self, amount, description, category="sales", when=None):
        txn = Transaction(Transaction.SALE, amount, description, category, when)
        self.add_transaction(txn)
        return txn

    @property
    def total_income(self) -> float:
        return sum(t.amount for t in self._transactions if t.kind == Transaction.SALE)

    @property
    def total_expenses(self) -> float:
        return sum(t.amount for t in self._transactions if t.kind == Transaction.EXPENSE)

    def calculate_profit(self) -> float:
        """Profit = sales - expenses (same rule for every enterprise)."""
        return self.total_income - self.total_expenses

    def income_between(self, start: date, end: date) -> float:
        return sum(t.amount for t in self._transactions
                   if t.kind == Transaction.SALE and start <= t.date <= end)

    def expenses_between(self, start: date, end: date) -> float:
        return sum(t.amount for t in self._transactions
                   if t.kind == Transaction.EXPENSE and start <= t.date <= end)

    # ---- helpers for subclasses ------------------------------------------
    @staticmethod
    def _window(days_ahead: int, today=None):
        """Return (today, last_day_to_look_at)."""
        if days_ahead < 0:
            raise InvalidInputError("Days ahead cannot be negative.")
        start = date.today() if today is None else to_date(today)
        return start, start + timedelta(days=days_ahead)

    def _recurring_tasks(self, label: str, every_days: int, today: date,
                         horizon: date, until: date | None = None) -> list:
        """Tasks that repeat every N days after the start date, limited to
        the window [today, horizon] and (optionally) stopping before `until`."""
        tasks, n = [], 1
        while True:
            due = self._start_date + timedelta(days=n * every_days)
            if due > horizon or (until is not None and due >= until):
                break
            if due >= today:
                tasks.append(Task(due, f"{label} #{n}", self._name))
            n += 1
        return tasks

    # ---- the ABSTRACT part: every subclass MUST provide these -------------
    @property
    @abstractmethod
    def kind(self) -> str:
        """'Crop' or 'Livestock'."""

    @property
    @abstractmethod
    def production_unit(self) -> str:
        """What we measure output in: 'kg', 'litres', 'eggs'..."""

    @property
    @abstractmethod
    def size_description(self) -> str:
        """Human-readable size: '2 acres' or '12 animals'."""

    @property
    @abstractmethod
    def total_output(self) -> float:
        """Total produced so far, in production_unit."""

    @abstractmethod
    def update_size(self, value) -> None:
        """Change the area (crops) or head count (livestock)."""

    @abstractmethod
    def record_output(self, quantity, when=None) -> None:
        """Record a harvest (crops) or production (milk, eggs)."""

    @abstractmethod
    def get_upcoming_tasks(self, days_ahead: int = 30, today=None) -> list:
        """Reminders due in the next `days_ahead` days."""

    @abstractmethod
    def production_summary(self) -> str:
        """One-line description of output so far."""

    @classmethod
    @abstractmethod
    def _create_from(cls, data: dict) -> "Enterprise":
        """Rebuild an object of this class from saved data."""

    # ---- saving / loading -------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "type": type(self).__name__,
            "name": self._name,
            "start_date": self._start_date.isoformat(),
            "transactions": [t.to_dict() for t in self._transactions],
        }

    @staticmethod
    def from_dict(data: dict) -> "Enterprise":
        """Look up the right subclass from the saved 'type' and rebuild it."""
        cls = Enterprise.available_types().get(data["type"])
        if cls is None:
            raise InvalidInputError(f"Unknown enterprise type: {data['type']!r}")
        obj = cls._create_from(data)
        for txn in data.get("transactions", []):
            obj.add_transaction(Transaction.from_dict(txn))
        return obj

    # ---- dunder methods ---------------------------------------------------
    def __str__(self) -> str:
        return (f"[{self.kind}] {self._name} | {self.size_description} | "
                f"started {self._start_date.isoformat()} | "
                f"profit {money(self.calculate_profit())}")

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self._name!r})"


# --------------------------------------------------------------------------
# Level 2: Crop
# --------------------------------------------------------------------------
class Crop(Enterprise):
    """A planted crop. Still abstract: each real crop must say how long it
    takes to grow and how often it needs spraying."""

    kind = "Crop"
    production_unit = "kg"
    size_label = "Area in acres"

    def __init__(self, name: str, area_acres: float, start_date=None):
        super().__init__(name, start_date)      # let the parent set up shared data
        self._area_acres = positive_number(area_acres, "Area")
        self._harvested_kg = 0.0

    @property
    @abstractmethod
    def growth_days(self) -> int:
        """Days from planting to harvest."""

    @property
    @abstractmethod
    def spray_interval_days(self) -> int:
        """Days between spraying rounds."""

    @property
    def area_acres(self) -> float:
        return self._area_acres

    @property
    def expected_harvest_date(self) -> date:
        return self._start_date + timedelta(days=self.growth_days)

    @property
    def size_description(self) -> str:
        return f"{self._area_acres:g} acres"

    @property
    def total_output(self) -> float:
        return self._harvested_kg

    def update_size(self, value) -> None:
        self._area_acres = positive_number(value, "Area")

    def record_output(self, quantity, when=None) -> None:
        # Crops only keep a running total of kg (the date is accepted so the
        # method signature matches Livestock, but is not stored).
        self._harvested_kg += positive_number(quantity, "Harvest quantity")

    def get_upcoming_tasks(self, days_ahead: int = 30, today=None) -> list:
        today, horizon = self._window(days_ahead, today)
        harvest = self.expected_harvest_date
        tasks = []
        if today <= self._start_date <= horizon:
            tasks.append(Task(self._start_date, "Plant", self._name))
        tasks += self._recurring_tasks("Spray", self.spray_interval_days,
                                       today, horizon, until=harvest)
        if self._harvested_kg == 0 and today <= harvest <= horizon:
            tasks.append(Task(harvest, "Harvest", self._name))
        return sorted(tasks)

    def production_summary(self) -> str:
        return (f"{self._name}: {self._harvested_kg:g} kg harvested so far; "
                f"expected harvest {self.expected_harvest_date.isoformat()}")

    def to_dict(self) -> dict:
        data = super().to_dict()                # reuse the parent's dict...
        data.update(area_acres=self._area_acres,  # ...and add Crop-only fields
                    harvested_kg=self._harvested_kg)
        return data

    @classmethod
    def _create_from(cls, data: dict) -> "Crop":
        obj = cls(data["name"], data["area_acres"], data["start_date"])
        obj._harvested_kg = float(data.get("harvested_kg", 0))
        return obj


# Level 3: concrete crops. Each is just data - no new logic needed.
class Maize(Crop):
    growth_days = 120
    spray_interval_days = 30


class Beans(Crop):
    growth_days = 90
    spray_interval_days = 21


class Tomatoes(Crop):
    growth_days = 90
    spray_interval_days = 14


# --------------------------------------------------------------------------
# Level 2: Livestock
# --------------------------------------------------------------------------
class Livestock(Enterprise):
    """A group of animals. Still abstract: each real type must say what it
    produces and how often it needs vaccinating."""

    kind = "Livestock"
    size_label = "Number of animals"

    def __init__(self, name: str, animal_count: int, start_date=None):
        super().__init__(name, start_date)
        self._animal_count = positive_int(animal_count, "Number of animals")
        self._production_log: list = []         # list of (date, quantity)

    @property
    @abstractmethod
    def vaccination_interval_days(self) -> int:
        """Days between vaccinations."""

    @property
    def animal_count(self) -> int:
        return self._animal_count

    @property
    def size_description(self) -> str:
        return f"{self._animal_count} animals"

    @property
    def total_output(self) -> float:
        return sum(quantity for _, quantity in self._production_log)

    def update_size(self, value) -> None:
        self._animal_count = positive_int(value, "Number of animals")

    def record_output(self, quantity, when=None) -> None:
        quantity = positive_number(quantity, "Production quantity")
        day = date.today() if when is None else to_date(when)
        self._production_log.append((day, quantity))

    def get_upcoming_tasks(self, days_ahead: int = 30, today=None) -> list:
        today, horizon = self._window(days_ahead, today)
        return sorted(self._recurring_tasks(
            "Vaccination", self.vaccination_interval_days, today, horizon))

    def production_summary(self) -> str:
        return (f"{self._name}: {self.total_output:g} {self.production_unit} "
                f"recorded from {self._animal_count} animal(s)")

    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update(
            animal_count=self._animal_count,
            production_log=[{"date": d.isoformat(), "quantity": q}
                            for d, q in self._production_log])
        return data

    @classmethod
    def _create_from(cls, data: dict) -> "Livestock":
        obj = cls(data["name"], data["animal_count"], data["start_date"])
        for entry in data.get("production_log", []):
            obj.record_output(entry["quantity"], entry["date"])
        return obj


class DairyCow(Livestock):
    production_unit = "litres"
    vaccination_interval_days = 180
    deworming_interval_days = 120

    def get_upcoming_tasks(self, days_ahead: int = 30, today=None) -> list:
        # OVERRIDE + EXTEND: start from Livestock's version (vaccinations)
        # and add a task that only dairy cows have.
        tasks = super().get_upcoming_tasks(days_ahead, today)
        today, horizon = self._window(days_ahead, today)
        tasks += self._recurring_tasks("Deworming", self.deworming_interval_days,
                                       today, horizon)
        return sorted(tasks)


class Poultry(Livestock):
    production_unit = "eggs"
    vaccination_interval_days = 90
