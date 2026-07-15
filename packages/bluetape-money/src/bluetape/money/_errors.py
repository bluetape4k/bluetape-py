class MoneyError(ValueError):
    """Base class for money value errors."""


class InvalidCurrencyError(MoneyError):
    """Raised when a currency is unknown or invalid."""


class InvalidAmountError(MoneyError):
    """Raised when an amount is malformed, non-finite, or out of bounds."""


class CurrencyMismatchError(MoneyError):
    """Raised when an operation crosses currency boundaries."""


class InvalidExchangeRateError(MoneyError):
    """Raised when an exchange rate violates its value contract."""
