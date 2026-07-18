# Issue #16 AWS, Graph, Text, and Image Adapter Boundaries

Issue: [#16](https://github.com/bluetape4k/bluetape-py/issues/16)
Milestone: `0.2.0`
Date: 2026-07-18

## Decision

Do not port the broad JVM, Go, graph, text, or image surfaces into Python.
Python libraries already own most service and algorithm APIs. Bluetape should
publish only narrow contracts that add bounded behavior, deterministic result
handling, or cross-package integration that callers cannot obtain by using the
selected dependency directly.

| Area | 0.2.x direction | Classification |
|---|---|---|
| AWS | Prototype a synchronous, optional `bluetape-aws` package around caller-supplied low-level Boto3 clients. Limit it to proven batch partial-result and bounded retry behavior. | Light wrapper |
| Graph | Prove one domain example with direct NetworkX and Neo4j-driver use. Add backend-neutral values only after two independent consumers need the same values. | Example first; conditional values |
| Text | Build an optional bounded literal multi-pattern matcher and masking package after a focused dependency benchmark. | Light wrapper |
| Image | Build an optional Pillow-backed bounded single-image transform only after its limits and codec contract are designed. Keep pyvips, barcode, OCR, and CAPTCHA outside the first package. | Light wrapper; examples/defer for heavy features |

This research decision does not authorize implementation. Issues #26-#29 must
each produce a focused design, dependency and license review, tests, packaging
impact, and release evidence before code is added.

## Selection Rule

A dependency-backed package is justified only when it owns at least one stable
bluetape invariant:

- bounded input, output, attempts, matches, pixels, or memory-related policy;
- deterministic preservation of partial successes and failures;
- caller-owned clients, sessions, credentials, storage, transactions, and
  lifecycle;
- safe errors that exclude credentials, payloads, text, image bytes, and
  caller paths;
- a contract proven by more than one consumer when it claims to be backend
  neutral.

Convenience aliases, generated SDK methods, generic repositories, broad
facades, model downloaders, service runtimes, and dependency lifecycle
ownership fail this rule.

## AWS Boundary

Use Boto3/Botocore as the synchronous baseline. Boto3 low-level clients already
map closely to AWS service APIs, and its resource interface receives no new
features. A broad wrapper would duplicate a generated SDK and its error model.
The optional package should accept caller-created clients and must not create a
default session, select credentials, own endpoint discovery, or add an
uncoordinated retry layer.

Candidate first proofs:

- SQS batch-result normalization that preserves every successful and failed
  entry and leaves retry/backoff to the caller;
- DynamoDB `BatchWriteItem` chunking and bounded resubmission of only
  `UnprocessedItems`, with caller-provided delay/cancellation and the final
  partial result;
- an S3 checksum or payload-envelope helper only if another bluetape package
  demonstrates a shared contract. Ordinary upload/download, pagination,
  multipart transfer, waiters, and presigning remain direct Boto3 use or
  examples.

`aioboto3` and `aiobotocore` are deferred from the supported 0.2.x surface.
They add async context-manager cleanup and cancellation requirements while
tightly coupling their versions to Botocore. An async experiment may be an
example, but it must not establish public parity with the synchronous package.

`testcontainers[localstack]` remains an optional test dependency. Tests pin the
container image, use explicit test credentials and endpoint URLs, and never
treat emulator success as proof of AWS production fidelity. Live AWS tests are
explicit opt-in.

### AWS risks and non-goals

- Boto3/Botocore generated models release frequently; wrappers must avoid
  copying service request and response types.
- SDK retry modes already exist. Stacking a package retry can multiply attempts
  and latency, so the first helper owns only its explicitly bounded partial
  batch loop.
- Credentials, presigned URLs, message bodies, DynamoDB values, and KMS data
  must never enter errors or logs.
- 0.2.x excludes async AWS APIs, global clients/sessions, credential providers,
  S3 filesystem abstractions, long-running SQS consumers, SNS, EventBridge,
  Kinesis, Step Functions, KMS, Secrets Manager, SSM, RDS IAM, leader election,
  and general provider integration.

Issue [#26](https://github.com/bluetape4k/bluetape-py/issues/26) should become a
bounded Boto3 prototype for SQS partial results, DynamoDB unprocessed-item
handling, and at most one proven S3 envelope/checksum helper. The remaining
service list is removed from its first slice.

## Graph Boundary

Do not create a new graph container or common backend API in 0.2.x. NetworkX
already provides Python graph types and algorithms; applications should depend
on it directly. A conversion example can establish whether common immutable
`Node`, `Edge`, or `Path` values are useful, but those values become first-class
only after at least two independent I/O or domain consumers need the same
representation.

Use the official Neo4j driver directly for the first database proof. The
application owns the driver, session, database selection, TLS, credentials,
transactions, and Cypher. Managed transaction callbacks can be retried and
therefore must be idempotent. Sessions are not safe to share between concurrent
threads/tasks, and async cancellation may leave commit outcome uncertain.
Wrappers must not hide these semantics.

NetworkX backend dispatch is not a foundation for a bluetape conformance suite:
its backend interface changes, algorithm support is partial, conversion can be
expensive, and fallback/caching semantics vary. GraphML ingestion is also
deferred because NetworkX warns that its XML parser is unsafe for untrusted
input.

### Graph risks and non-goals

- Neo4j query values must use parameter binding; connection and transaction
  failures must retain official-driver meaning.
- A Testcontainers Neo4j proof uses the current community module and keeps that
  import boundary isolated from production code.
- 0.2.x excludes a backend-neutral repository/session/query/schema DSL,
  generic traversal or algorithm facade, public untrusted GraphML ingestion,
  and adapters for Memgraph, AGE, TinkerPop/Gremlin, or FalkorDB.
- Multi-backend conformance requires a second independent backend to prove the
  same Python-shaped contract before a new issue is justified.

Issue [#27](https://github.com/bluetape4k/bluetape-py/issues/27) should become a
bounded values and interoperability proof: direct NetworkX conversion, one
official Neo4j-driver domain example, and resource/cancellation/retry tests.

## Text Boundary

An optional `bluetape-text` distribution may own bounded literal
multi-pattern matching and masking. It should benchmark `ahocorasick-rs`,
`pyahocorasick`, and a small stdlib baseline before selecting a dependency.
The public contract is exact, case-sensitive, code-point-indexed matching with
deterministic result order and union-based masking of overlapping spans.

The package must reject empty patterns and bound pattern count, total pattern
length, input length, match count, and any high-memory automaton mode. It must
not expose dependency persistence formats: `pyahocorasick` documents unsafe
pickle and save/load input, consistent with Python's warning that unpickling
untrusted data can execute arbitrary code. Persisted automata would add an
unnecessary trust boundary.

Do not normalize or case-fold internally. Python indices count code points, not
grapheme clusters; normalization can change offsets and partial masking can
split combining sequences, Hangul Jamo, or emoji sequences. Callers that need
normalization must apply the same transformation to both patterns and the text
they intend to mask.

Tokenizers and language detectors remain direct-dependency examples. Hugging
Face Tokenizers already owns normalization, pre-tokenization, model,
post-processing, artifact, and offset semantics. Korean/Japanese analyzers add
large dictionaries, native code, model data, and separate licenses. Lingua is
offline and capable but its model-bearing wheels and policy choices do not
justify a bluetape facade. Archived fastText is rejected as a new dependency.

### Text risks and non-goals

- Pin and hash the selected wheel; verify Python 3.13 and target-platform wheel
  coverage, including the musllinux gap where applicable.
- Never include source text, patterns, or matched substrings in errors/logs.
- 0.2.x excludes tokenizer and language-detector abstractions, dictionary/model
  downloads, normalization, case folding, homoglyph/grapheme handling, fuzzy,
  regex or semantic moderation, persisted automata, and cross-language index
  compatibility.

Issue [#28](https://github.com/bluetape4k/bluetape-py/issues/28) should become
`feat: add bounded literal text matching and masking`, with dependency
benchmarks, Unicode boundary tests, deterministic overlap semantics, and safe
failure tests.

## Image Boundary

Pillow is the only suitable first-package candidate because it is the common
Python-native codec and transform baseline. The optional package should expose
one bounded single-image transform with an explicit input-format allowlist,
maximum encoded bytes, width, height, decoded pixels, output dimensions, and
output pixels. It should support only the codecs and resize modes proved by its
tests, stage output before publication, and remove metadata by default unless a
later contract explicitly preserves selected fields.

Pillow's decompression-bomb check is necessary but not sufficient. It is a
process-global pixel threshold and does not bound encoded bytes, output work,
high-quality resampling CPU, frames, metadata, or application-specific memory.
The wrapper must apply request-local limits and convert
`DecompressionBombWarning` into a controlled failure without mutating global
Pillow settings.

`pyvips` is deferred to a separate benchmark issue. It can evaluate pixels on
demand and limit operation-cache memory/files, but it introduces libvips ABI,
codec-build, native packaging, cache/process-global configuration, and runtime
availability concerns. A Pillow API must not pretend that a future pyvips
backend has identical failure, metadata, animation, or codec semantics.

Barcode/QR, OCR, CAPTCHA, framework routes, storage, CDN, and S3 integration
remain examples or later focused research. Barcode generation/decoding can use
its selected provider directly until at least two providers prove a stable
result model. OCR carries native engine/model/language-data lifecycle and does
not belong in the initial image package.

### Image risks and non-goals

- Malformed or adversarial codecs can consume CPU, memory, descriptors, or
  native resources. The service boundary still owns concurrency, process
  isolation, timeout, and admission control.
- Errors must exclude image bytes, metadata, file paths, and native cause text.
- 0.2.x excludes pyvips/libvips, animation, SVG/PDF rasterization, AVIF/HEIC/TIFF
  breadth, EXIF editing, arbitrary effects, similarity, OCR, CAPTCHA, barcode,
  storage, CDN, web-framework integration, and a multi-backend facade.

Issue [#29](https://github.com/bluetape4k/bluetape-py/issues/29) should become a
bounded Pillow single-image transform design and proof. Barcode, OCR, and
pyvips are removed from its first implementation slice.

## Dependency And Ownership Matrix

| Candidate | License / footprint concern | Owner retained by caller | Result |
|---|---|---|---|
| Boto3/Botocore | Apache-2.0; rapid generated-model releases | clients, credentials, endpoints, retry mode | Select for narrow sync proof |
| aioboto3/aiobotocore | Apache-2.0; tight version coupling | async lifecycle and cancellation | Example/defer |
| NetworkX | BSD-3-Clause; optional scientific extras can be heavy | graph and algorithm selection | Direct use/example |
| Neo4j driver | `Apache-2.0 AND Python-2.0`; service runtime | driver, sessions, TLS, transactions, Cypher | Direct proof first |
| ahocorasick-rs / pyahocorasick | Apache-2.0 vs BSD/Public-Domain; wheel/platform and persistence differences | input normalization and privacy policy | Benchmark for light wrapper |
| Tokenizers / language models | native wheels, dictionaries/models, artifact drift | model, cache, normalization, offsets | Example only |
| Pillow | HPND-style Pillow license; codec and decompression risk | service admission, concurrency, timeouts | Select for bounded proof |
| pyvips/libvips | MIT binding plus `LGPL-2.1-or-later` native runtime and codec matrix | native installation, global cache/runtime policy | Separate benchmark/defer |

## Source Repositories Inspected

- `bluetape-go`: `dynamodb/batchwrite`, AWS examples, `graph`, `textsearch`, and
  `imagekit` bounded transform contracts.
- `bluetape4k-aws`: broad SDK wrappers and emulator-backed examples, used only
  as a scope-warning reference rather than a Python API template.
- `bluetape4k-graph`: multi-backend repository surfaces, used to identify the
  conformance burden that Python 0.2.x should not inherit.
- `bluetape4k-text`: tokenizer/model bounds and dependency separation.
- `bluetape4k-image`: image, barcode, OCR, native libvips, and framework module
  separation.

## Primary Sources

- [Boto3 clients](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/clients.html),
  [resources guidance](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/resources.html),
  [credentials](https://docs.aws.amazon.com/boto3/latest/guide/credentials.html),
  and [retries](https://docs.aws.amazon.com/boto3/latest/guide/retries.html).
- [DynamoDB BatchWriteItem](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_BatchWriteItem.html)
  and [error handling](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Programming.Errors.html),
  plus [SQS SendMessageBatch](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/APIReference/API_SendMessageBatch.html).
- [aioboto3](https://github.com/terricain/aioboto3),
  [aiobotocore](https://github.com/aio-libs/aiobotocore),
  [Testcontainers LocalStack](https://testcontainers-python.readthedocs.io/en/latest/modules/localstack/README.html),
  and [LocalStack Boto3 connection](https://docs.localstack.cloud/aws/connecting/aws-sdks/python-boto3/).
- [NetworkX graph types](https://networkx.org/documentation/stable/reference/introduction.html),
  [backends](https://networkx.org/documentation/stable/reference/backends.html),
  and [GraphML warning](https://networkx.org/documentation/stable/reference/readwrite/graphml.html).
- [Neo4j Python driver](https://github.com/neo4j/neo4j-python-driver),
  [transactions](https://neo4j.com/docs/python-manual/current/transactions/),
  and [async API](https://neo4j.com/docs/api/python-driver/current/async_api.html).
- [ahocorasick-rs](https://github.com/G-Research/ahocorasick_rs),
  [pyahocorasick](https://github.com/WojciechMula/pyahocorasick),
  [Python pickle security](https://docs.python.org/3/library/pickle.html),
  [Tokenizers pipeline](https://huggingface.co/docs/tokenizers/pipeline),
  and [Lingua](https://github.com/pemistahl/lingua-py).
- [Pillow Image safeguards](https://pillow.readthedocs.io/en/stable/reference/Image.html),
  [pyvips](https://github.com/libvips/pyvips), and
  [pyvips runtime controls](https://libvips.github.io/pyvips/voperation.html).

## Follow-up State

No new follow-up issues are needed. Existing issues #26-#29 own the four
focused proof lanes and should be narrowed in place. Any later async AWS,
second graph backend, tokenizer/model, pyvips, barcode, or OCR work requires
fresh evidence and its own issue rather than being restored to those first
slices.

## 0.2.x Global Non-Goals

- Cross-provider or cross-backend facades without two proven consumers.
- Package-owned clients, sessions, credentials, model downloads, background
  workers, global registries, logging, or lifecycle.
- Default `bluetape` installation of any AWS, graph, text, or image dependency.
- Claims of full service, backend, language, codec, or platform compatibility.
- Production implementation directly from this research issue.
