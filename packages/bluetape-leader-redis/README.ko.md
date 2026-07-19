# bluetape-leader-redis

[English](README.md) | 한국어

`bluetape-leader-redis`는 `bluetape-leader`용 opt-in Redis adapter입니다. 하나의
authoritative writable Redis primary를 대상으로 제한된 sync/asyncio distributed
lock과 leader elector를 구현합니다. Runtime dependency는
`bluetape-leader==0.1.0`과 `redis==8.0.1`뿐입니다.

현재 PyPI 공개는 보류 중입니다. 설치 명령은 공개 이후의 형태를 설명합니다.

<!-- leader-scenario:constructor -->
## 설치와 정확한 borrowed client 구성

```bash
pip install bluetape-leader-redis
pip install "bluetape[leader-redis]"
```

Adapter는 아직 connection을 열지 않은 정확한 redis-py client만 받습니다.
`127.0.0.1` 같은 numeric IP, 유한한 양수 connect/command timeout, zero retry,
`health_check_interval=0`, 비어 있는 기본 `event_dispatcher`를 사용하십시오. TLS,
hostname, retrying client, health check, credential callback, connection hook,
custom response callback, proxy, subclass, 이미 사용한 pool은 I/O 전에 거부합니다.

<!-- sync-constructor-example -->
```python
import redis
from redis.backoff import NoBackoff
from redis.maint_notifications import MaintNotificationsConfig
from redis.retry import Retry

from bluetape.leader.redis import RedisDistributedLock

client = redis.Redis(
    host="127.0.0.1",
    port=6379,
    db=0,
    socket_connect_timeout=0.5,
    socket_timeout=0.5,
    health_check_interval=0,
    retry=Retry(NoBackoff(), 0),
    retry_on_error=[],
    maint_notifications_config=MaintNotificationsConfig(
        enabled=False,
        proactive_reconnect=False,
        relaxed_timeout=-1,
    ),
)
lock = RedisDistributedLock(client)
```

<!-- async-constructor-example -->
```python
import asyncio

import redis.asyncio as async_redis
from redis.backoff import NoBackoff
from redis.asyncio.retry import Retry as AsyncRetry

from bluetape.leader.redis import AsyncRedisDistributedLock


async def build():
    client = async_redis.Redis(
        host="127.0.0.1",
        port=6379,
        db=0,
        socket_connect_timeout=0.5,
        socket_timeout=0.5,
        health_check_interval=0,
        retry=AsyncRetry(NoBackoff(), 0),
        retry_on_error=[],
    )
    lock = AsyncRedisDistributedLock(client)
    return client, lock


client, lock = asyncio.run(build())
```

Local Unix socket은 redis-py의 `unix_socket_path` option으로 정확한 sync/async
`UnixDomainSocketConnection`을 구성하고, 동일한 유한 timeout, zero-retry, no-hook
규칙을 적용합니다. Host나 port를 함께 지정하면 안 됩니다.

네 constructor 모두 client를 빌려 씁니다.

`RedisDistributedLock(...)`

`AsyncRedisDistributedLock(...)`

`RedisLeaderElector(...)`

`AsyncRedisLeaderElector(...)`

이들은 client를 닫지 않습니다. 모든 lock/elector 작업이 terminal 상태가 된 다음
caller-owned sync/async scope에서 정확히 한 번 닫으십시오.

<!-- leader-scenario:fencing -->
## Fencing으로 stale write 차단

Lock은 Redis lease가 유효한 동안만 동시 소유를 막습니다. 멈췄던 predecessor가 만료
후 다시 실행될 수 있으므로 protected storage는 오래된 integer `fencing_token`을
atomic하게 거부해야 합니다.

```python
handle = lock.try_acquire("daily-job", options)
if handle is not None:
    with handle as held:
        update_if_newer(
            value,
            fencing_token=held.lease.fencing_token,
        )
```

`update_if_newer`는 incoming token을 비교하고 새 high-watermark와 business data를
한 transaction에서 함께 commit해야 합니다. 비교 후 따로 쓰는 방식은 그 사이에
다른 writer가 승리할 수 있으므로 지원하지 않습니다. Redis counter persistence는
단조 증가 발급의 전제이며, atomic downstream transaction이 stale write를 막는 최종
방어선입니다.

Owner mismatch나 expiry가 발생하면 renewal은 `NotHeld`를 반환하고 scoped
entry/exit는 lease loss를 보고합니다. `is_held()`는 여전히 TOCTOU 관찰이므로
downstream fencing을 대체할 수 없습니다.

<!-- leader-scenario:unsupported-topology -->
## 지원 topology와 명시적 제외 범위

Mutual exclusion은 하나의 authoritative writable single-primary에 대해서만
성립합니다. Asynchronous failover, partition, promotion, proxy 또는 multi-primary
routing, Sentinel, Cluster는 이 전제를 깨뜨릴 수 있습니다. 첫 구현 범위에는
Redlock, group/slot lock, strategic election, multi-resource transaction, 다른
backend가 없습니다. Clock 관찰값은 진단용일 뿐이며 lease는 Redis TTL과 atomic
script가 판단합니다.

Adapter는 결과가 불확실한 command를 재시도하지 않습니다. 응답을 잃은 acquire는
owner-token reconciliation을 한 번만 수행하고, 그 밖의 불확실한 lifecycle failure는
값이 제거된 error로 중단합니다. Application은 같은 logical lock을 서로 다른 writable
primary로 routing하면 안 됩니다.

## 최소 ACL

