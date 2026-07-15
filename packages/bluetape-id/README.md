# bluetape-id

English | [한국어](README.ko.md)

Stdlib-only UUIDv4, monotonic UUIDv7, random ULID, and explicit monotonic ULID
values for Python 3.13+.

## Install

PyPI publication is on hold. The intended install shape is either the focused
distribution or the opt-in meta extra:

```bash
pip install bluetape-id
pip install "bluetape[id]"
```

The default `bluetape` install does not include this package.

## Quickstart

<!-- value-example:start -->
```python
from bluetape.id import MonotonicULIDGenerator, parse_ulid, ulid, uuid4, uuid7

random_uuid = uuid4()
sortable_uuid = uuid7()
random_ulid = ulid()
monotonic = MonotonicULIDGenerator()
first, second = monotonic.new(), monotonic.new()

assert random_uuid.version == 4
assert sortable_uuid.version == 7
assert parse_ulid(random_ulid) == random_ulid
assert first < second
```
<!-- value-example:end -->

`UUID7Generator`, `ULIDGenerator`, and `MonotonicULIDGenerator` accept explicit
clock and entropy callbacks for deterministic tests. Callback failures are
reported without copying entropy bytes into errors.

## IDs Are Not Secrets

UUIDs and ULIDs are identifiers, not credentials. UUIDv7 and ULID expose their
millisecond timestamp, and process-local monotonic ordering does not provide a
distributed total order. Do not put secrets in IDs or use ordering as an
authorization, uniqueness, or cross-process coordination guarantee.

## Generator State

The module-level `uuid7()` helper shares one process-local, thread-safe
generator. `ulid()` uses random entropy and makes no monotonic promise. Create a
`MonotonicULIDGenerator` when one process needs lock-acquisition ordering.

Monotonic state is intentionally transient. A restart, fork, upgrade, or
rollback starts fresh generator state. Applications own any stronger epoch,
machine identity, persistence, or distributed-order policy.

## Persistence and Rollback

Persist only canonical lowercase UUID strings or canonical 26-character ULID
strings. `uuid7_timestamp_ms()`, `parse_ulid()`, and `ulid_timestamp_ms()`
validate those boundaries. There is no version wrapper or serialized generator
state. Before uninstalling `bluetape-id` or `bluetape[id]`, stop imports while
retaining the canonical strings in application storage.

## Deferred Scope

KSUID is deferred until a concrete compatibility consumer exists. Snowflake
IDs require a separate design for machine identity, epoch, clock rollback, and
restart persistence. The package does not provide secrets, database keys,
distributed coordination, or package-owned background workers.
