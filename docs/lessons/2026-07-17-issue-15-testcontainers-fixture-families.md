# Issue #15 Testcontainers Fixture Family 교훈

## 배경과 결정

Issue #15는 기존 Redis-only fixture distribution을 generic container framework로 바꾸지 않고 확장했습니다. PostgreSQL과 LocalStack은 공식 Testcontainers module을 사용하며, Bluetape는 더 작은 immutable details, validation, error, loopback-binding, cleanup contract를 소유합니다.

## 재사용할 발견

### Provider가 지원하는 timeout만 노출

Testcontainers 4.14.2의 PostgreSQL provider readiness에는 public timeout input이 없으므로 wrapper는 허위 total-deadline promise를 노출하지 않습니다. LocalStack timeout은 public readiness-log wait에만 전달하고 image pull과 container creation은 provider-owned phase로 둡니다.

### Optional provider는 public import boundary에서 lazy하게 로드

`testcontainers.localstack`은 module import 시 boto3를 import합니다. 따라서 Bluetape package root를 import할 때는 얇은 adapter module만 load하고 공식 provider는 `start()` 안에서 load합니다. 이때 boto3가 없으면 focused install command를 포함한 정제된 `dependency-missing` category가 됩니다.

### 선택 service와 loopback binding은 security/capacity contract

LocalStack provider default는 모든 service를 시작하고 Docker의 일반 dynamic publishing은 wildcard interface에 bind할 수 있습니다. Wrapper는 normalized service tuple을 정확히 한 번 전달하고 ephemeral loopback binding을 요청하며 실제 runtime binding을 확인한 뒤 connection detail을 노출합니다.

### Provider-owned support container는 wrapper-owned resource가 아님

Adapter는 global Ryuk configuration을 변경하지 않습니다. Verification은 제거해야 하는 wrapper-owned PostgreSQL/LocalStack service container와 process shutdown까지 남을 수 있는 provider-owned process-wide Ryuk를 구분합니다.

## 검증 근거

- Docker-free test가 validation, lifecycle, failure redaction, cleanup retry, optional-import isolation, selected service, ambient credential, URL encoding을 다룹니다.
- Serial Docker test가 Redis, 실제 PostgreSQL 18 query, LocalStack S3 round trip, loopback binding, service-container removal을 다룹니다.
- Focused wheel smoke가 root meta extra를 바꾸지 않고 base, PostgreSQL, AWS, all-provider install shape를 입증합니다.
- Verifier artifact가 full pytest, Ruff, build, actionlint, diff, exact-head review evidence를 기록합니다.

## 향후 guard

Provider를 upgrade할 때는 pinned compatibility line을 바꾸기 전에 constructor import, readiness timeout ownership, port-binding conversion, selected-service forwarding, Ryuk behavior, error classification, wheel extra를 다시 확인합니다.
