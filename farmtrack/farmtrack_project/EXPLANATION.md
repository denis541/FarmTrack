# FarmTrack: how it works, part by part

Read this top to bottom once, then use sections 3 and 7 to prepare for your demo.

---------------------------------------------------------------------------

## 1. The big picture in one minute

FarmTrack models a farm with objects:

```
Farm  ----has many---->  Enterprise (abstract)
 |                          |-- Crop (abstract)        -> Maize, Beans, Tomatoes
 |                          `-- Livestock (abstract)   -> DairyCow, Poultry
 |                                  each Enterprise has many Transaction objects
 `----has many---->  InventoryItem

JsonStorage   saves / loads a Farm to a .json file
ReportGenerator   reads a Farm and produces text / csv reports
FarmTrackApp   the menu; it talks to the Farm, never edits data directly
```

A **class** is a blueprint (`Maize`). An **object** is one real thing built from it
(`Maize("Plot A", 2)`). Every concept below is just a rule about how these
blueprints relate to each other.

---------------------------------------------------------------------------

## 2. The six OOP concepts, one at a time

### 2.1 Classes and objects
`Transaction`, `InventoryItem`, `Farm`, `Maize` ... each bundles **data**
(attributes) with the **actions** that work on that data (methods).

```python
plot = Maize("Plot A", 2, "2026-01-01")     # create an object
plot.record_sale(4000, "Green maize")       # ask it to do something
print(plot.calculate_profit())              # ask it a question
```
`__init__` is the constructor: it runs when the object is created and sets up
its starting data.

### 2.2 Encapsulation: protect the data
**Idea:** an object guards its own data. Outside code may not change it freely;
it must go through methods that check the change is valid.

**In the code** (`models.py`, `InventoryItem`):
```python
self._quantity = non_negative_number(quantity, "Quantity")   # _ = "private, hands off"

@property
def quantity(self):          # read-only: you can LOOK at it...
    return self._quantity

def use(self, amount):       # ...but can only CHANGE it through a checked method
    amount = positive_number(amount, "Amount used")
    if amount > self._quantity:
        raise InsufficientStockError(...)
    self._quantity -= amount
```
What this buys you:
- `item.quantity = 500` -> **AttributeError** (there is no setter).
- `item.use(-5)` -> **InvalidInputError**. `item.use(9999)` -> **InsufficientStockError**.
- Stock can never go negative, whatever the rest of the program does.

Same idea elsewhere: `Transaction` has no setters at all (a recorded sale can't be
silently edited), and `Enterprise.transactions` returns a **tuple copy**, so outside
code can't `append` fake records.

*Demo sentence:* "The underscore marks data as private, properties give read-only
access, and the only way to change it is through methods that validate first."

### 2.3 Abstraction: define WHAT, hide HOW
**Idea:** `Enterprise` says "every enterprise can give you upcoming tasks, a
production summary, and record its output", without saying how. It is an
**abstract base class (ABC)**, so you can't create a plain `Enterprise`.

**In the code** (`enterprises.py`):
```python
class Enterprise(ABC):
    @abstractmethod
    def get_upcoming_tasks(self, days_ahead=30, today=None): ...
    @abstractmethod
    def production_summary(self): ...
```
Try it: `Enterprise("x")` or even `Crop("x", 1)` raises
`TypeError: Can't instantiate abstract class`. `Crop` is *also* abstract, because it
declares `growth_days` and `spray_interval_days` as abstract; only `Maize`,
`Beans`, `Tomatoes` fill them in, so only those can be created. This forces
every new crop to say how long it takes to grow: you can't forget.

### 2.4 Inheritance: reuse, don't repeat
**Idea:** a child class automatically gets everything its parent has.

```
Enterprise  (name, start date, transactions, profit, save/load)
  `-- Crop  (+ area, harvest tracking, spraying schedule)
        `-- Maize  (+ just two numbers: growth_days=120, spray_interval_days=30)
```
`Maize` is only 3 lines, yet it can record expenses, calculate profit, give
reminders and be saved to JSON, because all that is inherited from `Crop` and
`Enterprise`. Write once, reuse everywhere.

