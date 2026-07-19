# Issue #17 다양한 저장소를 위한 leader lock 계약 교훈

## 맥락과 결정

Leader 기능을 Redis 구현 하나로 시작하면 public API가 Redis key, client, retry,
topology에 묶인다. 다른 언어의 `bluetape4k-leader`처럼 leader core는 여러 repository와
backend가 구현할 수 있는 계약을 제공하고, Redis는 별도 opt-in distribution으로 두었다.
Python에서는 Kotlin 구조를 기계적으로 복사하지 않고 protocol, immutable result/value,
namespace package, sync/async 분리라는 Python-native 형태로 같은 경계 원칙을 구현했다.

Core `bluetape-leader`는 stdlib-only이며 ownership, fencing, lifecycle outcome과 오류만
정의한다. `bluetape-leader-redis`가 exact redis-py client, Lua, key derivation, timing,
ACL, single-primary 제약을 소유한다. 이 분리는 다음 SQL, ZooKeeper, Consul 같은 adapter가
core public surface를 바꾸지 않고 같은 leader 의미를 구현하게 한다.

## 재사용 가능한 발견

### Leader identity와 fencing capability는 다르다

`node_id`와 audit ID는 운영 상관관계일 뿐 소유권이나 stale-write 방지 능력이 아니다.
Acquire마다 생성하는 비밀 owner token이 Redis lease 소유권을 증명하고, 단조 증가 integer
fencing token만 downstream write ordering을 증명한다. 로그와 metric에는 이 값들을 넣지
않고 public operation/outcome 같은 낮은 cardinality 범주만 사용한다.

### Backend duration으로 안전성을 검증해야 한다

Python `timedelta`가 microsecond를 보존해도 Redis `PEXPIRE`는 millisecond integer를
받는다. Renewal 안전성을 원래 duration과 비교하면 backend TTL보다 늦은 완료를 허용할
수 있다. 옵션을 backend 표현으로 내린 뒤 `N < interval`과
`N + interval < effective TTL`을 검증해야 한다. Derived interval도 같은 단위로 내리되
caller object를 mutation하지 않는다.

### Exact client와 zero retry는 ownership 의미를 지킨다

분산 lock의 ambiguous command를 client가 몰래 retry하면 한 public call이 여러 lease를
만들 수 있다. 첫 구현은 fresh exact redis-py client, finite timeout, zero retry, no health
check/hook/custom callback을 요구한다. Response-lost acquire만 같은 owner token으로 한 번
reconcile하고 command를 재발행하지 않는다. 편의보다 검토 가능한 ownership trace가
우선이다.

### Process control도 cleanup 뒤에 동일 객체로 전파한다

`KeyboardInterrupt`, `SystemExit`, `GeneratorExit`, `CancelledError`를 일반 lifecycle
error로 감싸면 호출자가 중단 원인을 잃는다. 하지만 worker/thread/task가 시작된 뒤 즉시
전파하면 lease가 남는다. 먼저 bounded owned cleanup을 수행하고 동일한 control object를
다시 발생시켜야 한다. Cleanup failure는 원래 control identity를 바꾸지 않고 note나
sanitized secondary evidence로만 남긴다.

### Sync thread와 async task는 별도 state machine으로 검증한다

공통 abstraction으로 합치면 sync timeout worker나 detached async task 같은 숨은 실행
surface가 생기기 쉽다. Sync는 lease당 최대 한 non-daemon renewal thread를 소유하고
stop/join을 증명한다. Async는 event-loop task를 구조적으로 생성, cancel, await하고 exact
baseline 복귀를 증명한다. Public outcome만 맞는 테스트로는 leak와 cancellation race를
잡을 수 없다.

### 최소 ACL은 문서가 아니라 실제 거부 조건으로 증명한다

README allowlist가 좁아도 통합 test user에 `CLIENT SETINFO` 같은 추가 권한을 주면 최소
권한을 증명하지 못한다. 문서화한 key prefix와 command만 부여하고 unrelated command,
prefix 밖 key, `SCRIPT LOAD`가 계속 거부되는지 모든 protocol/auth/db/client-name shape에서
확인해야 한다. Handshake별 조건부 권한은 실제로 필요한 경우에만 추가한다.

