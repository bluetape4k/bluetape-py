# Issue #13 ID, Measure, and Money Value Packages Design

Date: 2026-07-15 KST
Target issue: #13 - `feat: add id, measure, and money value packages`
Target milestone: `0.2.0`

## Approved Delivery Shape

Issue #13 remains one issue, branch, and PR, but implementation is divided into
three independent package subplans. Each package has its own public contract,
tests, documentation, and reviewable commit boundary. No package imports
another. The user approved this scoped delivery on 2026-07-15.

Research basis:
[`docs/research/2026-07-15-issue-13-value-packages.md`](../../research/2026-07-15-issue-13-value-packages.md).

## Problem

The workspace has no Python-native values for service identifiers, physical
measurements, or currency amounts. Copying the broad Go/JVM surfaces would add
formats, dimensions, provider behavior, or dependencies before Python callers
have demonstrated a need. Using bare strings/floats instead loses validation,
ordering, dimension, and exact-decimal contracts at service boundaries.

The first release must therefore be narrow but complete: immutable public
values, explicit ownership of clocks/randomness/data, strict parsing and
serialization, and no hidden I/O.

## Cross-Package Decisions

- Distributions/imports: `bluetape-id` / `bluetape.id`,
  `bluetape-measure` / `bluetape.measure`, and `bluetape-money` /
  `bluetape.money`.
- Python `>=3.13`; runtime dependencies are empty for all three.
- Focused installs and matching `bluetape[id]`, `bluetape[measure]`,
  `bluetape[money]`, and aggregate `bluetape[values]` extras are supported.
- The default meta install remains exactly `bluetape-core==0.1.0`.
- All public values are immutable and slotted. Invalid construction fails
  before callbacks or arithmetic are invoked.
- Error messages identify invalid fields/categories but do not embed entropy,
  caller payloads, or downloaded source contents.
- Serialization is primitive-data-only and versionless in v1; no package
  registers global JSON encoders or framework adapters.
- PyPI publication, release, tag, and merge are outside the implementation
  design. PR creation is covered by the approved delivery workflow; merge
  still requires fresh exact-head approval.

## Package A: `bluetape-id`

### Scope

The package implements UUID v4, process-local monotonic UUID v7, random ULID,
and process-local monotonic ULID. KSUID and Snowflake are evaluated and deferred.

UUID functions return the stdlib `uuid.UUID` value. ULIDs use canonical uppercase
26-character Crockford Base32 strings because the stdlib has no ULID value.

### Public API

The ordered public exports are:

```python
[
    "IDError",
    "InvalidIDError",
    "IDOverflowError",
    "UUID7Generator",
    "ULIDGenerator",
    "MonotonicULIDGenerator",
    "uuid4",
    "uuid7",
    "uuid7_timestamp_ms",
    "ulid",
    "parse_ulid",
    "ulid_timestamp_ms",
]
```

`IDError` extends `ValueError`; `InvalidIDError` and `IDOverflowError`
extend `IDError`. Type errors use `TypeError`, while format/range/state errors
use these repo-owned value errors.

Signatures:

```python
class UUID7Generator:
    def __init__(
        self,
        *,
        clock: Callable[[], int] = unix_time_ms,
        random_bytes: Callable[[int], bytes] = secrets.token_bytes,
    ) -> None: ...
    def new(self) -> uuid.UUID: ...

class ULIDGenerator:
    def __init__(
        self,
        *,
        clock: Callable[[], int] = unix_time_ms,
        random_bytes: Callable[[int], bytes] = secrets.token_bytes,
    ) -> None: ...
    def new(self) -> str: ...

class MonotonicULIDGenerator:
    def __init__(
        self,
        *,
        clock: Callable[[], int] = unix_time_ms,
        random_bytes: Callable[[int], bytes] = secrets.token_bytes,
    ) -> None: ...
    def new(self) -> str: ...

def uuid4() -> uuid.UUID: ...
def uuid7() -> uuid.UUID: ...
def uuid7_timestamp_ms(value: uuid.UUID | str) -> int: ...
def ulid() -> str: ...
def parse_ulid(value: str) -> str: ...
def ulid_timestamp_ms(value: str) -> int: ...
```