`super()` lets a child build on its parent instead of replacing it:
```python
class Crop(Enterprise):
    def __init__(self, name, area_acres, start_date=None):
        super().__init__(name, start_date)     # parent sets up name/date/transactions
        self._area_acres = ...                 # child adds its own data
```
**IS-A test:** a Maize *is a* Crop, a Crop *is an* Enterprise. (`isinstance(maize, Crop)` is True.)

### 2.5 Polymorphism: same call, different behaviour
**Idea:** you call the same method name on different kinds of objects, and each
responds in its own way.

**The best example in the project** (`farm.py`):
```python
def upcoming_tasks(self, days_ahead=14, today=None):
    tasks = []
    for enterprise in self._enterprises.values():
        tasks.extend(enterprise.get_upcoming_tasks(days_ahead, today))   # <-- one call
    return sorted(tasks)
```
This loop has no `if crop ... elif cow ...`. It doesn't know or care what kind of
enterprise it has. Yet:
- a `Maize` answers with *Plant / Spray / Harvest* dates,
- a `Poultry` flock answers with *Vaccination* dates,
- a `DairyCow` herd answers with *Vaccination + Deworming* dates.

Other places: `production_summary()` ("kg harvested" vs "litres recorded"),
`update_size()` (changes acres vs. head count), `record_output()`, and
`__str__`.

Two flavours to name in your demo:
1. **Method overriding.** `DairyCow.get_upcoming_tasks` replaces the `Livestock`
   version, but calls `super().get_upcoming_tasks(...)` first and then *adds* deworming.
2. **Via abstract methods.** Each subclass fills in the abstract methods differently.

**The payoff (Open/Closed principle):** to add Sorghum you write one subclass.
`Farm`, the menu and the reports need **zero changes**. There is a test for this
(`test_new_crop_needs_only_a_subclass`).

### 2.6 Composition: HAS-A instead of IS-A
**Idea:** build big objects out of smaller ones.

A `Farm` *has* enterprises and *has* inventory. It doesn't inherit from them
(a farm *is not* a crop). An `Enterprise` *has* `Transaction` objects. Rule of
thumb: if you can say "X is a kind of Y" use inheritance; if you can say "X
contains / owns Y" use composition.

---------------------------------------------------------------------------

## 3. Other OOP-related features I used (be ready to name them)

| Feature | Where | One-line explanation |
|---|---|---|
| **Custom exceptions** | `exceptions.py` | `InvalidInputError`, `InsufficientStockError`... all inherit `FarmTrackError`, so the menu catches one type and shows a friendly message instead of crashing. (Inheritance again!) |
| **Class attributes** | `Maize.growth_days = 120` | Data shared by the whole class, not per object. |
| **`@property`** | everywhere | Read-only access to private data (encapsulation). |
| **`@classmethod`** | `Transaction.from_dict` | A method that builds an object from saved data; receives the class (`cls`). |
| **`@staticmethod`** | `Enterprise.from_dict`, `_window` | A utility function that lives in the class but needs neither `self` nor `cls`. |
| **Dunder methods** | `__str__`, `__repr__`, `__init_subclass__` | `__str__` = how an object prints. `__init_subclass__` = runs whenever someone makes a subclass (see 4.3). |
| **`@dataclass`** | `Task` | Auto-generates `__init__`, `==`, ordering. `frozen=True` makes it immutable; `order=True` lets tasks sort by date. |
| **Validation module** | `validators.py` | Each rule written once, used by every class (DRY). |
| **Dependency injection** | `FarmTrackApp(storage, input_fn, print_fn)` | The app receives its tools instead of hard-wiring them, which is how the tests drive the full menu with scripted input. |

---------------------------------------------------------------------------

## 4. File-by-file walkthrough

### 4.1 `exceptions.py`
Five tiny classes. `FarmTrackError` is the parent; the others describe *what*
went wrong. No logic, just clear names.

