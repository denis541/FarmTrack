# FarmTrack

A command-line farm management system for small-scale farmers, written in Python
to demonstrate object-oriented programming.

## Run it
```
python main.py            # start the app (creates farmtrack_data.json on first save)
python seed_demo.py       # OPTIONAL: fill it with sample data first, for demos
python -m unittest -v     # run the 40 automated tests
```
Requires Python 3.9+ and nothing else (standard library only).

## Project layout
```
main.py                  entry point
seed_demo.py             sample data for demonstrations
farmtrack/
  exceptions.py          custom exception classes
  validators.py          reusable input checks
  formatting.py          money formatting
  models.py              Transaction, InventoryItem
  enterprises.py         Enterprise (abstract) -> Crop/Livestock -> Maize, Beans, ...
  farm.py                Farm (holds everything: composition)
  storage.py             JsonStorage (save/load)
  reports.py             ReportGenerator (summaries, .txt, .csv)
  app.py                 menu-driven interface
tests/test_farmtrack.py  40 unit tests
EXPLANATION.md           how every part works (read this before your demo)
```

## Add a new crop in 3 lines
```python
class Sorghum(Crop):
    growth_days = 110
    spray_interval_days = 25
```
It automatically appears in the menu, gets planting/spraying/harvest reminders,
profit tracking, and can be saved and loaded. Nothing else changes.