`clock` returns Unix epoch milliseconds as a non-boolean integer. Entropy must
return exactly the requested byte count. Callbacks are validated as callable at
construction but not invoked until `new()`. Clock and entropy callbacks run
before the generator state lock is acquired; callback latency or failure cannot
hold the lock or partially advance generator state. Ordering is defined by the
subsequent state-lock acquisition, not by caller thread start order.
Injected callbacks are caller-owned and must be safe for concurrent calls when
the same generator is shared.

`uuid7_timestamp_ms()` accepts a `uuid.UUID` or an exact canonical lowercase,
hyphenated 36-character UUID string. It rejects braces, URNs, uppercase,
hyphenless strings, surrounding whitespace, non-v7 values, and non-RFC
variants even when the stdlib parser would otherwise accept them.

### UUIDv7 Behavior

- Bits 0-47 are Unix milliseconds, version is 7, variant is RFC 4122/9562,
  `rand_a` is a 12-bit counter, and `rand_b` contains 62 random bits.
- A new observed millisecond seeds the counter from entropy. Same-millisecond
  generation increments the counter. Clock rollback keeps the last logical
  millisecond and increments the counter.
- Counter overflow advances the logical millisecond by one. Exceeding the
  48-bit timestamp range raises `IDOverflowError`.
- Every UUIDv7 call requests exactly 10 entropy bytes before locking. Bytes
  0-1 are read as an unsigned big-endian integer and masked to 12 bits for a
  new-tick counter seed; bytes 2-9 are read big-endian and masked to 62 bits for
  a fresh `rand_b` on every call. Same/rollback ticks ignore the prefetched seed
  and increment the prior counter. Counter overflow advances the logical
  millisecond and uses the prefetched seed for that new logical tick; `rand_b`
  is still refreshed. Invalid entropy leaves state unchanged.
- Ordering is guaranteed only for calls through the same generator instance.
  The module `uuid7()` convenience function uses one process-local shared,
  thread-safe generator. It does not coordinate processes or hosts.
- `uuid4()` delegates to stdlib `uuid.uuid4()`.
- UUID values are identifiers, not authentication or authorization secrets.

### ULID Behavior

- Timestamp is 48-bit Unix milliseconds and randomness is 80 bits.
- Parsing requires exactly 26 canonical uppercase characters, rejects the
  ambiguous letters `I`, `L`, `O`, `U`, and rejects values above the 128-bit
  canonical maximum.
- `ULIDGenerator` is random within a millisecond. `MonotonicULIDGenerator`
  increments the 80-bit random component for same/rollback ticks; overflow
  raises `IDOverflowError` rather than blocking or sleeping.
- Every ULID call requests exactly 10 entropy bytes. Random generation uses all
  80 bits. Monotonic generation uses them for a new observed millisecond,
  ignores the prefetched value and increments the prior 80-bit value for a
  same/rollback tick, and fails without state change on entropy or 80-bit
  overflow.
- Module `ulid()` uses a random generator. Callers requiring monotonicity own a
  `MonotonicULIDGenerator` instance explicitly.
- `ULIDGenerator` has no sequencing state and is thread-safe only when injected
  callbacks are thread-safe. `MonotonicULIDGenerator` serializes state changes
  and guarantees lexical order by lock acquisition order; callbacks run before
  the lock. Neither generator nor module convenience preserves sequencing
  across processes, forks, or restarts.

### ID Non-Goals

- UUID v1/v3/v5 wrappers, UUID v6/v8, KSUID, Snowflake, machine-id allocation,
  distributed ordering, persistence across restart, authentication tokens, or
  cross-language generator-state compatibility.

## Package B: `bluetape-measure`

### Scope

The package implements immutable linear `Unit` and `Measure` values. The first
built-in dimensions are length, time, and mass. A runtime `Dimension` enum
blocks cross-dimension operations. Generic marker types were rejected because
this repository has no approved static-checker dependency and erased Python
type parameters could overstate guarantees for caller-created units.