### 4.2 `validators.py`
Functions like `positive_number(value)` and `to_date("2026-03-01")` that
either return a clean value or raise `InvalidInputError`. They also reject
`True`, `NaN` and `inf` (Python treats `True` as the number 1, which would be a
sneaky bug). Every class calls these instead of re-writing checks.

### 4.3 `enterprises.py` (the core file)
**`Task`**: a small immutable record: due date, description, enterprise name.

**`Enterprise` (abstract parent)** has three layers:
1. *Shared data* (private): `_name`, `_start_date`, `_transactions`.
2. *Shared behaviour* (concrete, inherited): `record_expense`, `record_sale`,
   `total_income`, `total_expenses`, `calculate_profit`, reports helpers, saving.
3. *Abstract contract*: `kind`, `production_unit`, `size_description`,
   `total_output`, `update_size`, `record_output`, `get_upcoming_tasks`,
   `production_summary`, `_create_from`.

**The registry trick (`__init_subclass__`).** Python calls this automatically each
time a class inherits from `Enterprise`, and it stores `{"Maize": Maize, ...}`.
When loading JSON, each saved enterprise has `"type": "Maize"`; `from_dict` looks up
that name to rebuild the right class. This is why new crops need no extra
wiring, and why the menu can list available types automatically.

**`_recurring_tasks`**: one helper that generates "every N days" reminders
(spraying, vaccination, deworming), shared by crops and livestock.

**`Crop`**: adds area and harvest tracking. Its schedule: *Plant* on the start
date, *Spray* every `spray_interval_days` (stopping before harvest), *Harvest* on
`start + growth_days` (skipped once you have recorded a harvest).

**`Livestock`**: adds animal count and a production log (date, quantity).
Schedule: *Vaccination* every `vaccination_interval_days`.

**Concrete classes**: `Maize`, `Beans`, `Tomatoes`, `DairyCow`, `Poultry`.
The numbers in them (growth days, spray/vaccination intervals) are *illustrative
placeholders*. Check them with an agronomist or vet before presenting them as real
farming advice.

### 4.4 `models.py`
**`Transaction`**: kind (`expense`/`sale`), amount, description, category, date.
Everything validated, nothing changeable afterwards.
**`InventoryItem`**: name, unit, quantity, low-stock threshold; `use()`,
`restock()`, `is_low`.

### 4.5 `farm.py`
`Farm` stores enterprises and inventory in dictionaries keyed by lower-case name
(so `Maize` and `maize` are the same). Methods: add/get/remove, `low_stock_items`,
`total_profit`, `upcoming_tasks` (the polymorphism loop), and `use_input`.

`use_input` deserves a mention: it uses stock **and** charges its cost to an
enterprise as an expense. It checks everything *before* changing anything, so a
failure can never leave the farm half-updated (stock reduced, no expense logged).
Tests cover this ("all or nothing").

