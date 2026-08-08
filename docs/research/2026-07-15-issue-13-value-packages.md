# Issue #13 ID, Measure, Money package 경계

Date: 2026-07-15 KST
Target issue: #13 - `feat: add id, measure, and money value packages`
Target milestone: `0.2.0`

## 결정

하나의 issue-scoped delivery로 독립적인 Python 3.13+ focused distribution 3개를 추가합니다.

- `bluetape-id` / `bluetape.id`: 표준 라이브러리 전용 UUID v4/v7 및 ULID value;
- `bluetape-measure` / `bluetape.measure`: 표준 라이브러리 전용 runtime dimension-checked linear unit 및 length, time, mass measured value;
- `bluetape-money` / `bluetape.money`: 표준 라이브러리 전용 ISO 4217 currency와 `decimal.Decimal` money value 및 caller-supplied exchange rate.

Package는 repository convention을 공유하지만 서로 runtime dependency를 갖지 않습니다. 모두 opt-in meta extra로 남기며 default `bluetape -> bluetape-core` dependency는 바꾸지 않습니다.

## 근거

### Identifier

- Python 3.13.14 `uuid`는 UUID version 1, 3, 4, 5 generation을 제공하지만 UUIDv7 generator는 제공하지 않습니다. 그래도 Python 3.13은 integer에서 `uuid.UUID`를 만들 수 있으므로 작은 RFC 9562 구현이 stdlib value type을 유지할 수 있습니다.
- RFC 9562는 UUIDv7의 most significant 48 bit에 Unix millisecond를 두고 같은 tick의 monotonicity를 위해 timestamp 바로 뒤에 counter를 허용합니다. Process-local generator는 외부 dependency 없이 12-bit `rand_a` counter와 random `rand_b` bit를 사용할 수 있습니다.
- Canonical ULID specification은 48-bit millisecond timestamp, 80-bit randomness, 26-character Crockford Base32 representation, canonical maximum, same-millisecond monotonic overflow behavior를 고정합니다.
- `bluetape-go/id`는 injected clock/entropy, process-local ordering, canonical parsing, identifier가 authentication secret이 아니라는 규칙의 semantic reference입니다. Go dependency type과 API는 복사하지 않습니다.

결정: UUID v4/v7과 random/monotonic ULID를 구현합니다. 첫 release의 sortable string/UUID 요구는 UUIDv7과 ULID로 충족하므로 KSUID를 보류합니다. Snowflake는 deployment-owned machine-id allocation 및 restart/clock rollback policy가 필요하지만 issue #13이 이를 정의하지 않으므로 보류합니다.

Primary source:

- [Python 3.13 uuid](https://docs.python.org/3.13/library/uuid.html)
- [RFC 9562](https://www.rfc-editor.org/rfc/rfc9562.html)
- [ULID canonical specification](https://github.com/ulid/spec)
- `../bluetape-go/id`

### Measurement

- String-valued runtime `Dimension` enum은 static checker contract나 이 repository가 아직 지원하지 않는 generic marker API 없이 dimension 간 accidental operation을 막습니다.
- `bluetape-go/measure`는 compound unit과 affine temperature를 포함하는 훨씬 넓은 family를 보여줍니다. 전체 surface를 port하면 usage evidence가 생기기 전에 Python contract를 과장하게 됩니다.

결정: 첫 release는 length, time, mass에 대한 immutable linear unit 및 measure, conversion, same-dimension arithmetic, scalar operation, parsing, formatting, primitive serialization을 지원합니다. Compound unit, area/volume/velocity, affine temperature, locale formatting, runtime에서 mutable한 registry는 보류합니다.

Source reference: `../bluetape-go/measure`.

### Money

- ISO 4217은 three-letter 및 three-digit currency code와 minor-unit 정보를 정의합니다. ISO는 code의 free use를 허용합니다.
- SIX는 공식 ISO 4217 Maintenance Agency이며 current List One을 XML/XLS로 publish합니다. List는 package code와 독립적으로 바뀌므로 import나 build 시 data를 fetch하지 않고 retrieval date가 있는 generated snapshot을 기록해야 합니다.
- `decimal.Decimal`은 issue가 요구하는 exact decimal representation을 제공합니다. Binary `float` input은 조용히 변환하지 말고 거부해야 합니다. Python 문서는 float에서 `Decimal`을 만들면 float의 정확한 binary approximation이 보존되어 예상보다 많은 digit이 생길 수 있다고 설명합니다.
- `bluetape-go/money`는 same-currency arithmetic, explicit minor unit, strict parsing, caller-owned exchange rate의 semantic reference입니다. Provider-backed network integration과 dependency type은 이 Python 첫 release 범위 밖입니다.

결정: source URL, retrieval date, SHA-256 provenance가 있는 generated current-currency table을 vendor합니다. Alphabetic 및 numeric code를 parsing하고 amount와 exchange rate는 `Decimal`로 표현하며 rounding은 명시적으로 유지합니다. Network I/O, locale inference, provider cache, rate refresh는 수행하지 않습니다.

Primary source:

- [ISO 4217 currency codes](https://www.iso.org/iso-4217-currency-codes.html)
- [SIX ISO 4217 maintenance and List One](https://www.six-group.com/en/products-services/financial-information/market-reference-data/data-standards.html)
- [Python 3.13 decimal arithmetic](https://docs.python.org/3.13/library/decimal.html)
- `../bluetape-go/money`

## Dependency와 data 경계

| Distribution | Runtime dependency | Mutable/global state | External data |
|---|---|---|---|
| `bluetape-id` | none | shared monotonic generator의 process-local lock | none |
| `bluetape-measure` | none | none | built-in unit definition |
| `bluetape-money` | none | none | generated SIX List One snapshot |

ISO snapshot updater는 caller가 download한 XML file을 받는 maintainer tool입니다. Package import, test, build, 일반 application 사용은 완전히 offline입니다.

## 거부한 대안

- Third-party UUID/ULID dependency: bounded initial format에는 불필요하며 dependency value type이나 version policy를 API로 유출합니다.
- 하나의 `bluetape-values` distribution: 독립적인 dependency/data ownership을 약화하고 향후 package evolution을 어렵게 합니다.
- 완전한 `bluetape-go` feature parity: Python-native가 아니며 첫 stable contract에 비해 범위가 넓습니다.
- Runtime ISO download 또는 locale inference: hidden I/O, freshness, network, regional-policy ownership을 도입합니다.
- Binary floating-point money constructor: issue acceptance를 위반하고 복구할 수 없는 decimal ambiguity를 만들 수 있습니다.

## 후속 후보

- 구체적인 compatibility consumer가 있을 때만 KSUID를 재평가합니다.
- Machine-id allocation, epoch, rollback, restart collision policy를 deployment contract가 소유한 뒤에만 Snowflake를 추가합니다.
- Concrete user demand와 별도의 design evidence가 있을 때만 measurement dimension 또는 affine temperature를 확장합니다.
- Provider-backed FX conversion은 pure money value package가 아닌 별도의 integration package에 추가합니다.
