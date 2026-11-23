"""FarmTrack - a simple farm management system (one-file OOP project).

OOP concepts (search for these words in the comments):
  ENCAPSULATION  - Transaction, InventoryItem, Enterprise protect their data
  ABSTRACTION    - Enterprise is an abstract class (cannot be created itself)
  INHERITANCE    - Enterprise -> Crop -> Maize,  Enterprise -> Livestock -> Poultry
  POLYMORPHISM   - Farm.upcoming_tasks() calls the same method on every enterprise
  COMPOSITION    - a Farm HAS enterprises and inventory items
"""
import csv
import json
import math
import os
from abc import ABC, abstractmethod
from datetime import date, timedelta

DATA_FILE = "farm_data.json"


# ---------------------------------------------------------------- helpers
class FarmError(Exception):
    """Our own exception: used for every expected problem (bad input, etc.)."""


def check_positive(value, what):
    """Return the value if it is a number above zero, else raise FarmError."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or not math.isfinite(value) or value <= 0:
        raise FarmError(f"{what} must be a number greater than zero.")
    return value


def to_date(value):
    """Turn '2026-03-15' into a date. Empty/None means today."""
    if not value:
        return date.today()
    try:
        result = value if isinstance(value, date) else date.fromisoformat(value)
    except ValueError:
        raise FarmError("Date must look like 2026-03-15.") from None
    if not 1900 <= result.year <= 2200:
        raise FarmError("Please use a year between 1900 and 2200.")
    return result


# ----------------------------------------------------------- Transaction
class Transaction:
    """One expense or one sale. It checks its own values when it is created,
    so an invalid transaction (negative amount, empty text) can never exist."""

    def __init__(self, kind, amount, description, when=None):
        if kind not in ("expense", "sale"):
            raise FarmError("Transaction must be 'expense' or 'sale'.")
        if not description.strip():
            raise FarmError("Description cannot be empty.")
        self.kind = kind
        self.amount = check_positive(amount, "Amount")
        self.description = description.strip()
        self.date = to_date(when)

    def to_dict(self):
        return {"kind": self.kind, "amount": self.amount,
                "description": self.description, "date": self.date.isoformat()}


# ---------------------------------------------------------- InventoryItem
class InventoryItem:
    """Farm stock (seed, fertiliser, feed...). ENCAPSULATION: the quantity can
    only be changed through use() and restock(), which check the rules."""

    def __init__(self, name, quantity, unit, warn_at=0):
        if not name.strip():
            raise FarmError("Item name cannot be empty.")
        if quantity < 0 or warn_at < 0:
            raise FarmError("Quantities cannot be negative.")
        self._name = name.strip()
        self._quantity = quantity
        self._unit = unit
        self._warn_at = warn_at

    @property
    def name(self):
        return self._name

    @property
    def quantity(self):
        return self._quantity

    @property
    def unit(self):
        return self._unit

    @property
    def is_low(self):
        return self._quantity <= self._warn_at

    def use(self, amount):
        check_positive(amount, "Amount used")
        if amount > self._quantity:
            raise FarmError(f"Only {self._quantity:g} {self._unit} of {self._name} left.")
        self._quantity -= amount

    def restock(self, amount):
        self._quantity += check_positive(amount, "Amount added")

    def to_dict(self):
        return {"name": self._name, "quantity": self._quantity,
                "unit": self._unit, "warn_at": self._warn_at}

    def __str__(self):
        warning = "   <-- LOW STOCK" if self.is_low else ""
        return f"{self._name}: {self._quantity:g} {self._unit}{warning}"


# ------------------------------------------------------------- Enterprise
class Enterprise(ABC):
    """ABSTRACTION: the parent of everything the farm produces. It holds the
    shared data and code, and DECLARES (but does not write) the methods each
    child must write itself. You cannot do Enterprise(...) directly."""

    unit = ""   # what output is measured in; each child class sets its own

    def __init__(self, name, size, start_date=None):
        if not name.strip():
            raise FarmError("Name cannot be empty.")
        self._name = name.strip()
        self._size = self._check_size(size)
        self._start_date = to_date(start_date)
        self._output = 0                 # total harvested / produced
        self._transactions = []

    # --- read-only access (ENCAPSULATION)
    @property
    def name(self):
        return self._name

    @property
    def start_date(self):
        return self._start_date

    @property
    def size(self):
        return self._size

    @property
    def output(self):
        return self._output

    @property
    def transactions(self):
        return tuple(self._transactions)     # a copy, so outsiders can't edit the list

    # --- shared behaviour: every child INHERITS these as they are
    def _check_size(self, size):
        return check_positive(size, "Size")

    def update_size(self, size):
        self._size = self._check_size(size)

    def add_expense(self, amount, description, when=None):
        self._transactions.append(Transaction("expense", amount, description, when))

    def add_sale(self, amount, description, when=None):
        self._transactions.append(Transaction("sale", amount, description, when))

    def record_output(self, quantity):
        self._output += check_positive(quantity, "Quantity")

    def total_income(self):
        return sum(t.amount for t in self._transactions if t.kind == "sale")

    def total_expenses(self):
        return sum(t.amount for t in self._transactions if t.kind == "expense")

    def profit(self):
        return self.total_income() - self.total_expenses()

    def _repeating_tasks(self, label, every_days, today, last_day, until=None):
        """Helper: a task that repeats every N days after the start date."""
        tasks = []
        if every_days > 0:
            due = self._start_date + timedelta(days=every_days)
            while due <= last_day and (until is None or due < until):
                if due >= today:
                    tasks.append((due, f"{label} {self._name}"))
                due += timedelta(days=every_days)
        return tasks

    # --- the ABSTRACT part: every child MUST write these two
    @abstractmethod
    def get_upcoming_tasks(self, days_ahead=14, today=None):
        """Return a list of (date, text) reminders."""

    @abstractmethod
    def describe(self):
        """Return a one-line description."""

    def __str__(self):
        return f"{self.describe()} | profit: KES {self.profit():,.2f}"

    # --- saving / loading
    def to_dict(self):
        return {"type": type(self).__name__, "name": self._name, "size": self._size,
                "start_date": self._start_date.isoformat(), "output": self._output,
                "transactions": [t.to_dict() for t in self._transactions]}

    @staticmethod
    def from_dict(data):
        obj = TYPES[data["type"]](data["name"], data["size"], data["start_date"])
        obj._output = data["output"]
        for t in data["transactions"]:
            obj._transactions.append(
                Transaction(t["kind"], t["amount"], t["description"], t["date"]))
        return obj


# ------------------------------------------------------------------ Crops
class Crop(Enterprise):
    """INHERITANCE (level 2): a Crop IS an Enterprise. It gets everything above
    and writes its own version of the two abstract methods."""

    unit = "kg"
    growth_days = 0         # each real crop below sets these two numbers
    spray_every_days = 0

    def harvest_date(self):
        return self._start_date + timedelta(days=self.growth_days)

    def get_upcoming_tasks(self, days_ahead=14, today=None):
        today = to_date(today)
        last_day = today + timedelta(days=days_ahead)
        tasks = []
        if today <= self._start_date <= last_day:
            tasks.append((self._start_date, f"Plant {self._name}"))
        tasks += self._repeating_tasks("Spray", self.spray_every_days, today,
                                       last_day, until=self.harvest_date())
        if self._output == 0 and today <= self.harvest_date() <= last_day:
            tasks.append((self.harvest_date(), f"Harvest {self._name}"))
        return sorted(tasks)

    def describe(self):
        return (f"[Crop] {self._name} ({self._size:g} acres) - {self._output:g} kg "
                f"harvested, harvest due {self.harvest_date()}")


# INHERITANCE (level 3): each crop is just two numbers.
class Maize(Crop):
    growth_days = 120
    spray_every_days = 30


class Beans(Crop):
    growth_days = 90
    spray_every_days = 21


class Tomatoes(Crop):
    growth_days = 90
    spray_every_days = 14


# -------------------------------------------------------------- Livestock
class Livestock(Enterprise):
    """A group of animals. Its size is a head count, so it must be whole."""

    vaccinate_every_days = 90

    def _check_size(self, size):             # OVERRIDES the parent's rule
        check_positive(size, "Number of animals")
        if size != int(size):
            raise FarmError("Number of animals must be a whole number.")
        return int(size)

    def get_upcoming_tasks(self, days_ahead=14, today=None):
        today = to_date(today)
        last_day = today + timedelta(days=days_ahead)
        return sorted(self._repeating_tasks("Vaccinate", self.vaccinate_every_days,
                                            today, last_day))

    def describe(self):
        return (f"[Livestock] {self._name} ({self._size} animals) - "
                f"{self._output:g} {self.unit} produced")


class DairyCow(Livestock):
    unit = "litres"
    vaccinate_every_days = 180

    def get_upcoming_tasks(self, days_ahead=14, today=None):
        # OVERRIDE + EXTEND: reuse the parent's tasks, then add one more.
        tasks = super().get_upcoming_tasks(days_ahead, today)
        today = to_date(today)
        last_day = today + timedelta(days=days_ahead)
        tasks += self._repeating_tasks("Deworm", 120, today, last_day)
        return sorted(tasks)


class Poultry(Livestock):
    unit = "eggs"
    vaccinate_every_days = 90


# The kinds of enterprise the program knows (used by the menu and by loading).
TYPES = {cls.__name__: cls for cls in (Maize, Beans, Tomatoes, DairyCow, Poultry)}


# ------------------------------------------------------------------- Farm
class Farm:
    """COMPOSITION: a Farm HAS enterprises and HAS inventory items."""

    def __init__(self):
        self._enterprises = {}      # lower-case name -> Enterprise
        self._inventory = {}        # lower-case name -> InventoryItem

    @property
    def enterprises(self):
        return list(self._enterprises.values())

    @property
    def inventory(self):
        return list(self._inventory.values())

    def add_enterprise(self, enterprise):
        key = enterprise.name.lower()
        if key in self._enterprises:
            raise FarmError(f"'{enterprise.name}' already exists.")
        self._enterprises[key] = enterprise

    def get_enterprise(self, name):
        if name.strip().lower() not in self._enterprises:
            raise FarmError(f"No enterprise called '{name}'.")
        return self._enterprises[name.strip().lower()]

    def remove_enterprise(self, name):
        self.get_enterprise(name)
        del self._enterprises[name.strip().lower()]

    def add_item(self, item):
        key = item.name.lower()
        if key in self._inventory:
            raise FarmError(f"'{item.name}' is already in the inventory.")
        self._inventory[key] = item

    def get_item(self, name):
        if name.strip().lower() not in self._inventory:
            raise FarmError(f"No inventory item called '{name}'.")
        return self._inventory[name.strip().lower()]

    def low_stock_items(self):
        return [item for item in self.inventory if item.is_low]

    def total_profit(self):
        return sum(e.profit() for e in self.enterprises)

    def upcoming_tasks(self, days_ahead=14, today=None):
        """POLYMORPHISM: the SAME call on every enterprise. A Maize answers
        with spray/harvest dates, a DairyCow with vaccination/deworming dates.
        This loop never checks what kind of enterprise it is."""
        tasks = []
        for enterprise in self.enterprises:
            tasks += enterprise.get_upcoming_tasks(days_ahead, today)
        return sorted(tasks)

    def save(self, path=DATA_FILE):
        data = {"enterprises": [e.to_dict() for e in self.enterprises],
                "inventory": [i.to_dict() for i in self.inventory]}
        with open(path, "w") as file:
            json.dump(data, file, indent=2)

    @staticmethod
    def load(path=DATA_FILE):
        farm = Farm()
        if not os.path.exists(path):
            return farm                       # first run: start empty
        try:
            with open(path) as file:
                data = json.load(file)
            for e in data["enterprises"]:
                farm.add_enterprise(Enterprise.from_dict(e))
            for i in data["inventory"]:
                farm.add_item(InventoryItem(i["name"], i["quantity"], i["unit"], i["warn_at"]))
        except (ValueError, KeyError, TypeError, FarmError):
            raise FarmError(f"The data file '{path}' is damaged. Fix or rename it.") from None
        return farm


# -------------------------------------------------------- ReportGenerator
class ReportGenerator:
    """Builds summaries from a Farm and saves them as .txt or .csv."""

    def __init__(self, farm):
        self._farm = farm

    def report(self, title, year=None, month=None):
        """Profit table. Give a year (and month) to count only that period."""
        if month is not None and not 1 <= month <= 12:
            raise FarmError("Month must be between 1 and 12.")
        if year is not None and not 1900 <= year <= 2200:
            raise FarmError("Please use a year between 1900 and 2200.")

        def inside(t):
            return ((year is None or t.date.year == year) and
                    (month is None or t.date.month == month))

        lines = [title, "-" * 70]
        total_in = total_out = 0
        for e in self._farm.enterprises:
            income = sum(t.amount for t in e.transactions if t.kind == "sale" and inside(t))
            spent = sum(t.amount for t in e.transactions if t.kind == "expense" and inside(t))
            lines.append(f"{e.name:<22} sales {income:>12,.2f}  costs {spent:>12,.2f}  "
                         f"profit {income - spent:>12,.2f}")
            total_in += income
            total_out += spent
        lines.append("-" * 70)
        lines.append(f"{'FARM TOTAL':<22} sales {total_in:>12,.2f}  costs {total_out:>12,.2f}  "
                     f"profit {total_in - total_out:>12,.2f}")
        for item in self._farm.low_stock_items():
            lines.append(f"WARNING: {item}")
        return "\n".join(lines)

    def save_text(self, text, path="report.txt"):
        with open(path, "w") as file:
            file.write(text + "\n")

    def export_csv(self, path="transactions.csv"):
        with open(path, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["date", "enterprise", "type", "description", "amount"])
            for e in self._farm.enterprises:
                for t in e.transactions:
                    writer.writerow([t.date, e.name, t.kind, t.description, t.amount])


# ------------------------------------------------------------------- Menu
MENU = """
=========== FarmTrack ===========
 1. Add enterprise        7. Add inventory item
 2. View enterprises      8. Use / restock inventory
 3. Update size           9. View inventory
 4. Remove enterprise    10. Upcoming tasks
 5. Record expense       11. Reports
 6. Record sale          12. Record harvest / production
 0. Save and exit
