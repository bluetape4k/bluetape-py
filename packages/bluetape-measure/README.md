# bluetape-measure

English | [한국어](README.ko.md)

Stdlib-only immutable linear measurements with runtime dimension checks.

## Install

PyPI publication is on hold. The intended focused and meta-extra installs are:

```bash
pip install bluetape-measure
pip install "bluetape[measure]"
```

The default `bluetape` install does not include this package.

## Quickstart

<!-- value-example:start -->
```python
from bluetape.measure import KILOMETER, METER, Dimension, Measure, Unit, parse_measure

distance = Measure(1.25, KILOMETER)
assert distance.to(METER) == Measure(1250, METER)
assert parse_measure("1250 m").equivalent_to(distance)

smoot = Unit("smoot", "smoot", Dimension.LENGTH, 1.7018)
custom = Measure.from_dict({"amount": "2.0", "unit": "smoot"}, units=[smoot])
assert custom == Measure(2, smoot)
```
<!-- value-example:end -->

The built-in set contains meter, kilometer, centimeter, millimeter, second,
millisecond, minute, hour, gram, and kilogram. Arithmetic converts only within
the same runtime `Dimension`; incompatible dimensions fail explicitly.

## Custom Units

`Unit` is immutable and describes a positive linear ratio to its dimension's
base unit. Applications own custom unit definitions and pass the same bounded,
duplicate-free unit iterable to `parse_measure()` or `Measure.from_dict()`.
There is no mutable global registry or unit-definition file loader.

## Versionless Schema

The exact primitive schema is `{"amount": str, "unit": str}` with no version
field and no extra keys. Deserialization resolves the symbol only from the
caller-supplied unit iterable. Amount parsing uses strict ASCII finite-number
grammar; Unicode digits, booleans, NaN, infinity, and surrounding whitespace
are rejected.

## Persistence and Rollback

Persist the exact two-key primitive schema and preserve custom unit definitions
with application configuration. Before uninstalling `bluetape-measure` or
`bluetape[measure]`, stop imports and keep the schema plus unit definitions.
Rollback can read a custom value only when the application supplies the same
immutable definition.

## Deferred Scope

Compound units, dimensional-expression parsing, affine temperature conversion,
currency values, locale formatting, arbitrary numeric protocols, and a global
registry are deferred. A concrete compound or temperature caller requires a
separate design issue.