### Counter 복구에는 downstream ordering authority가 필요하다

Redis fence counter만 backup해도 downstream high-watermark보다 작게 복구되면 stale writer가
다시 승인될 수 있다. 모든 writer를 멈추고 downstream watermark를 보존한 뒤 counter를
엄격히 큰 값으로 seed해야 한다. Signed integer 상한에 도달하면 reset이나 prefix 변경으로
복구할 수 없다. Downstream이 이해하는 새 epoch와 compound ordering으로 migration하거나
writer를 영구 중지해야 한다.

### Fence counter의 TTL 자체를 corruption으로 취급한다

Redis `INCR`는 기존 key의 TTL을 제거하지 않는다. 따라서 외부 운영 도구나 잘못된 복구
절차가 fence counter에 TTL을 붙이면 acquire가 더 큰 token을 한 번 발급한 뒤 counter가
만료되고, 다음 acquire가 1부터 다시 시작할 수 있다. 값의 형식과 상한만 검사해서는
fencing 불변조건을 지킬 수 없다. 기존 counter는 Lua acquire 안에서 `PTTL == -1`까지
원자적으로 확인하고, TTL이 있거나 상태가 불명확하면 lease를 만들지 않고 fail-closed해야
한다. Sync와 async adapter 모두 실제 Redis로 counter와 lease가 변경되지 않음을 증명한다.

### TLS 미지원은 배포 보안 조건이다

TLS를 거부하는 exact-client 정책은 단순한 호환성 제한이 아니다. TCP를 사용하면 Redis
자격 증명, owner token, capability 역할을 하는 lock material이 암호화되지 않는다. 공개
constructor 안내와 deployment checklist는 TCP를 호출자가 통제하는 보호 네트워크로
제한하고 가능한 경우 로컬 Unix socket을 우선하도록 같은 문구로 고정해야 한다.

### Manual lifecycle 예제도 failure precedence를 실행해야 한다

`renew()` 실패에서 `return False`를 쓰고 `finally: release()`를 두면 terminal/unknown
handle의 release 예외가 return을 덮는다. Compile-only README test는 이를 발견하지 못했다.
Terminal renewal outcome을 action/release block 전에 sanitized lifecycle error로 바꾸고,
문서 snippet의 실패 경로를 실제 fake handle로 실행해야 한다.

### 새 top-level test package는 workspace collection까지 확인한다

각 distribution test가 단독으로 통과해도 여러 `tests` package와 같은 basename helper가
workspace 전체 collection에서 충돌할 수 있다. Namespace-style test directory, package별
고유 module 이름, 고유 support helper 이름으로 구성하고 첫 전체 `pytest` collection을
Task 완료 조건에 포함해야 한다.

## 향후 가드

새 leader backend는 core에 backend dependency나 root implementation을 추가하지 않는다.
Adapter는 own repository/topology의 atomic acquire, owner proof, renewal, release, fencing,
uncertainty contract를 별도 spec과 real-backend integration으로 증명한다. Backend가 fencing을
제공하지 못하면 `LeaderLease`와 `FencedLeaderLease`를 혼동하지 않고 capability를 명시한다.

Redis 범위를 넓힐 때 Sentinel, Cluster, proxy, failover, TLS, hostname, retry 또는 다른
server major를 문서만으로 지원한다고 선언하지 않는다. 각 topology/client shape의 ownership
authority, ambiguity, timing, ACL, cancellation, counter restore를 새 evidence로 증명한다.

## 사전 검증 증거

- Core leader: `113 passed`.
- Redis adapter: `753 passed`.
- Real Redis Task 8 최종 gate: ACL `48` cases, sync/async Redis `73` cases,
  P0=0/P1=0/P2=0.
- 전체 workspace: `3246` collected, `3245 passed`, 기존 cache-redis benchmark Redis
  startup `1 failed`; 동일 test의 즉시 독립 rerun은 `1 passed`.
- Performance, stability, security, operator, developer/API, user/caller 여섯 review에서
  발견한 모든 P0/P1을 regression과 수정으로 닫았다. Exact-head verifier는 evidence
  commit 이후 변경 없는 SHA에서 수행한다.
