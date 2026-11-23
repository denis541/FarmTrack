"""ReportGenerator: turns a Farm into readable summaries and files."""
from __future__ import annotations

import calendar
import csv
from datetime import date
from pathlib import Path

from farmtrack.exceptions import InvalidInputError
from farmtrack.farm import Farm
from farmtrack.formatting import money
from farmtrack.validators import to_date

LINE = "-" * 90


class ReportGenerator:
    def __init__(self, farm: Farm):
        self._farm = farm

    def _table(self, title: str, rows: list) -> str:
        """rows = list of (name, kind, income, expenses)."""
        lines = [title, LINE,
                 f"{'Enterprise':<36}{'Income':>18}{'Expenses':>18}{'Profit':>18}", LINE]
        total_in = total_out = 0.0
        for name, kind, income, expenses in rows:
            label = f"{name} ({kind})"[:35]
            lines.append(f"{label:<36}{money(income):>18}{money(expenses):>18}"
                         f"{money(income - expenses):>18}")
            total_in += income
            total_out += expenses
        lines += [LINE,
                  f"{'FARM TOTAL':<36}{money(total_in):>18}{money(total_out):>18}"
                  f"{money(total_in - total_out):>18}"]
        low = self._farm.low_stock_items()
        if low:
            lines += ["", "LOW STOCK WARNING:"] + [f"  - {item}" for item in low]
        return "\n".join(lines)

    def profit_summary(self) -> str:
        rows = [(e.name, e.kind, e.total_income, e.total_expenses)
                for e in self._farm.enterprises]
        return self._table(f"PROFIT SUMMARY - {self._farm.name} (all time)", rows)

    def period_report(self, start, end, title: str = "PERIOD REPORT") -> str:
        start, end = to_date(start, "Start date"), to_date(end, "End date")
        if end < start:
            raise InvalidInputError("End date cannot be before start date.")
        rows = [(e.name, e.kind, e.income_between(start, end),
                 e.expenses_between(start, end)) for e in self._farm.enterprises]
        return self._table(f"{title}: {start.isoformat()} to {end.isoformat()}", rows)

    def monthly_report(self, year: int, month: int) -> str:
        if not 1 <= month <= 12:
            raise InvalidInputError("Month must be between 1 and 12.")
        last_day = calendar.monthrange(year, month)[1]
        return self.period_report(date(year, month, 1), date(year, month, last_day),
                                  f"MONTHLY REPORT ({calendar.month_name[month]} {year})")

    def seasonal_report(self, start, end) -> str:
        return self.period_report(start, end, "SEASONAL REPORT")

    def export_txt(self, text: str, path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        return path

    def export_csv(self, path) -> Path:
        """One row per transaction, across the whole farm, oldest first."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = [(t.date, e.name, e.kind, t.kind, t.category, t.description, t.amount)
                for e in self._farm.enterprises for t in e.transactions]
        rows.sort(key=lambda row: row[0])
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["date", "enterprise", "enterprise_type",
                             "transaction", "category", "description", "amount"])
            for row in rows:
                writer.writerow([row[0].isoformat(), *row[1:]])
        return path
