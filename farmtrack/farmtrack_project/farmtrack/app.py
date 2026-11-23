"""The menu-driven command-line interface.

The app never touches the data directly: it asks the Farm / Enterprise
objects to do the work, and shows any FarmTrackError as a friendly message.
`input_fn` and `print_fn` are injected so the tests can drive the whole menu
with scripted answers (no real keyboard needed).
"""
from __future__ import annotations

from datetime import date

from farmtrack.enterprises import Enterprise
from farmtrack.exceptions import FarmTrackError, InvalidInputError, ItemNotFoundError
from farmtrack.formatting import money
from farmtrack.models import InventoryItem
from farmtrack.reports import ReportGenerator
from farmtrack.validators import to_date

MENU = """
================ FarmTrack ================
 1. Add enterprise            7. Add inventory item
 2. View enterprises          8. Use / restock inventory
 3. Update enterprise size    9. View inventory
 4. Remove enterprise        10. Upcoming tasks
 5. Record expense           11. Reports
 6. Record sale              12. Record harvest / production
 0. Save and exit
==========================================="""


class FarmTrackApp:
    def __init__(self, storage, input_fn=input, print_fn=print, reports_dir="reports"):
        self._storage = storage
        self._input = input_fn
        self._say = print_fn
        self._reports_dir = reports_dir
        self._farm = storage.load()
        self._actions = {
            "1": self._add_enterprise, "2": self._view_enterprises,
            "3": self._update_size, "4": self._remove_enterprise,
            "5": self._record_expense, "6": self._record_sale,
            "7": self._add_item, "8": self._stock_action,
            "9": self._view_inventory, "10": self._show_tasks,
            "11": self._reports, "12": self._record_output,
        }

    @property
    def farm(self):
        return self._farm

    # ---- main loop --------------------------------------------------------
    def run(self) -> None:
        self._say(f"Welcome to FarmTrack - {self._farm.name}")
        self._show_alerts()
        while True:
            self._say(MENU)
            try:
                choice = self._ask("Choose an option: ")
            except EOFError:          # input stream ended: exit safely
                choice = "0"
            if choice == "0":
                try:
                    self._storage.save(self._farm)
                    self._say("Data saved. Goodbye!")
                except FarmTrackError as error:
                    self._say(f"Error: {error}")
                return
            action = self._actions.get(choice)
            if action is None:
                self._say("Please choose a number from the menu.")
                continue
            try:
                action()
                self._storage.save(self._farm)       # auto-save after every change
            except FarmTrackError as error:
                self._say(f"Error: {error}")

    def _show_alerts(self) -> None:
        for item in self._farm.low_stock_items():
            self._say(f"WARNING low stock: {item}")
        for task in self._farm.upcoming_tasks(days_ahead=3):
            self._say(f"REMINDER (next 3 days): {task}")

    # ---- input helpers (all raise InvalidInputError on bad input) ---------
    def _ask(self, prompt: str) -> str:
        return self._input(prompt).strip()

    def _ask_number(self, prompt: str, default=None) -> float:
        text = self._ask(prompt)
        if not text and default is not None:
            return default
        try:
            return float(text)
        except ValueError:
            raise InvalidInputError("Please enter a number.") from None

    def _ask_date(self, prompt: str):
        text = self._ask(prompt + " (YYYY-MM-DD, blank = today): ")
        return to_date(text) if text else None

    def _pick_enterprise(self) -> Enterprise:
        if not self._farm.enterprises:
            raise ItemNotFoundError("There are no enterprises yet - add one first.")
        self._say("Enterprises: " + ", ".join(e.name for e in self._farm.enterprises))
        return self._farm.get_enterprise(self._ask("Enterprise name: "))

    # ---- actions ----------------------------------------------------------
    def _add_enterprise(self) -> None:
        types = list(Enterprise.available_types().items())
        for number, (type_name, _) in enumerate(types, 1):
            self._say(f"  {number}. {type_name}")
        index = self._ask_number("Type number: ")
        if index != int(index) or not 1 <= index <= len(types):
            raise InvalidInputError("Pick one of the numbers listed.")
        _, enterprise_class = types[int(index) - 1]
        name = self._ask("Name (e.g. 'Maize Plot A'): ")
        size = self._ask_number(f"{enterprise_class.size_label}: ")
        start = self._ask_date("Start date")
        enterprise = enterprise_class(name, size, start)   # polymorphic construction
        self._farm.add_enterprise(enterprise)
        self._say(f"Added: {enterprise}")

    def _view_enterprises(self) -> None:
        if not self._farm.enterprises:
            self._say("No enterprises yet.")
        for enterprise in self._farm.enterprises:
            self._say(str(enterprise))
            self._say("    " + enterprise.production_summary())

    def _update_size(self) -> None:
        enterprise = self._pick_enterprise()
        enterprise.update_size(self._ask_number(f"New value ({enterprise.size_label}): "))
        self._say(f"Updated: {enterprise}")

    def _remove_enterprise(self) -> None:
        enterprise = self._pick_enterprise()
        if self._ask(f"Really remove '{enterprise.name}' and its records? (y/n): ").lower() == "y":
            self._farm.remove_enterprise(enterprise.name)
            self._say("Removed.")
        else:
            self._say("Cancelled.")

    def _record_expense(self) -> None:
        enterprise = self._pick_enterprise()
        amount = self._ask_number("Amount (KES): ")
        description = self._ask("What was it for? ")
        category = self._ask("Category (blank = general): ") or "general"
        enterprise.record_expense(amount, description, category, self._ask_date("Date"))
        self._say("Expense recorded.")

    def _record_sale(self) -> None:
        enterprise = self._pick_enterprise()
        amount = self._ask_number("Amount (KES): ")
        description = self._ask("What was sold? ")
        enterprise.record_sale(amount, description, when=self._ask_date("Date"))
        self._say("Sale recorded.")

    def _record_output(self) -> None:
        enterprise = self._pick_enterprise()
        quantity = self._ask_number(f"Quantity ({enterprise.production_unit}): ")
        enterprise.record_output(quantity, self._ask_date("Date"))
        self._say(enterprise.production_summary())

    def _add_item(self) -> None:
        name = self._ask("Item name (e.g. DAP fertiliser): ")
        category = self._ask("Category (seed/fertiliser/feed/chemical): ")
        unit = self._ask("Unit (kg, litres, bags): ")
        quantity = self._ask_number("Opening quantity: ")
        threshold = self._ask_number("Warn me when stock falls to (blank = 0): ", default=0)
        self._farm.add_inventory_item(InventoryItem(name, category, quantity, unit, threshold))
        self._say("Item added.")

    def _stock_action(self) -> None:
        action = self._ask("(u)se or (r)estock? ").lower()
        item = self._farm.get_item(self._ask("Item name: "))
        quantity = self._ask_number(f"Quantity ({item.unit}): ")
        if action == "r":
            item.restock(quantity)
        elif action == "u":
            enterprise_name = self._ask("Charge to enterprise (blank = none): ")
            cost = self._ask_number("Cost of this stock used (blank = none): ",
                                    default=-1) if enterprise_name else None
            self._farm.use_input(item.name, quantity, enterprise_name or None,
                                 None if cost == -1 else cost)
        else:
            raise InvalidInputError("Type 'u' or 'r'.")
        self._say(str(item))

    def _view_inventory(self) -> None:
        if not self._farm.inventory:
            self._say("Inventory is empty.")
        for item in self._farm.inventory:
            self._say(str(item))

    def _show_tasks(self) -> None:
        days = int(self._ask_number("Look how many days ahead? (blank = 14): ", default=14))
        tasks = self._farm.upcoming_tasks(days)
        self._say(f"Tasks in the next {days} days:" if tasks else "No tasks due.")
        for task in tasks:
            self._say("  " + str(task))

    def _reports(self) -> None:
        generator = ReportGenerator(self._farm)
        self._say(" a. Profit summary   b. Monthly report   c. Seasonal report   d. Export CSV")
        choice = self._ask("Choose: ").lower()
        today = date.today()
        if choice == "a":
            text, name = generator.profit_summary(), "profit_summary"
        elif choice == "b":
            year = int(self._ask_number(f"Year (blank = {today.year}): ", default=today.year))
            month = int(self._ask_number(f"Month 1-12 (blank = {today.month}): ", default=today.month))
            text, name = generator.monthly_report(year, month), f"monthly_{year}_{month:02d}"
        elif choice == "c":
            start, end = to_date(self._ask("Season start (YYYY-MM-DD): ")), to_date(self._ask("Season end (YYYY-MM-DD): "))
            text, name = generator.seasonal_report(start, end), f"season_{start}_{end}"
        elif choice == "d":
            path = generator.export_csv(f"{self._reports_dir}/transactions.csv")
            self._say(f"Exported to {path}")
            return
        else:
            raise InvalidInputError("Choose a, b, c or d.")
        self._say(text)
        if self._ask("Save this report as a .txt file? (y/n): ").lower() == "y":
            self._say(f"Saved to {generator.export_txt(text, f'{self._reports_dir}/{name}.txt')}")