### Public API

Core exports:

```python
[
    "MeasureError",
    "InvalidUnitError",
    "InvalidMeasureError",
    "IncompatibleUnitError",
    "Dimension",
    "Unit",
    "Measure",
    "parse_measure",
    "BUILTIN_UNITS",
    "METER",
    "KILOMETER",
    "CENTIMETER",
    "MILLIMETER",
    "SECOND",
    "MILLISECOND",
    "MINUTE",
    "HOUR",
    "GRAM",
    "KILOGRAM",
]
```

`MeasureError` extends `ValueError`; `InvalidUnitError`,
`InvalidMeasureError`, and `IncompatibleUnitError` extend `MeasureError`.
Wrong Python types raise `TypeError`; semantic invalidity uses these repo-owned
value errors.

`Dimension` is a string enum with exact values `LENGTH = "length"`,
`TIME = "time"`, and `MASS = "mass"`.

`Unit` and `Measure` have these complete public declarations:

```python
class Dimension(StrEnum):
    LENGTH = "length"
    TIME = "time"
    MASS = "mass"

@dataclass(frozen=True, slots=True)
class Unit:
    name: str
    symbol: str
    dimension: Dimension
    ratio: float

    def __init__(
        self,
        name: str,
        symbol: str,
        dimension: Dimension,
        ratio: int | float,
    ) -> None:
        # Declaration-smoke assignments; production validation is specified below.
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "dimension", dimension)
        object.__setattr__(self, "ratio", float(ratio))

METER = Unit("meter", "m", Dimension.LENGTH, 1.0)
KILOMETER = Unit("kilometer", "km", Dimension.LENGTH, 1000.0)
CENTIMETER = Unit("centimeter", "cm", Dimension.LENGTH, 0.01)
MILLIMETER = Unit("millimeter", "mm", Dimension.LENGTH, 0.001)
SECOND = Unit("second", "s", Dimension.TIME, 1.0)
MILLISECOND = Unit("millisecond", "ms", Dimension.TIME, 0.001)
MINUTE = Unit("minute", "min", Dimension.TIME, 60.0)
HOUR = Unit("hour", "h", Dimension.TIME, 3600.0)
GRAM = Unit("gram", "g", Dimension.MASS, 1.0)
KILOGRAM = Unit("kilogram", "kg", Dimension.MASS, 1000.0)

BUILTIN_UNITS: tuple[Unit, ...] = (
    METER,
    KILOMETER,
    CENTIMETER,
    MILLIMETER,
    SECOND,
    MILLISECOND,
    MINUTE,
    HOUR,
    GRAM,
    KILOGRAM,
)

@dataclass(frozen=True, slots=True)
class Measure:
    amount: float
    unit: Unit

    def __init__(self, amount: int | float, unit: Unit) -> None: ...
    def to(self, unit: Unit) -> Measure: ...
    def __add__(self, other: Measure) -> Measure: ...
    def __sub__(self, other: Measure) -> Measure: ...
    def __mul__(self, scalar: int | float) -> Measure: ...
    def __rmul__(self, scalar: int | float) -> Measure: ...
    def __truediv__(self, scalar: int | float) -> Measure: ...
    def equivalent_to(
        self,
        other: Measure,
        *,
        rel_tol: float = 1e-9,
        abs_tol: float = 0.0,
    ) -> bool: ...
    def format(self, unit: Unit | None = None, *, spec: str = "g") -> str: ...
    def to_dict(self) -> dict[str, str]: ...

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, object],
        *,
        units: Iterable[Unit] = BUILTIN_UNITS,
    ) -> Measure: ...

def parse_measure(
    text: str,
    *,
    units: Iterable[Unit] = BUILTIN_UNITS,
) -> Measure: ...
```

Names/symbols are non-blank trimmed strings, dimension is a `Dimension`, and
ratio is a finite positive non-boolean number normalized to `float` relative to
the base unit. Amounts are finite non-boolean `int | float` values normalized
to `float`.

