"""Run all tests from the project folder:   python -m unittest -v"""
import csv
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from farmtrack.app import FarmTrackApp
from farmtrack.enterprises import (Beans, Crop, DairyCow, Enterprise, Livestock,
                                   Maize, Poultry, Task, Tomatoes)
from farmtrack.exceptions import (DuplicateItemError, FarmTrackError,
                                  InsufficientStockError, InvalidInputError,
                                  ItemNotFoundError, StorageError)
from farmtrack.farm import Farm
from farmtrack.formatting import money
from farmtrack.models import InventoryItem, Transaction
from farmtrack.reports import ReportGenerator
from farmtrack.storage import JsonStorage


# ---------------------------------------------------------------- ENCAPSULATION
class TestTransaction(unittest.TestCase):
    def test_valid_transaction(self):
        t = Transaction("expense", 500, "Seed", "seed", "2026-03-01")
        self.assertEqual(t.amount, 500)
        self.assertEqual(t.date, date(2026, 3, 1))

    def test_rejects_bad_values(self):
        for bad in (0, -5, "abc", None, True, float("nan")):
            with self.assertRaises(InvalidInputError, msg=f"amount={bad!r}"):
                Transaction("expense", bad, "x")
        with self.assertRaises(InvalidInputError):
            Transaction("gift", 10, "x")            # unknown kind
        with self.assertRaises(InvalidInputError):
            Transaction("sale", 10, "   ")          # blank description
        with self.assertRaises(InvalidInputError):
            Transaction("sale", 10, "x", when="01/03/2026")   # wrong date format

    def test_is_read_only(self):
        t = Transaction("sale", 100, "Milk")
        with self.assertRaises(AttributeError):
            t.amount = 999                           # no setter -> protected

    def test_round_trip(self):
        t = Transaction("sale", 100.5, "Milk", "dairy", "2026-04-02")
        copy = Transaction.from_dict(t.to_dict())
        self.assertEqual(copy.to_dict(), t.to_dict())


class TestInventoryItem(unittest.TestCase):
    def setUp(self):
        self.item = InventoryItem("DAP", "fertiliser", 10, "kg", low_stock_threshold=4)

    def test_use_and_restock(self):
        self.item.use(3)
        self.assertEqual(self.item.quantity, 7)
        self.item.restock(5)
        self.assertEqual(self.item.quantity, 12)

    def test_low_stock_flag(self):
        self.assertFalse(self.item.is_low)
        self.item.use(6)                             # 4 left == threshold
        self.assertTrue(self.item.is_low)
        self.assertIn("LOW STOCK", str(self.item))

    def test_cannot_use_more_than_stock(self):
        with self.assertRaises(InsufficientStockError):
            self.item.use(11)
        self.assertEqual(self.item.quantity, 10)     # unchanged after failure

    def test_negative_quantities_rejected(self):
        with self.assertRaises(InvalidInputError):
            self.item.use(-1)
        with self.assertRaises(InvalidInputError):
            self.item.restock(0)
        with self.assertRaises(InvalidInputError):
            InventoryItem("Seed", "seed", -5, "kg")

    def test_quantity_cannot_be_set_directly(self):
        with self.assertRaises(AttributeError):
            self.item.quantity = 500


class TestEnterpriseEncapsulation(unittest.TestCase):
    def test_transactions_cannot_be_tampered_with(self):
        m = Maize("Plot", 1, "2026-01-01")
        m.record_sale(100, "x")
        self.assertIsInstance(m.transactions, tuple)
        with self.assertRaises(AttributeError):
            m.transactions.append("fake")            # tuple has no append
        self.assertEqual(len(m.transactions), 1)

    def test_validation_on_construction(self):
        with self.assertRaises(InvalidInputError):
            Maize("", 1)
        with self.assertRaises(InvalidInputError):
            Maize("Plot", -2)
        with self.assertRaises(InvalidInputError):
            Poultry("Flock", 2.5)                    # animals must be whole
        with self.assertRaises(InvalidInputError):
            Poultry("Flock", 0)


# ------------------------------------------------- ABSTRACTION + INHERITANCE
class TestAbstractionAndInheritance(unittest.TestCase):
    def test_abstract_classes_cannot_be_created(self):
        for abstract in (Enterprise, Crop, Livestock):
            with self.assertRaises(TypeError, msg=abstract.__name__):
                abstract("x", 1)

    def test_inheritance_chain(self):
        maize, cow = Maize("M", 1), DairyCow("C", 2)
        self.assertIsInstance(maize, Crop)
        self.assertIsInstance(maize, Enterprise)
        self.assertIsInstance(cow, Livestock)
        self.assertNotIsInstance(maize, Livestock)
        self.assertEqual(Maize.__mro__[1:3], (Crop, Enterprise))

    def test_subclasses_reuse_inherited_behaviour(self):
        for enterprise in (Maize("M", 1), Beans("B", 1), Poultry("P", 5)):
            enterprise.record_sale(1000, "sale")
            enterprise.record_expense(400, "cost")
            self.assertEqual(enterprise.calculate_profit(), 600)   # one shared formula

    def test_concrete_types_registered_automatically(self):
        self.assertEqual(sorted(Enterprise.available_types()),
                         ["Beans", "DairyCow", "Maize", "Poultry", "Tomatoes"])


