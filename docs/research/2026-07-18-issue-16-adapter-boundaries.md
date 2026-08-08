# Issue #16 AWS, Graph, Text, Image adapter 경계

Issue: [#16](https://github.com/bluetape4k/bluetape-py/issues/16)
Milestone: `0.2.0`
Date: 2026-07-18

## 결정

JVM, Go, graph, text, image의 넓은 surface를 Python으로 port하지 않습니다. Python library가 대부분의 service와 algorithm API를 이미 소유하므로, bluetape는 선택한 dependency를 직접 사용하는 것만으로 얻을 수 없는 bounded behavior, deterministic result handling, cross-package integration을 추가하는 좁은 contract만 publish합니다.

| 영역 | `0.2.x` 방향 | 분류 |
|---|---|---|
| AWS | caller가 제공한 low-level Boto3 client를 감싸는 optional `bluetape-aws`를 prototype합니다. 검증된 batch partial-result와 bounded retry만 포함합니다. | Light wrapper |
| Graph | NetworkX와 Neo4j-driver를 직접 사용하는 domain example 하나를 검증합니다. 두 독립 consumer가 같은 value를 필요로 할 때만 backend-neutral value를 추가합니다. | Example first; conditional values |
| Text | 집중 dependency benchmark 후 bounded literal multi-pattern matcher와 masking package를 optional로 만듭니다. | Light wrapper |
| Image | limit과 codec contract를 설계한 뒤에만 Pillow 기반 bounded single-image transform을 만듭니다. pyvips, barcode, OCR, CAPTCHA는 첫 package에서 제외합니다. | Light wrapper; examples/defer for heavy features |

이 research decision은 implementation을 승인하지 않습니다. Issue #26-#29는 각각 focused design, dependency 및 license review, test, packaging impact, release evidence를 만든 뒤에만 code를 추가해야 합니다.

## 선택 규칙

Dependency-backed package는 다음 중 하나 이상의 안정적인 bluetape invariant를 소유할 때만 정당화됩니다.

- input, output, attempt, match, pixel, memory 관련 policy의 bound;
- partial success와 failure의 deterministic preservation;
- caller-owned client, session, credential, storage, transaction, lifecycle;
- credential, payload, text, image bytes, caller path를 제외하는 safe error;
- backend-neutral을 주장한다면 둘 이상의 consumer로 입증한 contract.

Convenience alias, generated SDK method, generic repository, broad facade, model downloader, service runtime, dependency lifecycle ownership은 이 규칙을 통과하지 못합니다.

## AWS 경계

Boto3/Botocore를 synchronous baseline으로 사용합니다. Low-level client가 AWS service API와 가깝고 resource interface가 새 기능을 제공하지 않으므로 broad wrapper는 generated SDK와 error model을 중복합니다. Optional package는 caller가 만든 client를 받아야 하며 default session을 만들거나 credential을 선택하거나 endpoint discovery를 소유하거나 조정되지 않은 retry layer를 추가해서는 안 됩니다.

첫 proof 후보:

- SQS batch-result normalization: 모든 성공/실패 entry를 보존하고 retry/backoff는 caller에게 둡니다.
- DynamoDB `BatchWriteItem`: chunking과 `UnprocessedItems`만 bounded resubmission하며 caller가 delay/cancellation과 최종 partial result를 제공합니다.
- 다른 bluetape package가 shared contract를 보일 때만 S3 checksum 또는 payload-envelope helper를 고려합니다. 일반 upload/download, pagination, multipart transfer, waiter, presigning은 직접 Boto3 사용 또는 example로 둡니다.

`aioboto3`와 `aiobotocore`는 지원하는 `0.2.x` surface에서 보류합니다. Async context-manager cleanup과 cancellation 요구를 추가하면서 Botocore version과 강하게 결합하기 때문입니다. Async experiment은 example일 수 있지만 synchronous package와 public parity를 만들지는 않습니다.

`testcontainers[localstack]`은 optional test dependency로 유지합니다. Test는 container image를 pin하고 명시적인 test credential과 endpoint URL을 사용하며 emulator 성공을 AWS production fidelity의 증거로 취급하지 않습니다. Live AWS test는 명시적인 opt-in입니다.

### AWS 위험과 non-goal

- Boto3/Botocore generated model은 자주 release되므로 wrapper는 service request/response type을 복사하지 않습니다.
- SDK retry mode가 이미 있습니다. Package retry를 겹치면 attempt와 latency가 곱해질 수 있으므로 첫 helper는 명시적으로 bounded한 partial batch loop만 소유합니다.
- Credential, presigned URL, message body, DynamoDB value, KMS data를 error나 log에 넣지 않습니다.
- `0.2.x`에서는 async AWS API, global client/session, credential provider, S3 filesystem abstraction, long-running SQS consumer, SNS, EventBridge, Kinesis, Step Functions, KMS, Secrets Manager, SSM, RDS IAM, leader election, general provider integration을 제외합니다.

Issue [#26](https://github.com/bluetape4k/bluetape-py/issues/26)은 SQS partial result, DynamoDB unprocessed-item handling, 검증된 S3 envelope/checksum helper 최대 하나를 다루는 bounded Boto3 prototype이 되어야 합니다. 나머지 service list는 첫 slice에서 제거합니다.

## Graph 경계

`0.2.x`에서는 새 graph container나 common backend API를 만들지 않습니다. NetworkX가 Python graph type과 algorithm을 이미 제공하므로 application이 직접 의존해야 합니다. Conversion example로 immutable `Node`, `Edge`, `Path` value가 유용한지 확인하되, 두 독립적인 I/O 또는 domain consumer가 같은 representation을 필요로 할 때만 first-class value로 승격합니다.

첫 database proof에는 공식 Neo4j driver를 직접 사용합니다. Driver, session, database selection, TLS, credential, transaction, Cypher는 application이 소유합니다. Managed transaction callback은 retry될 수 있으므로 idempotent여야 합니다. Session은 concurrent thread/task 간에 안전하게 공유할 수 없고 async cancellation은 commit 결과를 불확정하게 만들 수 있으므로 wrapper가 이 semantics를 숨겨서는 안 됩니다.

NetworkX backend dispatch는 bluetape conformance suite의 기반으로 삼지 않습니다. Backend interface가 바뀌고, algorithm support가 부분적이며, conversion이 비싸고, fallback/cache semantics가 다릅니다. NetworkX는 XML parser가 untrusted input에 안전하지 않다고 경고하므로 GraphML ingestion도 보류합니다.

### Graph 위험과 non-goal

- Neo4j query value는 parameter binding을 사용해야 하며 connection/transaction failure는 공식 driver의 의미를 유지해야 합니다.
- Testcontainers Neo4j proof는 현재 community module을 사용하고 production code와 import boundary를 격리합니다.
- `0.2.x`에서는 backend-neutral repository/session/query/schema DSL, generic traversal/algorithm facade, public untrusted GraphML ingestion, Memgraph, AGE, TinkerPop/Gremlin, FalkorDB adapter를 제외합니다.
- Multi-backend conformance는 새 issue를 정당화하기 전에 두 번째 독립 backend가 같은 Python-shaped contract를 입증해야 합니다.

Issue [#27](https://github.com/bluetape4k/bluetape-py/issues/27)은 bounded value와 interoperability proof가 되어야 합니다. 직접 NetworkX conversion, 공식 Neo4j-driver domain example 하나, resource/cancellation/retry test를 포함합니다.

## Text 경계

Optional `bluetape-text` distribution이 bounded literal multi-pattern matching과 masking을 소유할 수 있습니다. Dependency를 선택하기 전에 `ahocorasick-rs`, `pyahocorasick`, 작은 stdlib baseline을 benchmark합니다. Public contract는 exact, case-sensitive, code-point-indexed matching과 deterministic result order, overlapping span의 union-based masking입니다.

Empty pattern을 거부하고 pattern count, total pattern length, input length, match count, high-memory automaton mode를 제한해야 합니다. Dependency persistence format을 노출하지 않습니다. `pyahocorasick`은 unsafe pickle과 save/load input을 문서화하며 Python도 untrusted data unpickle이 arbitrary code를 실행할 수 있다고 경고합니다. Persisted automaton은 불필요한 trust boundary를 추가합니다.

내부에서 normalize 또는 case-fold하지 않습니다. Python index는 grapheme cluster가 아닌 code point를 세며 normalization은 offset을 바꿀 수 있고 partial masking은 combining sequence, Hangul Jamo, emoji sequence를 분리할 수 있습니다. Normalization이 필요한 caller는 pattern과 mask 대상 text에 같은 변환을 적용해야 합니다.

Tokenizer와 language detector는 direct-dependency example으로 둡니다. Hugging Face Tokenizers가 normalization, pre-tokenization, model, post-processing, artifact, offset semantics를 이미 소유합니다. Korean/Japanese analyzer는 큰 dictionary, native code, model data, 별도 license를 추가합니다. Lingua는 offline이고 성능이 충분하지만 model-bearing wheel과 policy choice가 bluetape facade를 정당화하지 않습니다. Archived fastText는 새 dependency로 거부합니다.

### Text 위험과 non-goal

- 선택한 wheel을 pin/hash하고 Python 3.13 및 target-platform wheel coverage를 검증합니다. 필요한 경우 musllinux gap도 확인합니다.
- Source text, pattern, matched substring을 error/log에 넣지 않습니다.
- `0.2.x`에서는 tokenizer/language-detector abstraction, dictionary/model download, normalization, case folding, homoglyph/grapheme handling, fuzzy/regex/semantic moderation, persisted automaton, cross-language index compatibility를 제외합니다.

Issue [#28](https://github.com/bluetape4k/bluetape-py/issues/28)은 `feat: add bounded literal text matching and masking`이 되어야 하며 dependency benchmark, Unicode boundary test, deterministic overlap semantics, safe failure test를 포함합니다.

## Image 경계

Pillow는 Python-native codec와 transform baseline인 유일한 첫 package 후보입니다. Optional package는 explicit input-format allowlist, maximum encoded byte, width, height, decoded pixel, output dimension, output pixel을 가진 bounded single-image transform 하나를 제공합니다. Test로 입증한 codec과 resize mode만 지원하고 publication 전에 output을 stage하며, 이후 contract가 선택 field를 보존하도록 정하지 않는 한 metadata는 기본적으로 제거합니다.

Pillow의 decompression-bomb check는 필요하지만 충분하지 않습니다. 이는 process-global pixel threshold일 뿐 encoded byte, output work, high-quality resampling CPU, frame, metadata, application-specific memory를 제한하지 않습니다. Wrapper는 request-local limit을 적용하고 global Pillow setting을 변경하지 않은 채 `DecompressionBombWarning`을 controlled failure로 변환해야 합니다.

`pyvips`는 별도의 benchmark issue로 보류합니다. Pixel을 on demand로 평가하고 operation-cache memory/file을 제한할 수 있지만 libvips ABI, codec build, native packaging, cache/process-global configuration, runtime availability 문제가 추가됩니다. Pillow API가 향후 pyvips backend의 failure, metadata, animation, codec semantics가 동일하다고 가장해서는 안 됩니다.

Barcode/QR, OCR, CAPTCHA, framework route, storage, CDN, S3 integration은 example 또는 후속 focused research로 둡니다. 적어도 두 provider가 stable result model을 입증하기 전에는 barcode generation/decoding을 선택한 provider에 직접 위임합니다. OCR은 native engine/model/language-data lifecycle이 있어 초기 image package에 넣지 않습니다.

### Image 위험과 non-goal

- Malformed/adversarial codec은 CPU, memory, descriptor, native resource를 소모할 수 있습니다. Service boundary가 concurrency, process isolation, timeout, admission control을 소유합니다.
- Error에는 image byte, metadata, file path, native cause text를 넣지 않습니다.
- `0.2.x`에서는 pyvips/libvips, animation, SVG/PDF rasterization, AVIF/HEIC/TIFF breadth, EXIF editing, arbitrary effect, similarity, OCR, CAPTCHA, barcode, storage, CDN, web-framework integration, multi-backend facade를 제외합니다.

Issue [#29](https://github.com/bluetape4k/bluetape-py/issues/29)은 bounded Pillow single-image transform design과 proof가 되어야 합니다. Barcode, OCR, pyvips는 첫 implementation slice에서 제거합니다.

## Dependency와 ownership matrix

| Candidate | License / footprint concern | Caller가 계속 소유 | 결과 |
|---|---|---|---|
| Boto3/Botocore | Apache-2.0; rapid generated-model release | client, credential, endpoint, retry mode | narrow sync proof로 선택 |
| aioboto3/aiobotocore | Apache-2.0; tight version coupling | async lifecycle와 cancellation | Example/defer |
| NetworkX | BSD-3-Clause; optional scientific extra가 무거울 수 있음 | graph와 algorithm 선택 | Direct use/example |
| Neo4j driver | `Apache-2.0 AND Python-2.0`; service runtime | driver, session, TLS, transaction, Cypher | Direct proof first |
| ahocorasick-rs / pyahocorasick | Apache-2.0 vs BSD/Public-Domain; wheel/platform/persistence 차이 | input normalization과 privacy policy | Light wrapper용 benchmark |
| Tokenizers / language model | native wheel, dictionary/model, artifact drift | model, cache, normalization, offset | Example only |
| Pillow | HPND-style Pillow license; codec와 decompression risk | service admission, concurrency, timeout | Bounded proof로 선택 |
| pyvips/libvips | MIT binding + `LGPL-2.1-or-later` native runtime과 codec matrix | native install, global cache/runtime policy | Separate benchmark/defer |

## 조사한 source repository

- `bluetape-go`: `dynamodb/batchwrite`, AWS example, `graph`, `textsearch`, `imagekit` bounded transform contract.
- `bluetape4k-aws`: broad SDK wrapper와 emulator-backed example. Python API template가 아니라 scope-warning reference로만 사용합니다.
- `bluetape4k-graph`: multi-backend repository surface. Python `0.2.x`가 물려받지 말아야 할 conformance burden을 식별하는 데 사용합니다.
- `bluetape4k-text`: tokenizer/model bound와 dependency separation.
- `bluetape4k-image`: image, barcode, OCR, native libvips, framework module separation.

## Primary source

- [Boto3 clients](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/clients.html), [resources guidance](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/resources.html), [credentials](https://docs.aws.amazon.com/boto3/latest/guide/credentials.html), [retries](https://docs.aws.amazon.com/boto3/latest/guide/retries.html).
- [DynamoDB BatchWriteItem](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_BatchWriteItem.html), [error handling](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Programming.Errors.html), [SQS SendMessageBatch](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/APIReference/API_SendMessageBatch.html).
- [aioboto3](https://github.com/terricain/aioboto3), [aiobotocore](https://github.com/aio-libs/aiobotocore), [Testcontainers LocalStack](https://testcontainers-python.readthedocs.io/en/latest/modules/localstack/README.html), [LocalStack Boto3 connection](https://docs.localstack.cloud/aws/connecting/aws-sdks/python-boto3/).
- [NetworkX graph types](https://networkx.org/documentation/stable/reference/introduction.html), [backends](https://networkx.org/documentation/stable/reference/backends.html), [GraphML warning](https://networkx.org/documentation/stable/reference/readwrite/graphml.html).
- [Neo4j Python driver](https://github.com/neo4j/neo4j-python-driver), [transactions](https://neo4j.com/docs/python-manual/current/transactions/), [async API](https://neo4j.com/docs/api/python-driver/current/async_api.html).
- [ahocorasick-rs](https://github.com/G-Research/ahocorasick_rs), [pyahocorasick](https://github.com/WojciechMula/pyahocorasick), [Python pickle security](https://docs.python.org/3/library/pickle.html), [Tokenizers pipeline](https://huggingface.co/docs/tokenizers/pipeline), [Lingua](https://github.com/pemistahl/lingua-py).
- [Pillow Image safeguards](https://pillow.readthedocs.io/en/stable/reference/Image.html), [pyvips](https://github.com/libvips/pyvips), [pyvips runtime controls](https://libvips.github.io/pyvips/voperation.html).

## 후속 상태

새 follow-up issue는 필요하지 않습니다. 기존 issue #26-#29가 네 개의 focused proof lane을 소유하므로 해당 issue를 현재 위치에서 좁힙니다. 이후 async AWS, 두 번째 graph backend, tokenizer/model, pyvips, barcode, OCR 작업은 fresh evidence와 별도 issue가 필요하며 첫 slice로 되돌리지 않습니다.

## `0.2.x` 공통 non-goal

- 두 consumer가 입증되기 전의 cross-provider/cross-backend facade.
- Package-owned client, session, credential, model download, background worker, global registry, logging, lifecycle.
- AWS, graph, text, image dependency의 default `bluetape` install 포함.
- Full service, backend, language, codec, platform compatibility 주장.
- 이 research issue에서 직접 production implementation을 시작하는 것.