### 4.6 `storage.py`
`save` writes the whole farm to JSON through `to_dict()` methods; each class knows
how to turn itself into a dictionary (`Crop.to_dict` calls `super().to_dict()` and
adds its extra fields). It writes to a temporary file and then swaps it in, so a crash
mid-save can't corrupt your data. `load` reverses the process; a missing
file = first run = empty farm; a corrupted file raises `StorageError`, and
`main.py` then refuses to start (so it can't overwrite a file you might repair).

### 4.7 `reports.py`
`ReportGenerator` takes a `Farm` and builds text tables: all-time profit summary,
monthly report, seasonal (any date range) report, plus `export_txt` and
`export_csv` (one row per transaction). Monthly and seasonal reports are both
thin wrappers over one `period_report` method.

### 4.8 `app.py` and `main.py`
`FarmTrackApp.run()` loops: show menu -> read choice -> look the action up in a
dictionary -> run it -> save. All errors that inherit `FarmTrackError` are caught
in one `except`, printed, and the loop continues. The app is "thin": it only
collects input and calls objects; all rules live in the classes.

---------------------------------------------------------------------------

## 5. Follow one request all the way through

You choose **6. Record sale** and type `Maize Plot A`, `4000`, `Green maize`:

1. `FarmTrackApp._record_sale` asks for the inputs (a number that isn't a number
   becomes `InvalidInputError`).
2. `farm.get_enterprise("Maize Plot A")` returns the `Maize` object.
3. `enterprise.record_sale(4000, "Green maize")` (defined once in `Enterprise`)
   builds a `Transaction`, whose constructor validates the amount, description and date.
4. The transaction is appended to the enterprise's **private** list.
5. `run()` calls `storage.save(farm)` -> `farm.to_dict()` -> each enterprise's
   `to_dict()` -> JSON on disk.
6. Next time you open the app, `storage.load()` -> `Farm.from_dict` ->
   `Enterprise.from_dict` reads `"type": "Maize"`, finds the class in the registry, and rebuilds the object.

---------------------------------------------------------------------------

## 6. Testing: what is proven

Run `python -m unittest -v` (40 tests, all passing). They are grouped by concept:
- **Encapsulation:** setters don't exist; bad values rejected; stock never negative; transactions can't be tampered with.
- **Abstraction/inheritance:** `Enterprise()` and `Crop()` can't be instantiated; the inheritance chain is correct; one shared profit formula.
- **Polymorphism:** same method gives crop/livestock-specific results; exact harvest and spray dates are checked; the `DairyCow` override adds deworming.
- **Composition:** duplicate/missing handling; the all-or-nothing stock rule.
- **Persistence:** save/load round trip restores the right subclasses; corrupted files give a clean error; a brand-new subclass survives a round trip.
- **Reports:** a monthly report only counts that month; the CSV is correct.
- **Whole app:** a scripted menu session, restart persistence, and a barrage of bad inputs that must never crash the menu.

---------------------------------------------------------------------------

## 7. Questions your lecturer might ask (and short answers)

**Q: Where is polymorphism?**
`Farm.upcoming_tasks` calls `get_upcoming_tasks()` on every enterprise. Crops return planting/spraying/harvest, livestock returns vaccinations, and `DairyCow` overrides to add deworming. The loop never checks the type.

**Q: Why is `Enterprise` abstract?**
A generic "enterprise" has no schedule or output unit, so it can't exist on its own. The abstract methods force every real type to supply them.

**Q: Difference between abstraction and encapsulation?**
Abstraction = deciding *what* an object must offer and hiding *how* (the abstract `Enterprise`). Encapsulation = *protecting* an object's data behind validated methods (`InventoryItem.use`).

**Q: Inheritance vs composition here?**
`Maize` *is a* `Crop` (inheritance). `Farm` *has* enterprises (composition).

**Q: How would you add a new animal, say Goats?**
```python
class Goats(Livestock):
    production_unit = "litres"
    vaccination_interval_days = 120
```
Nothing else changes: it appears in the menu, saves and loads, and gets reminders.

**Q: Why `_name` with an underscore, and why `@property`?**
Underscore = "private by convention". Property gives read access without allowing uncontrolled writes.

**Q: Why custom exceptions?**
They say exactly what went wrong and let the menu handle all FarmTrack errors in one place, instead of a crash or a generic `ValueError`.

**Q (a fair one): your concept note said `calculate_profit()` would be abstract.**
I made it a normal inherited method in `Enterprise`, because profit (sales minus expenses) is the *same formula* for every enterprise; making it abstract would force copy-pasting identical code into each subclass, which goes against reuse. The abstract methods are the ones that genuinely differ (tasks, output, size). If your lecturer expects it abstract, tell me and I'll change it, but be ready to explain this reasoning.

---------------------------------------------------------------------------

## 8. Limitations you can mention honestly
- Command-line only, single user, one JSON file (no database).
- Growth/spray/vaccination intervals are example values, not agronomic advice.
- Crops keep a running harvest total, not a dated harvest log (livestock keeps dated production).
- A crop's "start date" is used as the planting date.
- Possible next steps: a GUI/web front end, SMS reminders, per-input cost tracking, multiple seasons per field.