Coordination prefix key pattern과 문서화된 adapter command만 허용하십시오.
`EVALSHA`, `EVAL`, `GET`, script 내부 `TYPE`, `PTTL`, `INCR`, `SET`, `PEXPIRE`,
`DEL`이 전부이며 `SCRIPT LOAD`는 허용하지 않습니다. RESP negotiation, non-default
DB, authentication, client name을 쓰면 실제 handshake에서 확인한
`HELLO`/`AUTH`/`SELECT`/`CLIENT SETNAME` permission만 추가합니다. 관련 없는 command와
prefix 밖 key가 계속 거부되는지 검증하십시오.

<!-- leader-scenario:migration -->
## Coordination identity migration과 counter 복원

Prefix, SHA-256 logical-name digest derivation, `lease`/`fence` suffix set, record
version `v1`이 하나의 coordination identity를 이룹니다. Rolling migration은
contender를 갈라놓을 수 있으므로 다음 stop-the-world 순서를 지키십시오.

1. **기존 contender와 신규 contender를 모두 중지**하고 새 protected action을 막습니다.
2. 값을 삭제하거나 출력하지 않고 **기존 lease가 없음을 증명**합니다.
3. 모든 **downstream resource high-watermark**를 읽고 보존합니다.
4. authoritative Redis fence counter를 보존한 최대 watermark보다 **엄격히 큰 값**으로
   복원하거나 seed합니다.
5. 모든 contender에 하나의 **동일한 prefix**, digest derivation, suffix set, record
   version을 설정합니다.
6. 하나의 coordination identity에서 **모든 contender를 다시 시작**한 다음 protected
   work를 다시 허용합니다.

Fence counter는 protected data와 함께 backup하고 restore하십시오. Counter가 없거나
rollback되었거나 모든 보존 watermark보다 큰 값임을 증명할 수 없다면 writer를 계속
중지합니다. Active lease를 삭제하거나 downstream state를 낮춰 “복구”하면 안 됩니다.

## Lease-loss runbook

Renewal loss, owner mismatch, corruption, uncertain release가 발생하면 다음 순서로
처리합니다.

1. 해당 operation의 새 protected work를 차단합니다.
2. atomic downstream fencing이 stale write를 거부하거나 중단하게 둡니다.
3. caller-owned Redis health, ACL, pool, command, server evidence를 확인합니다.
4. lease가 terminal 상태임을 증명한 뒤에만 재개합니다.

이 runbook은 coordination key를 절대 삭제하지도 reset하지도 않으며 lease value를
절대 출력하지 않습니다. 값이 제거된 예외를 근거로 key scan이나 value dump를
수행하지 마십시오.

<!-- leader-scenario:rollback -->
## Rollback

Contender와 protected work를 중지하고 adapter 사용과 `leader-redis` extra를
제거하되 counter와 만료된 lease key를 그대로 둡니다. 이전 application이 동일한
coordination identity를 사용하고 보존된 downstream high-watermark보다 작은 token을
가진 writer를 다시 들여오지 않을 때만 복원합니다. 그렇지 않으면 protected work를
계속 중지하고 ordered migration 절차를 마친 뒤 재개하십시오.

<!-- leader-scenario:operator-actions -->
## 구조화된 operator action table

`LeaderBackendError`는 의도적으로 진단 정보를 담지 않으며 backend cause kind를
노출하지 않습니다. Operator는 exception에서 분기하거나 원인을 추측하지 말고
caller-owned evidence를 확인해야 합니다.

| 의심 상황 | Caller-owned evidence | 안전한 조치 |
|---|---|---|
| Connection 또는 pool timeout | Redis health, pool saturation, 설정한 finite timeout | 소유권이 불확실하면 protected work를 중지하고 capacity 또는 연결 문제를 해결 |
| Permission denial | ACL audit와 denied-command evidence | 정확한 ACL command/key allowlist를 비교하고 관련 없는 key 권한은 열지 않음 |
| Protocol failure | redis-py/RESP configuration과 server log | 정확한 supported client shape를 복구하고 retry나 hook을 켜지 않음 |
| Corrupt lease record | 값을 표현하지 않는 server-side integrity evidence | Writer를 중지하고 소유권을 조사하며 record를 삭제, reset, 출력하지 않음 |

정확한 caller-owned signal set은 acquire outcome/latency, renewal latency/loss,
release failure, pool timeout, command failure, reconnect입니다. 안전한 call-site
signal은 public operation과 outcome category만 label로 사용합니다. Lock name,
node/audit ID, owner token, Redis key/prefix, fencing token과 추측한 backend cause는
log field나 metric label로 사용하면 안 됩니다.

<!-- leader-scenario:deployment-checklist -->
## Deployment checklist

- [ ] `redis==8.0.1`을 pin하고 numeric IP 또는 Unix socket, 유한한 양수 timeout,
  zero retry로 새 exact sync/async client를 구성합니다. TLS, hostname, health check,
  callback, event hook, custom response callback을 사용하지 않습니다.
- [ ] 모든 contender를 하나의 writable standalone primary로 routing하고 Sentinel,
  Cluster, proxy, promotion, multi-primary routing을 거부합니다.
- [ ] 최소 ACL을 적용하고 prefix 밖 접근이 거부되는지 검증합니다.
- [ ] Fence counter를 protected data와 함께 보존, backup, restore합니다.
- [ ] 모든 protected store가 high-watermark와 business data를 atomic하게 비교하고
  commit하게 합니다.
- [ ] 유한한 deadline 아래에서 contention, cancellation, lease loss, release failure,
  caller-owned borrowed-client cleanup을 검증합니다.
- [ ] Counter, 만료 lease, downstream watermark를 보존한 채 동일한 coordination
  identity로만 rollback합니다.

Async cancellation은 제한된 owned cleanup을 수행한 뒤 `CancelledError`를 다시
발생시킵니다. 취소된 lock/elector call이 terminal 경계에 도달한 뒤에만 borrowed
async client를 닫으십시오.
