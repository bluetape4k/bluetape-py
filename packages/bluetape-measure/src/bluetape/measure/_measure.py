import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from ._errors import IncompatibleUnitError, InvalidMeasureError
from ._units import BUILTIN_UNITS, Unit, index_units

_NUMBER_PATTERN = re.compile(
    r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?",
    re.ASCII,
)


def require_number(value: object, name: str = "amount") -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be an integer or float")
    try:
        normalized = float(value)
    except OverflowError as error:
        raise InvalidMeasureError(f"{name} must be finite") from error
    if not math.isfinite(normalized):
        raise InvalidMeasureError(f"{name} must be finite")
    return normalized


def parse_number(value: str) -> float:
    if len(value) > 256 or _NUMBER_PATTERN.fullmatch(value) is None:
        raise InvalidMeasureError("amount must use the strict ASCII number grammar")
    try:
        return require_number(float(value))
    except ValueError as error:
        raise InvalidMeasureError("amount must use the strict ASCII number grammar") from error


@dataclass(frozen=True, slots=True, init=False)
class Measure:
    amount: float
    unit: Unit

    def __init__(self, amount: int | float, unit: Unit) -> None:
        normalized_amount = require_number(amount)
        if not isinstance(unit, Unit):
            raise TypeError("unit must be a Unit")
        object.__setattr__(self, "amount", normalized_amount)
        object.__setattr__(self, "unit", unit)

    def to(self, unit: Unit) -> "Measure":
        if not isinstance(unit, Unit):
            raise TypeError("unit must be a Unit")
        if self.unit.dimension is not unit.dimension:
            raise IncompatibleUnitError("units must have the same dimension")
        return Measure(self.amount * self.unit.ratio / unit.ratio, unit)

    def __add__(self, other: "Measure") -> "Measure":
        if not isinstance(other, Measure):
            return NotImplemented
        return Measure(self.amount + other.to(self.unit).amount, self.unit)

    def __sub__(self, other: "Measure") -> "Measure":
        if not isinstance(other, Measure):
            return NotImplemented
        return Measure(self.amount - other.to(self.unit).amount, self.unit)

    def __mul__(self, scalar: int | float) -> "Measure":
        return Measure(self.amount * require_number(scalar, "scalar"), self.unit)

    def __rmul__(self, scalar: int | float) -> "Measure":
        return self * scalar

    def __truediv__(self, scalar: int | float) -> "Measure":
        normalized = require_number(scalar, "scalar")
        if normalized == 0:
            raise ZeroDivisionError("measure division by zero")
        return Measure(self.amount / normalized, self.unit)

    def equivalent_to(
        self,
        other: "Measure",
        *,
        rel_tol: float = 1e-9,
        abs_tol: float = 0.0,
    ) -> bool:
        if not isinstance(other, Measure):
            raise TypeError("other must be a Measure")
        relative = require_number(rel_tol, "rel_tol")
        absolute = require_number(abs_tol, "abs_tol")
        if relative < 0 or absolute < 0:
            raise InvalidMeasureError("tolerances must be non-negative")
        if self.unit.dimension is not other.unit.dimension:
            return False
        return math.isclose(
            self.amount,
            other.to(self.unit).amount,
            rel_tol=relative,
            abs_tol=absolute,
        )

    def format(self, unit: Unit | None = None, *, spec: str = "g") -> str:
        if unit is not None and not isinstance(unit, Unit):
            raise TypeError("unit must be a Unit or None")
        if not isinstance(spec, str):
            raise TypeError("spec must be a string")
        converted = self if unit is None else self.to(unit)
        return f"{format(converted.amount, spec)} {converted.unit.symbol}"

    def to_dict(self) -> dict[str, str]:
        return {"amount": repr(self.amount), "unit": self.unit.symbol}

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, object],
        *,
        units: Iterable[Unit] = BUILTIN_UNITS,
    ) -> "Measure":
        if not isinstance(value, Mapping):
            raise TypeError("value must be a mapping")
        if set(value) != {"amount", "unit"}:
            raise InvalidMeasureError("value must contain exactly amount and unit")
        amount = value["amount"]
        symbol = value["unit"]
        if not isinstance(amount, str):
            raise TypeError("amount must be a string")
        if not isinstance(symbol, str):
            raise TypeError("unit must be a string")
        indexed = index_units(units)
        try:
            unit = indexed[symbol]
        except KeyError as error:
            raise InvalidMeasureError("unit symbol is unknown") from error
        return cls(parse_number(amount), unit)
