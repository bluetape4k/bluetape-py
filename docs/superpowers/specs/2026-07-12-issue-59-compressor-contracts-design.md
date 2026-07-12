# Issue #59 Composable Compressor Contracts Design

- Issue: [#59](https://github.com/bluetape4k/bluetape-py/issues/59)
- Blocks: [#54](https://github.com/bluetape4k/bluetape-py/issues/54)
- Date: 2026-07-12
- Work type: Type A - Full Feature

## Problem

`bluetape-compression`은 bounded gzip, zlib, raw DEFLATE 함수만 제공한다. 이
함수들은 독립적으로 유용하지만 serializer나 Redis payload pipeline에서
algorithm identity, immutable configuration, decompression limit을 하나의 객체
계약으로 전달할 수 없다. Kotlin의 `bluetape4k-io`는 `Compressor` interface와
LZ4, Snappy, Zstd 구현을 제공하지만, Python에는 대응하는 조합 경계가 없다.

#59는 기존 함수 API를 보존하면서 Python-native `Protocol`과 immutable concrete
compressor를 추가한다. 기본 distribution은 stdlib-only를 유지하고 native
provider는 명시적 extras로만 설치한다. 이 작업은 Redis provider나 serializer
decorator를 구현하지 않으며, #54가 metadata-preserving serializer composition과
result-envelope integration을 소유한다.

## Constraints

- Python 3.13+만 지원한다.
- 기존 `gzip_*`, `zlib_*`, `deflate_*` 함수의 signature와 동작을 바꾸지 않는다.
- 기본 `bluetape-compression` 설치는 stdlib-only이며 native provider를 import하지
  않는다.
- 압축 해제는 caller-configured `max_output_size`를 초과하는 output을 반환하거나
  먼저 무제한으로 materialize하지 않는다.
- malformed, truncated, trailing, concatenated payload를 deterministic하게 거절한다.
- raw payload, provider diagnostic, environment detail을 error message나 log에 넣지
  않는다. 라이브러리는 실패를 자체 logging하지 않는다.
- Kotlin과 wire compatibility를 요구하지 않는다. algorithm availability,
  explicit failure, bounded decompression, immutable configuration이라는 semantic
  contract를 맞춘다.
- `bluetape[dev]`와 `bluetape[all]`은 native provider를 암묵적으로 설치하지 않는다.

## Evidence

### Repository anchors

- `packages/bluetape-compression/src/bluetape/compression/__init__.py`는 stdlib
  zlib을 lazy import하고 bounded decompression과 stable public errors를 제공한다.
- `packages/bluetape-compression/tests/test_compression.py`는 format별 success,
  malformed input, trailing data, output limits를 검증한다.
- `packages/bluetape-serde`는 immutable `SerializedPayload`와 metadata/profile
  validation을 제공한다. Compressor는 이를 해석하거나 변경하지 않고 bytes만
  transform해야 한다.
- `packages/bluetape-serde/src/bluetape/serde/fory.py`는 optional provider를 focused
  submodule과 extra 뒤에 두는 packaging precedent다.
- `bluetape4k-projects/io/io/.../Compressor.kt`와
  `CompressableBinarySerializer.kt`는 serializer 이후 compress, decompress 이후
  deserialize 순서를 사용한다.

### Provider evidence

- [python-lz4 4.4.5](https://pypi.org/project/lz4/4.4.5/)는 Python 3.13 wheels와
  `LZ4FrameDecompressor.decompress(..., max_length=...)`를 제공한다.
- [cramjam 2.11.0](https://pypi.org/project/cramjam/2.11.0/)은 Snappy raw payload의
  declared decompressed length를 decode 전에 조회할 수 있다.
- [python-zstandard 0.25.0](https://pypi.org/project/zstandard/0.25.0/)은 Python
  3.13 wheels와 incremental/streaming decompression을 제공한다.

Provider API는 release마다 변할 수 있으므로 위 버전을 package metadata와
`uv.lock`에 pin하고 source/signature 기반 contract tests로 감싼다.

## Alternatives

### A. Functions only

기존 함수만 #54에서 직접 조합한다. dependency는 늘지 않지만 algorithm identity와
fixed decompression policy가 caller convention에 흩어지고 custom serializer가
동일 contract를 type-check할 수 없다. Kotlin 사용자가 기대하는 interface-shaped
composition도 제공하지 못하므로 거절한다.

### B. Abstract base class hierarchy

`ABC`와 `@abstractmethod`로 모든 구현의 상속을 강제한다. nominal inheritance는
runtime method availability를 분명하게 보이지만 third-party compressor와 test
double이 bluetape base class를 상속해야 한다. Python structural typing과 맞지 않아
거절한다.

### C. Protocol plus immutable implementations

`typing.Protocol`로 structural contract를 정의하고 frozen, slotted dataclass
implementations를 제공한다. custom implementation은 상속 없이 type checker와
conformance suite를 사용할 수 있다. 기존 function API와 optional-provider 경계도
유지할 수 있어 이 방식을 채택한다.

Native dependency는 하나의 aggregate provider보다 각 algorithm의 검증 가능한 API를
사용한다. LZ4는 `lz4`, Snappy는 declared output length를 노출하는 `cramjam`, Zstd는
`zstandard`를 선택한다. `native` extra는 세 provider를 묶는 설치 편의일 뿐 runtime
registry나 auto-detection을 만들지 않는다.

## Public API

### Base module

```python
from typing import Protocol


class Compressor(Protocol):
    @property
    def algorithm(self) -> str: ...

    @property
    def max_output_size(self) -> int: ...

    def compress(
        self,
        data: bytes | bytearray | memoryview,
    ) -> bytes: ...

    def decompress(
        self,
        data: bytes | bytearray | memoryview,
    ) -> bytes: ...


class GzipCompressor: ...
class ZlibCompressor: ...
class DeflateCompressor: ...
```

`Compressor`는 `@runtime_checkable`이 아니다. `isinstance()`가 method signature와
behavior를 검증할 수 있다는 잘못된 기대를 만들지 않는다. Static type checking과
공통 conformance test가 contract를 검증한다.

Concrete classes는 `@dataclass(frozen=True, slots=True)`이며 constructor에서 모든
configuration을 검증한다.

- `GzipCompressor(level=9, max_output_size=DEFAULT_MAX_OUTPUT_SIZE)`
- `ZlibCompressor(level=-1, max_output_size=DEFAULT_MAX_OUTPUT_SIZE)`
- `DeflateCompressor(level=-1, max_output_size=DEFAULT_MAX_OUTPUT_SIZE)`

`algorithm`은 각각 `gzip`, `zlib`, `deflate`다. Methods는 기존 functions에 위임하여
functional API와 object API의 wire/error semantics가 갈라지지 않게 한다.

### Native module

```python
from bluetape.compression.native import (
    Lz4Compressor,
    SnappyCompressor,
    ZstdCompressor,
)
```

- `Lz4Compressor(compression_level=0, max_output_size=...)`
  - algorithm: `lz4-frame`
  - complete LZ4 frame, stored content size, content checksum
- `SnappyCompressor(max_output_size=...)`
  - algorithm: `snappy-raw`
  - raw Snappy block with declared output length preflight
- `ZstdCompressor(level=3, max_output_size=...)`
  - algorithm: `zstd-frame`
  - complete Zstd frame with content size and checksum

Provider submodule은 필요한 dependency가 없으면 payload나 environment detail 없이
해당 extra 설치 방법만 포함하는 `ModuleNotFoundError`를 발생시킨다. Root
`bluetape.compression` import는 `bluetape.compression.native`를 import하지 않는다.
`bluetape.compression.native` 자체도 provider package를 eager import하지 않는다.
각 class는 private provider loader를 통해 constructor에서 자신에게 필요한 package만
import하고 provider availability와 configuration을 함께 검증한다. 따라서 `[lz4]`만
설치한 환경에서도 같은 module에서 `SnappyCompressor`와 `ZstdCompressor` 이름을
import할 수 있지만, missing provider의 class를 생성하는 순간 focused failure를 낸다.
이미 생성된 instance가 첫 operation에서 뒤늦게 dependency failure를 내는 방식은
허용하지 않는다.

구현 배치는 다음과 같다.

```text
bluetape/compression/
├── __init__.py              # Protocol, stdlib implementations, functions
└── native/
    ├── __init__.py          # public native classes; no eager provider imports
    ├── _lz4.py
    ├── _snappy.py
    └── _zstd.py
```

## Input and Configuration Contract

- `data`는 `bytes | bytearray | memoryview`를 받으며 output은 exact `bytes`다.
- unsupported input은 coercion하지 않고 `TypeError`를 발생시킨다.
- bool은 integer configuration으로 허용하지 않는다.
- `max_output_size`는 `0 <= value < sys.maxsize`인 exact integer다.
- compression level은 algorithm이 지원하는 inclusive range로 constructor에서
  검증한다. Gzip/Zlib/Deflate는 zlib contract의 `-1..9`, LZ4는 pinned provider의
  `COMPRESSIONLEVEL_MIN..COMPRESSIONLEVEL_MAX` (`0..16`)를 사용한다. Provider가
  out-of-range 값을 clamp하도록 두지 않는다.
- Zstd는 portable named levels `1..MAX_COMPRESSION_LEVEL` (`1..22` at the pinned
  version)만 public contract로 허용한다. Provider-specific negative fast levels와
  level `0`의 implicit default는 안정적인 cross-version configuration이 아니므로
  받지 않는다.
- instances는 immutable이며 call 사이에 buffer, provider context, payload reference를
  보존하지 않는다.

## Empty Input Contract

Python의 기존 function semantics를 유지한다.

- `compress(b"")`는 algorithm별 valid compressed frame/block을 반환한다.
- `decompress(compress(b"")) == b""`다.
- bare `decompress(b"")`는 valid compressed payload가 아니므로 `CompressionError`다.

Kotlin은 null/empty input을 empty bytes로 short-circuit하지만, Python은 null을 API에
허용하지 않고 기존 wire function과 object behavior를 동일하게 유지한다. 두
생태계는 empty value round-trip 지원이라는 기능은 동일하고 byte-level 처리만 각
언어 contract를 따른다.

## Decompression Safety

모든 decoder는 limit과 정확히 같은 output은 허용하고 한 byte 초과를
`DecompressionLimitError`로 거절한다.

### stdlib formats

기존 incremental `_decompress()`를 재사용한다. gzip은 현재와 동일하게 complete
concatenated members를 허용한다. zlib과 raw DEFLATE는 단일 stream만 허용하고
trailing bytes를 거절한다. 이 기존 gzip behavior는 compatibility 때문에 유지하며
새 native formats에는 확대하지 않는다.

### LZ4

`LZ4FrameDecompressor`에 `max_output_size + 1` output budget을 주고 incremental
decode한다. `eof`가 아니거나 `unused_data`가 있으면 malformed/trailing input이다.
budget을 모두 사용하고 추가 output이 가능하면 limit failure다. One-shot
`lz4.frame.decompress()`로 먼저 전체 payload를 materialize하지 않는다.

### Snappy

raw block의 declared decompressed length를 `decompress_raw_len()`으로 먼저 읽는다.
declared size가 limit을 넘으면 provider decode 전에 거절한다. 허용된 size일 때만
decode하고 actual length가 declaration과 일치하는지 확인한다. Invalid prefix,
truncation, trailing input, provider mismatch는 `CompressionError`다. Pinned provider의
raw decoder가 trailing bytes를 corruption으로 거절한다는 contract test를 유지하며,
그 동작이 provider upgrade에서 달라지면 별도 parser 없이 upgrade를 승인하지 않는다.

### Zstd

단일 frame decoder/stream reader에서 `max_output_size + 1`까지만 읽는다. Frame
terminal과 trailing input을 확인하고 output이 limit을 넘으면
`DecompressionLimitError`다. One-shot API가 content size를 신뢰해 큰 allocation을
수행하도록 두지 않는다.

`max_output_size == sys.maxsize - 1`일 때 `+1` arithmetic이 overflow하지 않도록
budget 계산과 chunk iteration을 별도로 검증한다. 이 limit은 returned logical bytes
bound이며 이미 caller가 보유한 compressed input이나 Python allocator 전체를 제한하는
process-memory ceiling은 아니다.

## Error Contract

- configuration type errors: `TypeError`
- configuration range errors: `ValueError`
- malformed/truncated/trailing/provider decode failure: `CompressionError`
- output bound violation: `DecompressionLimitError`
- missing optional provider: `ModuleNotFoundError` with focused install guidance

Provider `Exception`은 stable public error로 변환한다. Raw provider messages는 payload
fragment, native path, build detail을 포함할 수 있기 때문이다. `MemoryError`는
`Exception`의 subclass이므로 broad translation보다 먼저 명시적으로 re-raise한다.
`KeyboardInterrupt`, `SystemExit`, `GeneratorExit` 같은 `BaseException` 계열도 변환하지
않는다. 일반 provider exception은 handler 밖에서 새 public error를 발생시켜
`__cause__`와 `__context__`가 모두 `None`이 되게 한다. 라이브러리는 실패를 logging하지
않는다.

Compression failure도 payload를 error attribute, provider exception context, closure,
global registry에 보존하지 않는다. Active Python traceback frame은 호출 argument를
일시적으로 보유할 수 있다는 언어 동작까지 제거한다고 약속하지 않는다. Tests는
public error의 attributes/cause/context를 검사하고 traceback을 해제한 뒤 caller-owned
source가 추가로 유지되지 않는지 검증한다.

## Packaging

`packages/bluetape-compression/pyproject.toml` extras:

```toml
[project.optional-dependencies]
lz4 = ["lz4==4.4.5"]
snappy = ["cramjam==2.11.0"]
zstd = ["zstandard==0.25.0"]
native = [
  "lz4==4.4.5",
  "cramjam==2.11.0",
  "zstandard==0.25.0",
]
```

Meta distribution forwarding extras:

- `bluetape[compression-lz4]`
- `bluetape[compression-snappy]`
- `bluetape[compression-zstd]`
- `bluetape[compression-native]`

`bluetape[dev]`와 `bluetape[all]`에는 provider extras를 넣지 않는다. Default
`bluetape`, `bluetape-core`, base `bluetape-compression`, 다른 focused packages에도
native dependency가 유입되지 않는다.

## Serializer and Redis Composition

#59는 serializer decorator를 구현하지 않지만 다음 integration contract를 문서화한다.

```text
value
  -> serializer.serialize(value, metadata=policy)
  -> SerializedPayload(metadata, data)
  -> compressor.compress(data)
  -> Redis result envelope(metadata, compression algorithm, compressed data)
```

Decode는 역순이다. Envelope가 algorithm을 명시하며 auto-detection하지 않는다.
Decompression은 serializer/provider access 전에 configured bound를 적용한다.
`PayloadMetadata`, schema, type, trust profile은 compression 전후 동일하게 보존한다.
Compression은 serialization policy나 trusted/untrusted classification을 바꾸지 않는다.

실제 metadata-preserving decorator, envelope schema, unknown-algorithm behavior,
rollout/rollback은 #54 spec에서 확정한다.

## Test Design

### Base contract and conformance

- `Compressor` Protocol signature and export order
- frozen/slotted concrete configuration
- exact algorithm identity and max-output property
- bytes, bytearray, memoryview round-trip
- empty input framed round-trip and bare empty decode rejection
- invalid input type and bool/range configuration rejection
- malformed, truncated, trailing input
- exact output bound success and one-byte-over failure
- implementation reuse of existing function semantics
- no logging, global registry, source retention, or call-to-call state

### Provider-specific

- LZ4 content-size/checksum frame and incremental limit path
- Snappy declared-size rejection before provider decode
- Zstd checksum/content-size frame and bounded reader path
- missing-extra errors occur at native class construction and contain only install guidance
- provider `Exception` redaction and fatal failure propagation
- provider source/signature anchors that fail loudly on incompatible upgrades

### Packaging isolation

- base wheel metadata has no native dependencies
- each focused extra installs only its provider
- aggregate extra installs all three
- base isolated venv imports `bluetape.compression` while provider specs remain absent
- focused venv constructs the selected provider implementation while unselected class names
  remain importable and fail only when constructed
- namespace packages coexist without root `bluetape/__init__.py`
- meta forwarding extras resolve exactly and default meta remains core-only

### Validation ladder

1. Targeted RED/GREEN compression tests.
2. `uv run ruff format --check .` and `uv run ruff check .`.
3. Base and native-provider targeted tests.
4. `uv sync --all-packages --extra fory --extra compression-native --locked`.
5. Full `uv run pytest` with the intended extras preserved.
6. `uv build --all-packages` and isolated wheel/import smoke checks.
7. `actionlint` and `git diff --check`.
8. Independent review reaches `P0=0 P1=0`.

Native provider tests do not use Docker or shared external state and may run in one dedicated
CI job. The base CI job first proves provider-free imports before enabling any explicit extra.

## Documentation

- Update package `README.md` and add source-equivalent `README.ko.md` with language switch.
- Explain Kotlin `interface` versus Python structural `Protocol` without claiming wire
  compatibility.
- Document focused extras, immutable configuration, empty-input difference, errors,
  logical output limits, and serializer/Redis composition order.
- Update root `README.md` and `README.ko.md` package status/install examples together.
- Add the completed user-facing change to `CHANGELOG.md`.
- No diagram is required: one interface, six implementations, and a short linear pipeline are
  clearer as an API table and code example than a generated asset.

## Failure Modes

### 1. Decompression bomb

Decoder produces or declares more than the configured bound. The wrapper rejects before full
materialization and raises `DecompressionLimitError` without returning a partial result.

### 2. Provider missing or incompatible

Base import and native class-name import remain usable. Constructing the affected native
implementation fails with focused extra guidance. Signature contract tests and pinned lock state
detect provider API drift before release.

### 3. Malformed or trailing payload

The wrapper rejects invalid terminal state, unused bytes, checksum failure, or size mismatch as
`CompressionError`. It never auto-detects a different format.

### 4. Algorithm mismatch in future Redis envelope

#54 must select the compressor from explicit envelope metadata. A caller must not try several
decoders because fallback can hide corruption and expand attack surface.

### 5. Compression expands small payloads

Compressors always honor the caller's explicit choice and do not apply a hidden size threshold.
The future serializer decorator may offer an explicit threshold only if its envelope records
whether compression was applied. #59 does not make that policy decision.

### 6. Provider error leaks diagnostics or retains payload

The wrapper emits a stable error with no provider cause/context or payload logging. Tests verify
error text and attributes, then clear the ordinary Python traceback before checking caller-owned
value release on failure paths.

## Compatibility and Migration

This is additive. Existing function imports and payloads remain valid. Callers may migrate from
functions to immutable objects without changing the chosen wire format:

```python
compressed = gzip_compress(data, level=6)

compressor = GzipCompressor(level=6)
compressed = compressor.compress(data)
```

Native formats have no previous Python contract. Their stable algorithm identifiers must be
stored with transported payloads before use in Redis or persistent storage. Provider upgrades
require compatibility tests against committed fixtures or explicit migration evidence; lockfile
updates alone are insufficient.

## Rollout and Rollback

Rollout order:

1. Add base Protocol and stdlib object implementations while preserving functions.
2. Add focused native modules and extras.
3. Prove base/provider isolation and dedicated CI.
4. Publish documentation and stable identifiers.
5. Let #54 consume only the merged public contract.

Rollback removes native forwarding extras and native implementation modules first. Base
Protocol and stdlib implementations can remain because they add no dependency and preserve
existing function behavior. If the whole feature is reverted, existing function imports and
wire payloads remain unchanged.

## Acceptance Criteria

- `Compressor` Protocol and six immutable implementations match the approved signatures and
  stable identifiers.
- Existing stdlib functions remain source- and behavior-compatible.
- Every implementation passes the common success/failure/empty/boundary conformance suite.
- LZ4, Snappy, and Zstd enforce output bounds before unbounded materialization.
- Base installation and root import remain native-provider-free.
- Focused and aggregate extras resolve the exact pinned providers and no others.
- Public errors are stable, redacted, non-logging, and do not retain caller payloads.
- English/Korean documentation and CHANGELOG accurately describe the contract and #54 boundary.
- Full validation, packaging isolation, CI, and independent review finish with `P0=0 P1=0`.

## Definition of Done

- Approved spec and implementation plan are committed before code.
- TDD evidence records failing tests before implementation and passing targeted tests after it.
- `uv run ruff check .`, `uv run ruff format --check .`, full pytest,
  `uv build --all-packages`, isolated install checks, `actionlint`, and `git diff --check` pass.
- Final review records `P0=0 P1=0`.
- PR metadata mirrors issue #59 and its final Markdown `##` section is `## DoD Status`.
- Merge remains an explicit user decision; #54 resumes only after the prerequisite is merged and
  the Redis worktree is rebased on current `origin/develop`.
