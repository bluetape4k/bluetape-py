class IDError(ValueError):
    """Base class for bluetape identifier value errors."""


class InvalidIDError(IDError):
    """Raised when an identifier or generator input is invalid."""


class IDOverflowError(IDError):
    """Raised when an identifier timestamp or sequence is exhausted."""
