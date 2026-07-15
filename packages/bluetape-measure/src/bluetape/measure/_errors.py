class MeasureError(ValueError):
    """Base class for measurement value errors."""


class InvalidUnitError(MeasureError):
    """Raised when a unit definition is invalid."""


class InvalidMeasureError(MeasureError):
    """Raised when a measure value or representation is invalid."""


class IncompatibleUnitError(MeasureError):
    """Raised when an operation crosses runtime dimensions."""