# ----------------------------------------------------------------- POLYMORPHISM
class TestPolymorphism(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 1, 1)
        self.farm = Farm()
        self.farm.add_enterprise(Maize("Maize", 2, "2026-01-01"))
        self.farm.add_enterprise(DairyCow("Cows", 3, "2026-01-01"))
        self.farm.add_enterprise(Poultry("Hens", 20, "2026-01-01"))

    def test_same_call_different_results(self):
        """One loop, one method name, three different behaviours."""
        summaries = {e.name: e.production_summary() for e in self.farm.enterprises}
        self.assertIn("kg harvested", summaries["Maize"])
        self.assertIn("litres", summaries["Cows"])
        self.assertIn("eggs", summaries["Hens"])

    def test_crop_tasks(self):
        maize = self.farm.get_enterprise("Maize")
        tasks = maize.get_upcoming_tasks(days_ahead=200, today=self.today)
        self.assertEqual([t.due_date for t in tasks],
                         [date(2026, 1, 1), date(2026, 1, 31), date(2026, 3, 2),
                          date(2026, 4, 1), date(2026, 5, 1)])
        self.assertEqual(tasks[0].description, "Plant")
        self.assertEqual(tasks[-1].description, "Harvest")

    def test_harvested_crop_has_no_harvest_reminder(self):
        maize = self.farm.get_enterprise("Maize")
        maize.record_output(500)
        tasks = maize.get_upcoming_tasks(days_ahead=200, today=self.today)
        self.assertFalse(any("Harvest" in t.description for t in tasks))

    def test_livestock_tasks_and_override(self):
        poultry = self.farm.get_enterprise("Hens").get_upcoming_tasks(100, self.today)
        self.assertEqual([t.description for t in poultry], ["Vaccination #1"])
        cow = self.farm.get_enterprise("Cows").get_upcoming_tasks(200, self.today)
        kinds = [t.description.split()[0] for t in cow]
        self.assertIn("Vaccination", kinds)
        self.assertIn("Deworming", kinds)            # added by DairyCow's override
        self.assertEqual(cow, sorted(cow))           # still in date order

    def test_farm_collects_tasks_from_every_type(self):
        tasks = self.farm.upcoming_tasks(days_ahead=200, today=self.today)
        self.assertTrue(all(isinstance(t, Task) for t in tasks))
        self.assertEqual({t.enterprise for t in tasks}, {"Maize", "Cows", "Hens"})
        self.assertEqual(tasks, sorted(tasks))

    def test_update_size_means_different_things(self):
        self.farm.get_enterprise("Maize").update_size(5)
        self.farm.get_enterprise("Cows").update_size(7)
        self.assertEqual(self.farm.get_enterprise("Maize").size_description, "5 acres")
        self.assertEqual(self.farm.get_enterprise("Cows").size_description, "7 animals")
        with self.assertRaises(InvalidInputError):
            self.farm.get_enterprise("Cows").update_size(2.5)

    def test_record_output(self):
        cows = self.farm.get_enterprise("Cows")
        cows.record_output(30, "2026-01-02")
        cows.record_output(32, "2026-01-03")
        self.assertEqual(cows.total_output, 62)
        with self.assertRaises(InvalidInputError):
            cows.record_output(-4)


