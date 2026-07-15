# bluetape-money

English | [한국어](README.ko.md)

Stdlib-only ISO 4217 currencies and exact `Decimal` money values with
caller-supplied exchange rates.

## Install

PyPI publication is on hold. The intended focused and meta-extra installs are:

```bash
pip install bluetape-money
pip install "bluetape[money]"
```

The default `bluetape` install does not include this package.

## Quickstart

<!-- value-example:start -->
```python
from decimal import ROUND_HALF_UP

from bluetape.money import EUR, USD, ExchangeRate, Money, convert

price = Money.of("12.345", USD)
assert price.quantize(rounding=ROUND_HALF_UP) == Money.of("12.35", USD)

rate = ExchangeRate.of(USD, EUR, "0.925")
euros = convert(price, rate)
assert euros == Money.of("11.419125", EUR)
assert convert(euros, rate) == price

try:
    Money.of(12.34, USD)
except TypeError:
    pass
else:
    raise AssertionError("binary floats must be rejected")
```
<!-- value-example:end -->

Amounts and rates accept only bounded exact `Decimal`, integer, or strict ASCII
decimal strings. Every binary float and boolean is rejected before arithmetic.
Operations use a package-local Decimal context and never mutate or inherit the
caller's ambient precision.

## ISO 4217 Snapshot

Currency metadata is generated offline from the committed SIX ISO 4217 current
List One snapshot. The exact XML and provenance manifest live under
`docs/research/sources/iso4217/`; `scripts/update-iso4217.py` deterministically
regenerates the Python table from explicit local input. Import, build, and
normal use never access the network. `XXX` and `XTS` are excluded.

## Rounding and Exchange Rates

Arithmetic never rounds automatically. `quantize()` and `minor_units()` make
minor-unit policy explicit, including caller-selected stdlib Decimal rounding.
Currencies whose current ISO row has no minor unit reject those operations.

`ExchangeRate` is a positive exact base-to-quote value supplied by the caller.
`convert()` supports both directions without quantizing. The package owns no FX
provider, freshness policy, cache, retry, background task, or I/O.

## Versionless Schema

The exact primitive schema is `{"amount": str, "currency": str}` with no
version or extra keys. Canonical formatting is `CODE amount` in fixed-point
notation. Parsing rejects symbols, locale rules, Unicode digits, whitespace
drift, floats, and unknown/currently excluded currency codes.

## Current, Not Historical

Lookup represents the committed current snapshot, not historical tender or
jurisdiction policy. A code added by a later package version may be unreadable
after rollback. Archival applications must pin a package version or own a
historical currency table. Before uninstalling `bluetape-money` or
`bluetape[money]`, stop imports while retaining the exact primitive values.

## Deferred Scope

Locale/CLDR formatting, accounting, tax, allocation, historical ISO codes, and
provider-backed FX are deferred. Locale money and FX providers require separate
issues that assign data source, freshness, cache, failure, and lifecycle
ownership.
