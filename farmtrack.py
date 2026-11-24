"""FarmTrack - a small farm management system (one file).

The four main OOP concepts (look for the CAPITAL WORDS in the comments):
  ENCAPSULATION  data is private and changes only through checked methods
  ABSTRACTION    Enterprise is abstract: it cannot be created directly
  INHERITANCE    Enterprise -> Crop -> Maize ...   Enterprise -> Livestock -> Poultry ...
  POLYMORPHISM   the same method call behaves differently for each type
"""
import math, os, pickle
from abc import ABC, abstractmethod
from datetime import date, timedelta

DATA_FILE = "farm_data.pkl"


def positive(value, what):
    """Return the number if it is real and above zero, otherwise raise an error."""
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{what} must be greater than zero.")
    return value


def to_date(text):
    """'2026-03-15' -> a date. Blank means today."""
    try:
        d = date.fromisoformat(text) if text else date.today()
    except ValueError:
        raise ValueError("Date must look like 2026-03-15.") from None
    if not 1900 <= d.year <= 2200:
        raise ValueError("Please use a year between 1900 and 2200.")
    return d


# ---------------------------------------------------------- InventoryItem
class InventoryItem:
    """ENCAPSULATION: _quantity is private. It can only be changed by use()
    and restock(), and both check the rules first, so stock can never go
    negative. Outside code can read item.quantity but cannot set it."""

    def __init__(self, name, quantity, warn_at):
        if not name.strip() or quantity < 0 or warn_at < 0:
            raise ValueError("An item needs a name and cannot have negative amounts.")
        self._name = name.strip()
        self._quantity = quantity
        self._warn_at = warn_at

    @property
    def name(self):
        return self._name

    @property
    def quantity(self):              # read-only: "item.quantity = 5" is an error
        return self._quantity

    @property
    def is_low(self):
        return self._quantity <= self._warn_at

    def use(self, amount):
        if positive(amount, "Amount") > self._quantity:
            raise ValueError(f"Only {self._quantity:g} of {self._name} left.")
        self._quantity -= amount

    def restock(self, amount):
        self._quantity += positive(amount, "Amount")

    def __str__(self):
        return f"{self._name}: {self._quantity:g}" + ("   <-- LOW STOCK" if self.is_low else "")


# ------------------------------------------------------------- Enterprise
class Enterprise(ABC):
    """ABSTRACTION: the parent of everything the farm produces. It holds the
    shared data and code, and DECLARES two methods that every child must
    write for itself. Because of that, Enterprise(...) cannot be created."""

    unit = ""                        # what output is counted in (set by children)

    def __init__(self, name, size, start_date=None):
        if not name.strip():
            raise ValueError("Name cannot be empty.")
        self._name = name.strip()    # ENCAPSULATION: private data
        self._size = self._check_size(size)
        self._start = to_date(start_date)
        self._output = 0
        self._records = []           # (kind, amount, note) for every expense/sale

    @property
    def name(self):
        return self._name

    # --- shared code: every child INHERITS these exactly as written
    def _check_size(self, size):
        return positive(size, "Size")

    def add_expense(self, amount, note):
        self._records.append(("expense", positive(amount, "Amount"), note))

    def add_sale(self, amount, note):
        self._records.append(("sale", positive(amount, "Amount"), note))

    def record_output(self, quantity):
        self._output += positive(quantity, "Quantity")

    def profit(self):
        return sum(a if kind == "sale" else -a for kind, a, _ in self._records)

    def _repeat(self, label, every_days, today, last_day, until=None):
        """Helper: a reminder that repeats every N days after the start date."""
        tasks, due = [], self._start + timedelta(days=every_days)
        while due <= last_day and (until is None or due < until):
            if due >= today:
                tasks.append((due, f"{label} {self._name}"))
            due += timedelta(days=every_days)
        return tasks

    # --- the ABSTRACT part: every child MUST write these two
    @abstractmethod
    def get_upcoming_tasks(self, days_ahead, today):
        """Return a list of (date, text) reminders."""

    @abstractmethod
    def describe(self):
        """Return a one-line description."""

    def __str__(self):
        return f"{self.describe()} | profit: KES {self.profit():,.2f}"


# ------------------------------------------------------------------ Crops
class Crop(Enterprise):
    """INHERITANCE: a Crop IS an Enterprise. It gets all the shared code above
    and writes its own version of the two abstract methods."""

    unit = "kg"
    growth_days = 100                # every real crop below sets its own numbers
    spray_every = 30

    def harvest_date(self):
        return self._start + timedelta(days=self.growth_days)

    def get_upcoming_tasks(self, days_ahead, today):
        last_day = today + timedelta(days=days_ahead)
        tasks = self._repeat("Spray", self.spray_every, today, last_day, until=self.harvest_date())
        if today <= self._start <= last_day:
            tasks.append((self._start, f"Plant {self._name}"))
        if self._output == 0 and today <= self.harvest_date() <= last_day:
            tasks.append((self.harvest_date(), f"Harvest {self._name}"))
        return sorted(tasks)

    def describe(self):
        return (f"[Crop] {self._name}, {self._size:g} acres, {self._output:g} kg "
                f"harvested, harvest due {self.harvest_date()}")


