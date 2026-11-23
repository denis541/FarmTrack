"""JSON persistence: save the Farm to a file and load it back."""
from __future__ import annotations

import json
import os
from pathlib import Path

from farmtrack.exceptions import FarmTrackError, StorageError
from farmtrack.farm import Farm


class JsonStorage:
    def __init__(self, path="farmtrack_data.json"):
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def save(self, farm: Farm) -> None:
        """Write to a temp file first, then swap it in. If the program dies
        mid-write, the old data file is still intact."""
        temp = self._path.with_suffix(".tmp")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(temp, "w", encoding="utf-8") as handle:
                json.dump(farm.to_dict(), handle, indent=2)
            os.replace(temp, self._path)
        except OSError as error:
            raise StorageError(f"Could not save data: {error}") from error

    def load(self) -> Farm:
        """A missing file just means 'first run': start with an empty farm."""
        if not self._path.exists():
            return Farm()
        try:
            with open(self._path, encoding="utf-8") as handle:
                return Farm.from_dict(json.load(handle))
        except (OSError, ValueError, KeyError, TypeError, FarmTrackError) as error:
            raise StorageError(
                f"Data file '{self._path}' is unreadable or corrupted: {error}"
            ) from error
