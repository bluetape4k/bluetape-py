# Issue #13 ID, Measure, and Money Package Boundaries

Date: 2026-07-15 KST
Target issue: #13 - `feat: add id, measure, and money value packages`
Target milestone: `0.2.0`

## Decision

Add three independent Python 3.13+ focused distributions in one issue-scoped
delivery:

- `bluetape-id` / `bluetape.id`: stdlib-only UUID v4/v7 and ULID values;
- `bluetape-measure` / `bluetape.measure`: stdlib-only runtime
  dimension-checked linear units and measured values for length, time, and mass;
- `bluetape-money` / `bluetape.money`: stdlib-only ISO 4217 currency and
  `decimal.Decimal` money values with caller-supplied exchange rates.

The packages share repository conventions but no runtime dependency on each
other. They remain opt-in meta extras and do not change the default
`bluetape -> bluetape-core` dependency.

## Evidence

### Identifiers

- Python 3.13.14 `uuid` exposes UUID versions 1, 3, 4, and 5 generation but no
  UUIDv7 generator. Python 3.13 can still construct a `uuid.UUID` from an
  integer, so a small RFC 9562 implementation can retain the stdlib value type.
- RFC 9562 places Unix milliseconds in the most significant 48 bits of UUIDv7
  and permits a counter immediately after the timestamp for same-tick
  monotonicity. A process-local generator can therefore use a 12-bit `rand_a`
  counter plus random `rand_b` bits without external dependencies.
- The canonical ULID specification fixes a 48-bit millisecond timestamp,
  80-bit randomness, 26-character Crockford Base32 representation, canonical
  maximum, and same-millisecond monotonic overflow behavior.
- `bluetape-go/id` is a semantic reference for injected clocks/entropy,
  process-local ordering, canonical parsing, and the rule that identifiers are
  not authentication secrets. Its Go dependency types and APIs are not copied.

Decision: implement UUID v4/v7 and random/monotonic ULID. Defer KSUID because
UUIDv7 and ULID already cover the first release's sortable string/UUID needs.
Defer Snowflake because safe operation requires deployment-owned machine-id
allocation and restart/clock rollback policy that issue #13 does not define.

Primary sources:

- [Python 3.13 uuid](https://docs.python.org/3.13/library/uuid.html)
- [RFC 9562](https://www.rfc-editor.org/rfc/rfc9562.html)
- [ULID canonical specification](https://github.com/ulid/spec)
- `../bluetape-go/id`

### Measurements

- A string-valued runtime `Dimension` enum prevents accidental operations
  across dimensions without introducing a static-checker contract or generic
  marker API that this repository does not currently support.
- `bluetape-go/measure` demonstrates a much broader family including compound
  units and affine temperature. Porting that whole surface would overstate the
  Python contract before usage evidence exists.

Decision: first release supports immutable linear units and measures for
length, time, and mass, conversion, same-dimension arithmetic, scalar
operations, parsing, formatting, and primitive serialization. Compound units,
area/volume/velocity, affine temperature, locale formatting, and registries
mutable at runtime are deferred.

Source reference: `../bluetape-go/measure`.

### Money

- ISO 4217 defines three-letter and three-digit currency codes plus minor-unit
  information. ISO permits free use of the codes.
- SIX is the official ISO 4217 Maintenance Agency and publishes the current
  List One in XML/XLS form. Its list changes independently of package code, so
  the package must record a dated, generated snapshot rather than fetch data at
  import or build time.
- `decimal.Decimal` provides the exact decimal representation required by the
  issue. Binary `float` input must be rejected rather than silently converted.
  Python documents that constructing `Decimal` from a float preserves the
  float's exact binary approximation, often adding many unexpected digits.
- `bluetape-go/money` is a semantic reference for same-currency arithmetic,
  explicit minor units, strict parsing, and caller-owned exchange rates. Its
  provider-backed network integrations and dependency types are outside this
  Python first release.

Decision: vendor a generated current-currency table with source URL, retrieval
date, and SHA-256 provenance; parse alphabetic and numeric codes; represent
amounts and exchange rates with `Decimal`; keep rounding explicit; perform no
network I/O, locale inference, provider caching, or rate refresh.

Primary sources:

- [ISO 4217 currency codes](https://www.iso.org/iso-4217-currency-codes.html)
- [SIX ISO 4217 maintenance and List One](https://www.six-group.com/en/products-services/financial-information/market-reference-data/data-standards.html)
- [Python 3.13 decimal arithmetic](https://docs.python.org/3.13/library/decimal.html)
- `../bluetape-go/money`

## Dependency and Data Boundaries

| Distribution | Runtime dependencies | Mutable/global state | External data |
|---|---|---|---|
| `bluetape-id` | none | process-local locks in shared monotonic generators | none |
| `bluetape-measure` | none | none | built-in unit definitions |
| `bluetape-money` | none | none | generated SIX List One snapshot |

The ISO snapshot updater is a maintainer tool that accepts a caller-downloaded
XML file. Package import, tests, builds, and normal application use are fully
offline.

## Rejected Alternatives

- Third-party UUID/ULID dependencies: unnecessary for the bounded initial
  formats and would leak dependency value types or version policy into the API.
- One `bluetape-values` distribution: weakens independent dependency/data
  ownership and makes future package evolution harder.
- Full `bluetape-go` feature parity: not Python-native and too broad for the
  first stable contract.
- Runtime ISO downloads or locale inference: introduce hidden I/O, freshness,
  network, and regional-policy ownership.
- Binary floating-point money constructors: violate issue acceptance and can
  create irrecoverable decimal ambiguity.

## Follow-up Candidates

- Re-evaluate KSUID only with a concrete compatibility consumer.
- Add Snowflake only after machine-id allocation, epoch, rollback, and restart
  collision policy are owned by a deployment contract.
- Expand measurement dimensions or affine temperature only from concrete user
  demand and separate design evidence.
- Add provider-backed FX conversion in a separate integration package, not in
  the pure money value package.