class Maize(Crop):                   # INHERITANCE again: a crop is just two numbers
    growth_days, spray_every = 120, 30


class Beans(Crop):
    growth_days, spray_every = 90, 21


class Tomatoes(Crop):
    growth_days, spray_every = 90, 14


# -------------------------------------------------------------- Livestock
class Livestock(Enterprise):
    """A group of animals: also an Enterprise, with its own tasks."""

    vaccinate_every = 90

    def _check_size(self, size):     # OVERRIDES the parent: animals come in whole numbers
        if positive(size, "Number of animals") != int(size):
            raise ValueError("Number of animals must be a whole number.")
        return int(size)

    def get_upcoming_tasks(self, days_ahead, today):
        last_day = today + timedelta(days=days_ahead)
        return sorted(self._repeat("Vaccinate", self.vaccinate_every, today, last_day))

    def describe(self):
        return f"[Livestock] {self._name}, {self._size} animals, {self._output:g} {self.unit} produced"


class DairyCow(Livestock):
    unit, vaccinate_every = "litres", 180

    def get_upcoming_tasks(self, days_ahead, today):
        # OVERRIDE + EXTEND: take the parent's tasks, then add one more kind.
        last_day = today + timedelta(days=days_ahead)
        extra = self._repeat("Deworm", 120, today, last_day)
        return sorted(super().get_upcoming_tasks(days_ahead, today) + extra)


class Poultry(Livestock):
    unit, vaccinate_every = "eggs", 90


TYPES = {"Maize": Maize, "Beans": Beans, "Tomatoes": Tomatoes,
         "DairyCow": DairyCow, "Poultry": Poultry}


# ------------------------------------------------------------------- Menu
MENU = """
============== FarmTrack ==============
 1. Add enterprise       6. Add inventory item
 2. View enterprises     7. Use / restock inventory
 3. Record expense       8. View inventory
 4. Record sale          9. Upcoming tasks
 5. Record harvest       0. Save and exit
======================================="""


def ask(prompt):
    return input(prompt).strip()


def ask_number(prompt):
    try:
        number = float(ask(prompt))
    except ValueError:
        raise ValueError("Please type a number.") from None
    if not math.isfinite(number):
        raise ValueError("Please type a real number.")
    return number