`BUILTIN_UNITS` is the immutable tuple shown above in exact order. Meter,
second, and gram are the base units for their dimensions; every ratio is the
number of those base units represented by one unit. Tests execute this literal
declaration order and compare every constant's name, symbol, dimension, ratio,
and tuple position.
Caller unit iterables are materialized once, limited to 256 entries, and
validated for exact unique symbols. Custom immutable units are supported.

Addition/subtraction require the same runtime dimension and preserve the left
operand's unit. Multiplication/division accept finite scalar int/float values;
division by zero fails. `equivalent_to()` compares converted amounts using
the declared tolerances, returns `False` for an incompatible dimension, and
rejects boolean, negative, NaN, or infinite tolerances.

`parse_measure()` accepts a `str` of at most 256 characters matching the ASCII
grammar `[+-]?(digits[.digits?]?|.digits)([eE][+-]?digits)?[ \t]+symbol`.
It rejects surrounding whitespace, newlines, underscores, Unicode digits,
missing separation, special float names, and symbol case changes. Duplicate
symbols in a caller-supplied unit set fail closed. Formatting does not use
locale, emits exactly `<format(amount, spec)> <symbol>`, and serialization emits
`{"amount": repr(amount), "unit": symbol}`.

### Measure Non-Goals

- Compound/product/ratio units, area, volume, velocity, acceleration, affine
  temperature, currencies, arbitrary numeric protocols, locale formatting,
  mutable global registries, dimensional-analysis expression parsing, or unit
  definition files.

## Package C: `bluetape-money`

### Currency Data Boundary

`Currency` values come from a generated Python table derived from the SIX ISO
4217 current List One XML. The generated module records source URL, retrieval
date, and input SHA-256. An offline maintainer script accepts an explicit XML
path and writes deterministic Python output. Import/build/test never accesses
the network.

The exact retrieved XML is committed at
`docs/research/sources/iso4217/2026-07-15-list-one.xml` under ISO's documented
free currency-code use. The sibling
`2026-07-15-list-one.provenance.json` records canonical and effective HTTPS
URLs, retrieval UTC timestamp, byte count, SHA-256, source-row count,
unique-currency count, excluded-code count/list, and generated output path.
This immutable source+manifest pair is the reproduction authority after SIX
updates the live endpoint.

Current alphabetic and numeric codes are parsed case-insensitively for letters
but surrounding whitespace is rejected. `XXX` (no currency) and `XTS` (testing)
are not valid money currencies. A missing ISO minor unit is represented by
`None`, never guessed.

### Public API

The ordered public exports are:

```python
[
    "MoneyError",
    "InvalidCurrencyError",
    "InvalidAmountError",
    "CurrencyMismatchError",
    "InvalidExchangeRateError",
    "Currency",
    "Money",
    "ExchangeRate",
    "get_currency",
    "parse_money",
    "sum_money",
    "convert",
    "USD",
    "EUR",
    "KRW",
    "JPY",
    "CNY",
]
```

`MoneyError` extends `ValueError`; `InvalidCurrencyError`,
`InvalidAmountError`, `CurrencyMismatchError`, and
`InvalidExchangeRateError` extend `MoneyError`. Wrong Python types, especially
binary float and boolean inputs, raise `TypeError` before Decimal arithmetic.

The complete public declarations are:

```python
@dataclass(frozen=True, slots=True)
class Currency:
    code: str
    numeric_code: str
    name: str
    minor_unit: int | None

@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: Currency

    @classmethod
    def of(cls, value: Decimal | int | str, currency: Currency) -> Money: ...

    @classmethod
    def from_minor(cls, units: int, currency: Currency) -> Money: ...

    def __add__(self, other: Money) -> Money: ...
    def __sub__(self, other: Money) -> Money: ...
    def __neg__(self) -> Money: ...
    def __abs__(self) -> Money: ...
    def __mul__(self, scalar: Decimal | int | str) -> Money: ...
    def __rmul__(self, scalar: Decimal | int | str) -> Money: ...
    def __truediv__(self, scalar: Decimal | int | str) -> Money: ...
    def __lt__(self, other: Money) -> bool: ...
    def __le__(self, other: Money) -> bool: ...
    def __gt__(self, other: Money) -> bool: ...
    def __ge__(self, other: Money) -> bool: ...
    def quantize(self, *, rounding: str = ROUND_HALF_EVEN) -> Money: ...
    def minor_units(self, *, rounding: str | None = None) -> int: ...
    def format(
        self,
        *,
        quantize: bool = False,
        rounding: str = ROUND_HALF_EVEN,
    ) -> str: ...
    def to_dict(self) -> dict[str, str]: ...

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> Money: ...

@dataclass(frozen=True, slots=True)
class ExchangeRate:
    base: Currency
    quote: Currency
    rate: Decimal

    @classmethod
    def of(
        cls,
        base: Currency,
        quote: Currency,
        rate: Decimal | int | str,
    ) -> ExchangeRate: ...

def get_currency(code_or_numeric: str | int) -> Currency: ...
def parse_money(text: str) -> Money: ...
def sum_money(currency: Currency, values: Iterable[Money]) -> Money: ...
def convert(money: Money, rate: ExchangeRate) -> Money: ...
```

Direct `Currency` construction is supported only for an exact generated table
row; normal callers use `get_currency()` or the five constants. Direct `Money`
and `ExchangeRate` construction requires already validated finite `Decimal`
values and still enforces all invariants.

`Money.of()` accepts `Decimal | int | str`; `bool` and every `float` are
rejected. String construction rejects blank or surrounding-space input and
accepts only ASCII decimal/exponent grammar without underscores or Unicode
digits. Input is capped at 512 characters, coefficient digits at 256, and
absolute exponent at 256. Every constructed or arithmetic result is finite and
must remain inside those bounds; failures raise `InvalidAmountError` without
echoing the amount. `Money.from_minor()` requires a non-boolean integer and a
known minor unit.

All arithmetic runs inside a package-owned local Decimal context with precision
256, `Emin=-256`, `Emax=256`, half-even arithmetic rounding, and traps for
invalid operations, division by zero, and overflow. Ambient caller context is
neither mutated nor allowed to change results. `quantize()` alone accepts one
of the stdlib Decimal rounding constants explicitly.

Money supports same-currency addition, subtraction, ordering, negation,
absolute value, multiplication by an exact decimal scalar, and division by a
non-zero exact decimal scalar. Mixed currencies raise `CurrencyMismatchError`.
Unsupported/wrong operand types raise `TypeError`; scalar zero division raises
`ZeroDivisionError`; invalid rounding names raise `InvalidAmountError`. No
arithmetic automatically quantizes.

Canonical formatting is `CODE amount` with fixed-point decimal notation and no
locale symbol. `parse_money()` requires that shape. Serialization is
`{"amount": str(decimal), "currency": code}` and rejects extra/missing keys.
Explicit `quantize()` owns minor-unit rounding.

For a currency whose minor unit is `None`, `Money.from_minor()`, `quantize()`,
and `minor_units()` always raise `InvalidCurrencyError`, including when a
rounding argument is supplied. Other exact arithmetic and unquantized
format/serialization remain supported.

`ExchangeRate` is frozen/slotted with `base`, `quote`, and positive finite
`rate: Decimal`. Direct construction requires `Decimal`; the classmethod
`ExchangeRate.of(base, quote, rate)` accepts the same
`Decimal | int | str` exact scalar boundary as `Money.of`.
Same-currency rates must equal one. `convert(money, rate)` multiplies in the
base-to-quote direction and divides in reverse, returns an unquantized `Money`,
and rejects unrelated currencies. It performs no lookup, cache, refresh, or I/O.

`sum_money(currency, values)` returns zero for empty input and rejects the first
invalid/mixed-currency value.

### Money Non-Goals

- Binary float amounts/rates, locale inference, currency symbols, accounting
  ledgers, tax, allocation, provider-backed FX, ECB/IMF clients, network/cache
  ownership, automatic rounding, historical ISO codes, or jurisdiction policy.