# ------------------------------------------------------------------ COMPOSITION
class TestFarm(unittest.TestCase):
    def setUp(self):
        self.farm = Farm("Test Farm")
        self.farm.add_enterprise(Maize("Maize", 1, "2026-01-01"))
        self.farm.add_inventory_item(InventoryItem("DAP", "fertiliser", 50, "kg", 10))

    def test_duplicates_and_missing(self):
        with self.assertRaises(DuplicateItemError):
            self.farm.add_enterprise(Beans("maize", 1))        # case-insensitive
        with self.assertRaises(DuplicateItemError):
            self.farm.add_inventory_item(InventoryItem("dap", "x", 1, "kg"))
        with self.assertRaises(ItemNotFoundError):
            self.farm.get_enterprise("Ghost")
        with self.assertRaises(ItemNotFoundError):
            self.farm.get_item("Ghost")

    def test_only_correct_types_accepted(self):
        with self.assertRaises(InvalidInputError):
            self.farm.add_enterprise("not an enterprise")

    def test_remove(self):
        self.farm.remove_enterprise("MAIZE")
        self.assertEqual(self.farm.enterprises, [])

    def test_use_input_charges_enterprise(self):
        self.farm.use_input("DAP", 20, "Maize", cost=3000)
        self.assertEqual(self.farm.get_item("DAP").quantity, 30)
        self.assertEqual(self.farm.get_enterprise("Maize").total_expenses, 3000)

    def test_use_input_is_all_or_nothing(self):
        with self.assertRaises(ItemNotFoundError):             # bad enterprise
            self.farm.use_input("DAP", 20, "Ghost", cost=100)
        with self.assertRaises(InvalidInputError):             # bad cost
            self.farm.use_input("DAP", 20, "Maize", cost=-5)
        with self.assertRaises(InsufficientStockError):        # too much stock
            self.farm.use_input("DAP", 500, "Maize", cost=100)
        self.assertEqual(self.farm.get_item("DAP").quantity, 50)
        self.assertEqual(self.farm.get_enterprise("Maize").total_expenses, 0)

    def test_low_stock_and_total_profit(self):
        self.farm.get_item("DAP").use(45)
        self.assertEqual([i.name for i in self.farm.low_stock_items()], ["DAP"])
        maize = self.farm.get_enterprise("Maize")
        maize.record_sale(1000, "s")
        maize.record_expense(300, "e")
        self.farm.add_enterprise(Beans("Beans", 1)).record_expense(200, "e")
        self.assertEqual(self.farm.total_profit(), 500)


# ------------------------------------------------------------------ PERSISTENCE
class TestStorage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "data.json"
        self.addCleanup(self.tmp.cleanup)

    def build(self):
        farm = Farm("Round Trip")
        maize = farm.add_enterprise(Maize("Maize", 2.5, "2026-01-01"))
        maize.record_expense(500, "Seed", "seed", "2026-01-02")
        maize.record_output(120)
        cows = farm.add_enterprise(DairyCow("Cows", 3, "2026-01-01"))
        cows.record_output(30, "2026-02-01")
        cows.record_sale(900, "Milk", when="2026-02-02")
        farm.add_inventory_item(InventoryItem("DAP", "fertiliser", 40, "kg", 10))
        return farm

    def test_round_trip_preserves_everything(self):
        original = self.build()
        storage = JsonStorage(self.path)
        storage.save(original)
        loaded = storage.load()
        self.assertEqual(loaded.to_dict(), original.to_dict())
        self.assertIsInstance(loaded.get_enterprise("Cows"), DairyCow)   # right subclass
        self.assertEqual(loaded.get_enterprise("Cows").total_output, 30)
        self.assertEqual(loaded.get_enterprise("Maize").total_output, 120)

    def test_missing_file_gives_empty_farm(self):
        self.assertEqual(JsonStorage(self.path).load().enterprises, [])

    def test_corrupted_files_raise_storage_error(self):
        for content in ("{not json", '{"enterprises": [{"type": "Unicorn"}]}',
                        '{"enterprises": [{"type": "Maize"}]}',
                        '{"enterprises": [{"type": "Maize", "name": "M", "area_acres": -1, "start_date": "2026-01-01"}]}'):
            self.path.write_text(content)
            with self.assertRaises(StorageError, msg=content):
                JsonStorage(self.path).load()

    def test_new_crop_needs_only_a_subclass(self):
        """The 'extensible design' claim from the concept note, proven."""
        class Sorghum(Crop):
            growth_days = 110
            spray_interval_days = 25

        farm = Farm()
        farm.add_enterprise(Sorghum("Sorghum Plot", 1, "2026-01-01"))
        storage = JsonStorage(self.path)
        storage.save(farm)
        self.assertIsInstance(storage.load().get_enterprise("Sorghum Plot"), Sorghum)
        self.assertIn("Sorghum", Enterprise.available_types())


