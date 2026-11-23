"""Fill farmtrack_data.json with realistic sample data for your demo.

    python seed_demo.py     (then)     python main.py
"""
from __future__ import annotations

from datetime import date, timedelta

from farmtrack.enterprises import DairyCow, Maize, Poultry, Tomatoes
from farmtrack.farm import Farm
from farmtrack.models import InventoryItem
from farmtrack.storage import JsonStorage


def build_demo_farm(today: date | None = None) -> Farm:
    today = today or date.today()
    ago = lambda days: today - timedelta(days=days)

    farm = Farm("Onduso Family Farm")

    maize = farm.add_enterprise(Maize("Maize Plot A", 2, ago(60)))
    maize.record_expense(12000, "Certified seed", "seed", ago(60))
    maize.record_expense(8500, "DAP fertiliser", "inputs", ago(58))
    maize.record_expense(3000, "Weeding labour", "labour", ago(30))

    tomatoes = farm.add_enterprise(Tomatoes("Tomato Greenhouse", 0.25, ago(40)))
    tomatoes.record_expense(6000, "Seedlings", "seed", ago(40))
    tomatoes.record_expense(2500, "Fungicide", "chemical", ago(26))
    tomatoes.record_output(180, ago(2))
    tomatoes.record_sale(9000, "Sold to market", when=ago(1))

    cows = farm.add_enterprise(DairyCow("Dairy Herd", 4, ago(200)))
    cows.record_expense(15000, "Napier grass and feed", "feed", ago(20))
    for day in range(10, 0, -1):
        cows.record_output(38, ago(day))
    cows.record_sale(28000, "Milk to cooperative", when=ago(5))

    hens = farm.add_enterprise(Poultry("Layer Flock", 50, ago(85)))
    hens.record_expense(9000, "Layers mash", "feed", ago(30))
    hens.record_output(900, ago(3))
    hens.record_sale(5400, "Eggs (tray sales)", when=ago(2))

    farm.add_inventory_item(InventoryItem("DAP fertiliser", "fertiliser", 40, "kg", 20))
    farm.add_inventory_item(InventoryItem("Layers mash", "feed", 15, "kg", 25))
    farm.add_inventory_item(InventoryItem("Fungicide", "chemical", 3, "litres", 1))
    return farm


if __name__ == "__main__":
    JsonStorage("farmtrack_data.json").save(build_demo_farm())
    print("Demo data written to farmtrack_data.json")