class FarmTrackApp:
    def __init__(self):
        self.enterprises = []        # Crop and Livestock objects, mixed together
        self.items = []              # InventoryItem objects
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "rb") as file:
                    self.enterprises, self.items = pickle.load(file)
            except Exception:
                raise ValueError(f"'{DATA_FILE}' is damaged. Fix or rename it.") from None

    def save(self):
        with open(DATA_FILE, "wb") as file:
            pickle.dump((self.enterprises, self.items), file)

    def load_sample_data(self):
        """Premade records for demonstrations. Start dates are worked out from
        today, so there are always real upcoming tasks to show."""
        def ago(days):
            return (date.today() - timedelta(days=days)).isoformat()

        maize = Maize("Maize Plot A", 2, ago(60))
        maize.add_expense(12000, "Certified seed")
        maize.add_expense(8500, "DAP fertiliser")
        maize.add_expense(3000, "Weeding labour")

        tomatoes = Tomatoes("Tomato Greenhouse", 0.25, ago(40))
        tomatoes.add_expense(6000, "Seedlings")
        tomatoes.add_expense(2500, "Fungicide")
        tomatoes.record_output(180)
        tomatoes.add_sale(15000, "Sold at the market")

        cows = DairyCow("Dairy Herd", 4, ago(200))
        cows.add_expense(15000, "Napier grass and feed")
        cows.record_output(380)
        cows.add_sale(28000, "Milk to the cooperative")

        hens = Poultry("Layer Flock", 50, ago(85))
        hens.add_expense(9000, "Layers mash")
        hens.record_output(900)
        hens.add_sale(14400, "Egg tray sales")

        self.enterprises = [maize, tomatoes, cows, hens]
        self.items = [InventoryItem("DAP fertiliser (kg)", 40, 20),
                      InventoryItem("Layers mash (kg)", 15, 25),      # below its warning level
                      InventoryItem("Fungicide (litres)", 3, 1)]
        self.save()

    def load_sample_data(self):
        """Premade records for demonstrations. Start dates are worked out from
        today, so there are always real upcoming tasks to show."""
        def ago(days):
            return (date.today() - timedelta(days=days)).isoformat()

        maize = Maize("Maize Plot A", 2, ago(60))
        maize.add_expense(12000, "Certified seed")
        maize.add_expense(8500, "DAP fertiliser")
        maize.add_expense(3000, "Weeding labour")

        tomatoes = Tomatoes("Tomato Greenhouse", 0.25, ago(40))
        tomatoes.add_expense(6000, "Seedlings")
        tomatoes.add_expense(2500, "Fungicide")
        tomatoes.record_output(180)
        tomatoes.add_sale(15000, "Sold at the market")

        cows = DairyCow("Dairy Herd", 4, ago(200))
        cows.add_expense(15000, "Napier grass and feed")
        cows.record_output(380)
        cows.add_sale(28000, "Milk to the cooperative")

        hens = Poultry("Layer Flock", 50, ago(85))
        hens.add_expense(9000, "Layers mash")
        hens.record_output(900)
        hens.add_sale(14400, "Egg tray sales")

        self.enterprises = [maize, tomatoes, cows, hens]
        self.items = [InventoryItem("DAP fertiliser (kg)", 40, 20),
                      InventoryItem("Layers mash (kg)", 15, 25),      # below its warning level
                      InventoryItem("Fungicide (litres)", 3, 1)]
        self.save()

    @staticmethod
    def find(things, name):
        for thing in things:
            if thing.name.lower() == name.strip().lower():
                return thing
        raise ValueError(f"'{name}' was not found.")

    @staticmethod
    def add(things, new):
        if any(t.name.lower() == new.name.lower() for t in things):
            raise ValueError(f"'{new.name}' already exists.")
        things.append(new)

    def pick(self):
        print("Enterprises:", ", ".join(e.name for e in self.enterprises) or "(none yet)")
        return self.find(self.enterprises, ask("Enterprise name: "))

    def add_enterprise(self):
        for number, name in enumerate(TYPES, 1):
            print(f"  {number}. {name}")
        choice = int(ask_number("Type number: "))
        if not 1 <= choice <= len(TYPES):
            raise ValueError("Pick one of the numbers listed.")
        kind = list(TYPES.values())[choice - 1]
        self.add(self.enterprises, kind(ask("Name (e.g. Maize Plot A): "),
                                        ask_number("Acres (crops) or number of animals: "),
                                        ask("Start date YYYY-MM-DD (blank = today): ")))

    def view_enterprises(self):
        for e in self.enterprises:
            print(e)                 # POLYMORPHISM: each type describes itself its own way
        print(f"Whole farm profit: KES {sum(e.profit() for e in self.enterprises):,.2f}")

    def record_expense(self):
        self.pick().add_expense(ask_number("Amount (KES): "), ask("What for? "))

    def record_sale(self):
        self.pick().add_sale(ask_number("Amount (KES): "), ask("What was sold? "))

    def record_harvest(self):
        e = self.pick()
        e.record_output(ask_number(f"Quantity ({e.unit}): "))   # kg, litres or eggs

    def add_item(self):
        self.add(self.items, InventoryItem(ask("Item name (e.g. DAP kg): "),
                                           ask_number("Opening quantity: "),
                                           ask_number("Warn me when stock falls to: ")))

    def use_or_restock(self):
        item = self.find(self.items, ask("Item name: "))
        action = ask("(u)se or (r)estock? ").lower()
        amount = ask_number("Quantity: ")
        if action == "u":
            item.use(amount)
        elif action == "r":
            item.restock(amount)
        else:
            raise ValueError("Type u or r.")
        print(item)

    def view_inventory(self):
        for item in self.items:
            print(item)
        if not self.items:
            print("Inventory is empty.")

    def upcoming_tasks(self):
        days = int(ask_number("Look how many days ahead? "))
        if not 0 <= days <= 3650:
            raise ValueError("Choose between 0 and 3650 days.")
        found = []
        for e in self.enterprises:   # POLYMORPHISM: same call, different answers
            found += e.get_upcoming_tasks(days, date.today())
        for when, text in sorted(found):
            print(" ", when, text)
        if not found:
            print("No tasks due.")

    def run(self):
        if not self.enterprises:        # nothing recorded yet: start with the sample data
            self.load_sample_data()
        actions = {"1": self.add_enterprise, "2": self.view_enterprises,
                   "3": self.record_expense, "4": self.record_sale,
                   "5": self.record_harvest, "6": self.add_item,
                   "7": self.use_or_restock, "8": self.view_inventory,
                   "9": self.upcoming_tasks}
        for item in self.items:
            if item.is_low:
                print("WARNING low stock:", item)
        while True:
            print(MENU)
            choice = ask("Choose: ")
            if choice == "0":
                break
            if choice not in actions:
                print("Please choose a number from the menu.")
                continue
            try:
                actions[choice]()
                self.save()          # saved after every change
            except (ValueError, OverflowError) as error:
                print("Error:", error)
        self.save()
        print("Saved. Goodbye!")


if __name__ == "__main__":
    try:
        FarmTrackApp().run()
    except ValueError as error:
        print("Error:", error)
    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye! (your last change was already saved)")