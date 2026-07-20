# Issue #85 Redis Host Port Readiness 교훈

## 배경

`RedisServer`는 컨테이너 내부에서 `redis-cli ping`이 성공하면 시작을 완료했다.
하지만 Docker가 동적 host port를 게시한 직후에는 컨테이너 내부 Redis가 준비됐어도
host endpoint의 TCP 연결이 잠시 거부될 수 있었다. 이 간극 때문에 전체 테스트가 거의
끝난 뒤 최초 `PING`이나 benchmark 시작이 간헐적으로 실패했다.

## 근본 원인

service readiness와 publish-boundary readiness를 하나의 조건으로 취급했다.
`ExecWaitStrategy`는 컨테이너 namespace 안의 Redis만 증명하며, caller가 사용하는
`host:mapped_port` 경로는 검증하지 않는다. 따라서 내부 readiness 성공만으로
`RedisServer.start()`의 공개 계약을 충족했다고 볼 수 없었다.

## 결정

- 내부 `redis-cli ping` 뒤에 host의 published port 연결을 순차 검증한다.
- Testcontainers 4.14.2의 `CompositeWaitStrategy`, `ExecWaitStrategy`,
  `PortWaitStrategy`를 재사용해 별도 dependency나 polling 구현을 추가하지 않는다.
- 기존 `startup_timeout`을 두 readiness strategy에 동일하게 적용한다.
- host port timeout은 기존 `readiness-timeout` 분류와 startup 실패 cleanup 경로를
  그대로 사용한다.
- connection detail의 형태와 public API는 변경하지 않는다.

## 검증 원칙

- 회귀 테스트는 내부 strategy 성공 뒤 host strategy가 실패하는 순서를 직접 실행해,
  내부 readiness만으로는 충분하지 않음을 결정적으로 증명해야 한다.
- Docker/Testcontainers 검증은 직렬 실행한다. 간헐적 lifecycle 결함은 단일 통과가
  아니라 이전 실패 consumer의 반복 실행으로 확인한다.
- clean source를 요구하는 benchmark smoke는 변경을 커밋한 정확한 head에서 실행한다.

## 향후 지침

동적 port를 외부에 노출하는 container wrapper는 최소 두 경계를 분리해 검토한다.

1. container namespace 안에서 service가 요청을 처리할 준비가 됐는가.
2. caller가 사용하는 host 또는 gateway의 published endpoint가 연결 가능한가.

공개 `start()`가 외부 connection detail을 반환한다면 두 번째 경계까지 통과해야 한다.