# ---------------------------------------------------------------------- REPORTS
class TestReports(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.farm = Farm("Report Farm")
        maize = self.farm.add_enterprise(Maize("Maize", 1, "2026-01-01"))
        maize.record_expense(1000, "Seed", when="2026-03-05")
        maize.record_sale(5000, "Sale", when="2026-03-20")
        maize.record_expense(700, "Spray", when="2026-04-02")
        self.farm.add_inventory_item(InventoryItem("Feed", "feed", 2, "kg", 5))
        self.reports = ReportGenerator(self.farm)

    def test_monthly_report_only_counts_that_month(self):
        march = self.reports.monthly_report(2026, 3)
        self.assertIn("KES 5,000.00", march)
        self.assertIn("KES 1,000.00", march)
        self.assertNotIn("KES 700.00", march)
        self.assertIn("LOW STOCK", march)

    def test_profit_summary_and_negative_money(self):
        self.assertIn("KES 3,300.00", self.reports.profit_summary())
        self.assertEqual(money(-300), "-KES 300.00")

    def test_period_validation(self):
        with self.assertRaises(InvalidInputError):
            self.reports.monthly_report(2026, 13)
        with self.assertRaises(InvalidInputError):
            self.reports.seasonal_report("2026-05-01", "2026-04-01")

    def test_exports(self):
        csv_path = self.reports.export_csv(Path(self.tmp.name) / "out" / "t.csv")
        with open(csv_path, newline="") as handle:
            rows = list(csv.reader(handle))
        self.assertEqual(rows[0][0], "date")
        self.assertEqual(len(rows), 4)                         # header + 3 transactions
        self.assertEqual([r[0] for r in rows[1:]], sorted(r[0] for r in rows[1:]))
        txt_path = self.reports.export_txt("hello", Path(self.tmp.name) / "r.txt")
        self.assertEqual(txt_path.read_text().strip(), "hello")


# ------------------------------------------------------------- WHOLE-APP (menu)
class TestApp(unittest.TestCase):
    def run_app(self, answers, path):
        """Feed scripted answers to the real menu; return everything it printed."""
        answers = iter(answers)
        output = []
        app = FarmTrackApp(JsonStorage(path), input_fn=lambda prompt: next(answers),
                           print_fn=output.append,
                           reports_dir=str(Path(path).parent / "reports"))
        app.run()
        return "\n".join(output), app

    def test_full_session_and_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.json"
            text, app = self.run_app([
                "1", "1", "Maize Plot A", "2", "2026-01-01",       # add maize, 2 acres
                "5", "Maize Plot A", "1500", "Seed", "seed", "2026-01-02",
                "6", "Maize Plot A", "4000", "Green maize", "2026-03-01",
                "7", "DAP", "fertiliser", "kg", "10", "20",        # stock 10, warn at 20
                "12", "Maize Plot A", "300", "",                   # harvest 300 kg
                "11", "a", "n",                                    # profit summary
                "11", "d",                                         # CSV export
                "0"], path)
            self.assertIn("Added: [Crop] Maize Plot A", text)
            self.assertIn("KES 2,500.00", text)                    # 4000 - 1500
            self.assertIn("LOW STOCK", text)
            self.assertIn("300 kg harvested", text)
            self.assertTrue((Path(tmp) / "reports" / "transactions.csv").exists())
            # Restart the app: everything must still be there.
            text2, app2 = self.run_app(["0"], path)
            self.assertEqual(app2.farm.get_enterprise("Maize Plot A").total_income, 4000)
            self.assertIn("WARNING low stock", text2)

    def test_bad_input_never_crashes_the_menu(self):
        with tempfile.TemporaryDirectory() as tmp:
            text, app = self.run_app([
                "99",                                  # not a menu option
                "5",                                   # expense with no enterprises
                "1", "9",                              # invalid enterprise type number
                "1", "1", "Plot", "-3", "",            # negative area
                "1", "1", "Plot", "abc",               # non-numeric area
                "1", "1", "Plot", "1", "31-12-2026",   # bad date format
                "8", "r", "Ghost", "5",                # unknown inventory item
                "0"], Path(tmp) / "d.json")
            self.assertIn("Please choose a number", text)
            self.assertIn("no enterprises yet", text)
            self.assertIn("Pick one of the numbers", text)
            self.assertIn("greater than zero", text)
            self.assertIn("Please enter a number", text)
            self.assertIn("YYYY-MM-DD", text)
            self.assertIn("No inventory item", text)
            self.assertEqual(app.farm.enterprises, [])

    def test_ending_input_stream_saves_and_exits(self):
        with tempfile.TemporaryDirectory() as tmp:
            answers = iter(["1", "1", "Plot", "1", ""])      # then input runs out
            def fake_input(prompt):
                try:
                    return next(answers)
                except StopIteration:
                    raise EOFError
            app = FarmTrackApp(JsonStorage(Path(tmp) / "d.json"), fake_input, lambda *_: None)
            app.run()
            self.assertEqual(len(JsonStorage(Path(tmp) / "d.json").load().enterprises), 1)

    def test_demo_seed_is_valid(self):
        from seed_demo import build_demo_farm
        farm = build_demo_farm(date(2026, 11, 23))
        self.assertEqual(len(farm.enterprises), 4)
        self.assertTrue(farm.low_stock_items())
        self.assertTrue(farm.upcoming_tasks(30, date(2026, 11, 23)))


if __name__ == "__main__":
    unittest.main()
