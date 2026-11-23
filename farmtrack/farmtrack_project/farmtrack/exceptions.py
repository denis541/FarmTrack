"""Custom exceptions.

Every error FarmTrack raises on purpose inherits from FarmTrackError, so the
menu can catch ONE type and show a friendly message instead of crashing.
"""


class FarmTrackError(Exception):
    """Base class for all FarmTrack errors."""


class InvalidInputError(FarmTrackError):
    """Bad value: negative quantity, empty name, wrong date format..."""


class ItemNotFoundError(FarmTrackError):
    """An enterprise or inventory item that does not exist."""


class DuplicateItemError(FarmTrackError):
    """Trying to add something whose name is already used."""


class InsufficientStockError(FarmTrackError):
    """Trying to use more stock than we have."""


class StorageError(FarmTrackError):
    """The data file is unreadable or could not be written."""