================================="""


def ask(prompt):
    return input(prompt).strip()


def ask_number(prompt):
    try:
        number = float(ask(prompt))
    except ValueError:
        raise FarmError("Please type a number.") from None
    if not math.isfinite(number):
        raise FarmError("Please type a real number.")
    return number


class FarmTrackApp:
    def __init__(self, farm):
        self.farm = farm

    def pick(self):
        names = ", ".join(e.name for e in self.farm.enterprises) or "(none yet)"
        print("Enterprises:", names)
        return self.farm.get_enterprise(ask("Enterprise name: "))

    def add_enterprise(self):
        names = list(TYPES)
        for number, name in enumerate(names, 1):
            print(f"  {number}. {name}")
        choice = int(ask_number("Type number: "))
        if not 1 <= choice <= len(names):
            raise FarmError("Pick one of the numbers listed.")
        kind = TYPES[names[choice - 1]]
        name = ask("Name (e.g. Maize Plot A): ")
        size = ask_number("Acres (crops) or number of animals (livestock): ")
        start = ask("Start date YYYY-MM-DD (blank = today): ")
        self.farm.add_enterprise(kind(name, size, start))
        print("Added.")

    def view_enterprises(self):
        for e in self.farm.enterprises:
            print(e)            # POLYMORPHISM again: each type describes itself
        if not self.farm.enterprises:
            print("No enterprises yet.")
        else:
            print(f"Whole farm profit: KES {self.farm.total_profit():,.2f}")

    def update_size(self):
        self.pick().update_size(ask_number("New size: "))
        print("Updated.")

    def remove_enterprise(self):
        e = self.pick()
        if ask(f"Remove '{e.name}' and all its records? (y/n): ").lower() == "y":
            self.farm.remove_enterprise(e.name)
            print("Removed.")

    def record_expense(self):
        e = self.pick()
        e.add_expense(ask_number("Amount (KES): "), ask("What for? "), ask("Date (blank = today): "))
        print("Expense recorded.")

    def record_sale(self):
        e = self.pick()
        e.add_sale(ask_number("Amount (KES): "), ask("What was sold? "), ask("Date (blank = today): "))
        print("Sale recorded.")

    def record_output(self):
        e = self.pick()
        e.record_output(ask_number(f"Quantity ({e.unit}): "))
        print(e.describe())

    def add_item(self):
        self.farm.add_item(InventoryItem(
            ask("Item name: "), ask_number("Opening quantity: "), ask("Unit (kg, litres, bags): "),
            ask_number("Warn me when stock falls to: ")))
        print("Item added.")

    def stock_action(self):
        item = self.farm.get_item(ask("Item name: "))
        action = ask("(u)se or (r)estock? ").lower()
        amount = ask_number(f"Quantity ({item.unit}): ")
        if action == "u":
            item.use(amount)
        elif action == "r":
            item.restock(amount)
        else:
            raise FarmError("Type u or r.")
        print(item)

    def view_inventory(self):
        for item in self.farm.inventory:
            print(item)
        if not self.farm.inventory:
            print("Inventory is empty.")

    def show_tasks(self):
        days = int(ask_number("Look how many days ahead? "))
        if not 0 <= days <= 3650:
            raise FarmError("Choose between 0 and 3650 days.")
        tasks = self.farm.upcoming_tasks(days)
        for when, text in tasks:
            print(f"  {when}  {text}")
        if not tasks:
            print("No tasks due.")

    def reports(self):
        generator = ReportGenerator(self.farm)
        choice = ask("(a) profit summary  (b) monthly report  (c) export CSV: ").lower()
        if choice == "c":
            generator.export_csv()
            print("Saved transactions.csv")
            return
        if choice == "a":
            text = generator.report("PROFIT SUMMARY (all time)")
        elif choice == "b":
            year, month = int(ask_number("Year: ")), int(ask_number("Month 1-12: "))
            text = generator.report(f"MONTHLY REPORT {year}-{month:02d}", year, month)
        else:
            raise FarmError("Type a, b or c.")
        print(text)
        if ask("Save as report.txt? (y/n): ").lower() == "y":
            generator.save_text(text)
            print("Saved report.txt")

    def run(self):
        actions = {"1": self.add_enterprise, "2": self.view_enterprises, "3": self.update_size,
                   "4": self.remove_enterprise, "5": self.record_expense, "6": self.record_sale,
                   "7": self.add_item, "8": self.stock_action, "9": self.view_inventory,
                   "10": self.show_tasks, "11": self.reports, "12": self.record_output}
        for item in self.farm.low_stock_items():
            print("WARNING low stock:", item)
        for when, text in self.farm.upcoming_tasks(3):
            print(f"REMINDER: {when} {text}")
        while True:
            print(MENU)
            try:
                choice = ask("Choose: ")
            except EOFError:
                choice = "0"
            if choice == "0":
                self.farm.save()
                print("Saved. Goodbye!")
                return
            if choice not in actions:
                print("Please choose a number from the menu.")
                continue
            try:
                actions[choice]()
                self.farm.save()           # save after every change
            except FarmError as error:
                print("Error:", error)     # a friendly message, never a crash


if __name__ == "__main__":
    try:
        FarmTrackApp(Farm.load()).run()
    except FarmError as error:
        print("Error:", error)