## Packaging and Repository Integration

- Register all three members in root workspace dependency/source/member lists.
- Add the four opt-in meta extras and include the three packages in `dev` and
  `all`; keep default core-only.
- Add all three to fail-closed publishable classification but not the historical
  `v0.1.0` target-release table. Publication remains HOLD.
- Generic CI owns tests, Ruff, and `uv build --all-packages`; no dedicated
  service/container job is needed.
- Root/meta/package README locale pairs, package layout, WIP, changelog, and
  release classification are updated together.
- One static package-boundary diagram is produced as both SVG and PNG. It shows
  separate focused distributions, their stdlib/data ownership, opt-in meta
  extras, and caller-owned clock/entropy/rates. Mermaid is not used.

## Compatibility, Persistence, and Rollback

- ID values persist only as canonical UUID/ULID strings. Generator sequencing
  state is not serialized; upgrades, forks, restarts, and rollbacks start fresh
  process-local state.
- Measure v1 primitive schema is exactly `amount` and `unit`; money v1 is
  exactly `amount` and `currency`. Unknown/missing keys fail. Custom measure
  deserialization requires the application to supply the same immutable unit
  definition; there is no migration or global registry lookup.
- Currency lookup represents the committed current ISO snapshot, not historical
  ISO data. Values created with a later currency code fail after rollback to a
  snapshot that lacks it. Archival callers must pin a version or own historical
  policy.
- Removing focused distributions or extras requires no repository-owned data
  migration. Applications stop imports before rollback and retain ownership of
  persisted-string compatibility.

## Deferred Follow-ups

| Candidate | Adoption trigger | Disposition |
|---|---|---|
| KSUID | Concrete Segment/Kotlin compatibility consumer | Deferred; file only with evidence |
| Snowflake | Owned machine-id, epoch, rollback, restart policy | Dedicated future issue |
| Compound/affine measures | Concrete dimension/temperature caller | Separate design issue |
| Locale money | Owned CLDR/current-tender policy | Separate research issue |
| Provider FX | Source/freshness/cache/failure ownership | Separate integration package |

## Acceptance Criteria

1. Each distribution builds and imports independently on Python 3.13.
2. Exact ordered exports, signatures, immutability, and callback non-invocation
   are tested.
3. UUIDv7/ULID format vectors, same-tick order, rollback, overflow, entropy
   failures, concurrency, and parsing boundaries are tested.
4. Measure conversion/arithmetic/format/parse/serialization covers success,
   cross-dimension rejection, duplicates, NaN/infinity, booleans, empty and
   boundary values.
5. Money never accepts binary float amounts or rates; Decimal arithmetic,
   mismatch, rounding, minor units, parse/format/serialization, and invalid ISO
   codes are tested.
6. ISO table provenance and deterministic regeneration are tested without
   network access. XML input is capped at 2 MiB, source rows at 1,024, and
   unique currencies at 512. Generation rejects oversized input, DTD/entity markers,
   unexpected roots or fields, incomplete rows, conflicting duplicate codes,
   unreasonable row counts, and output-path aliasing. Output uses same-directory
   temporary write, flush/close, `os.replace`, and failure cleanup while
   preserving the previous file.
7. Default `bluetape` installation remains core-only; focused and meta-extra
   wheel smoke tests prove isolation and imports.
8. English/Korean docs describe the same scope, non-goals, and examples.
9. SVG XML/render/audit checks pass and the full-size PNG is visually inspected.
10. Full generic tests, Ruff, format, build, actionlint, diff check, six-lens
    review, verifier, and Type A lesson gate pass before PR creation.

## Alternatives Considered

1. Recommended and approved: three independent stdlib-only packages in one
   issue/PR with subplan commits. This preserves the milestone delivery while
   keeping package boundaries reviewable.
2. Three child issues/PRs: strongest isolation but changes the approved branch
   and PR scope and adds milestone overhead.
3. Dependency-backed broad parity: shortest implementation path for some
   formats/units but imports third-party type/data policy and overextends v1.
