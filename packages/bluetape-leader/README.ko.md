# bluetape-leader

[English](README.md) | 한국어

`bluetape-leader`는 제한된 leader action과 distributed lock lease를 위한 표준
라이브러리 전용 backend-neutral 계약을 제공합니다. 실제 coordination은 backend
adapter가 담당합니다. Core package는 immutable option과 lease, 정밀한 result 값,
protocol, 값이 노출되지 않는 public error를 소유합니다.

현재 PyPI 공개는 보류 중입니다. 아래 명령은 공개 이후의 설치 형태입니다. 보류
기간에는 workspace build를 사용하십시오.

<!-- leader-scenario:install -->
## 설치

```bash
pip install bluetape-leader
pip install "bluetape[leader]"
```

두 방식 모두 표준 라이브러리만 사용하는 `bluetape.leader` 계약을 설치합니다.
Redis 지원은 별도 opt-in입니다. 기본 `bluetape` 설치는 계속 core-only입니다.

<!-- leader-scenario:contention -->
## 획득 결과를 확인한 뒤 context에 진입

`try_acquire()`
는 lease handle을 반환하며, 다른 contender가 lock을 소유하면 `None`을 반환합니다.
결과를 확인하기 전에 context에 진입하면 안 됩니다. 특히 다음 두 형태를 사용하지
마십시오.

`with lock.try_acquire(...)`

`async with await lock.try_acquire(...)`

```python
from datetime import timedelta

from bluetape.leader import LeaderElectionOptions

options = LeaderElectionOptions(
    wait_time=timedelta(0),
    lease_time=timedelta(seconds=30),
    node_id="worker-a",
    auto_renew=True,
)

handle = lock.try_acquire("daily-job", options)
if handle is not None:
    with handle as held:
        update_if_newer(
            value,
            fencing_token=held.lease.fencing_token,
        )
```

```python
async_handle = await async_lock.try_acquire("daily-job", options)
if async_handle is not None:
    async with async_handle as held:
        await update_if_newer_async(
            value,
            fencing_token=held.lease.fencing_token,
        )
```

`try_acquire()`
자체는 renewer를 시작하지 않습니다. `auto_renew=True`일 때도 context 진입 시
소유권을 다시 증명한 뒤에만 renewal을 시작합니다. 획득 후 context 진입까지의
지연은 최초 TTL만 보호합니다. 그러므로 바로 진입해야 하며, 진입에 실패하면 lease
loss로 처리해야 합니다.

<!-- leader-scenario:precise-result -->
## 정밀한 leader result 우선

`run_if_leader()`는 contention 때문에 action을 건너뛴 경우와 성공한 action이
`None`을 반환한 경우 모두 `None`을 반환합니다. `T`가 `None`일 수 있다면
`run_if_leader_result()`
를 사용하고 `Elected`, `Skipped`, `ActionFailed`를 빠짐없이 처리하십시오.

<!-- precise-result-example -->
```python
from bluetape.leader import ActionFailed, Elected, FencedLeaderLease, Skipped


def classify(result: object) -> str:
    if isinstance(result, Elected):
        return "elected:none" if result.value is None else "elected:value"
    if isinstance(result, Skipped):
        return "skipped"
    if isinstance(result, ActionFailed):
        return "action-failed"
    raise AssertionError("unreachable leader result")


sample_lease = FencedLeaderLease(
    audit_leader_id="example-run",
    node_id="worker-a",
    elected_at=None,
    lease_until=None,
    fencing_token=1,
)
sample_result = Elected(value=None, lease=sample_lease)
```

정밀한 result는 일반적인 caller action 예외를 `ActionFailed.cause`에만 보존합니다.
Package가 만드는 표현은 값을 노출하지 않습니다. Lease loss, release 불확실성,
backend failure는 일반 action result가 아니라 lifecycle 예외입니다.

<!-- leader-scenario:manual-lifecycle -->
## Manual lifecycle과 scoped lifecycle

일반적인 경우에는 context를 사용하십시오. Context는 진입 시 소유권을 확인하고,
필요하면 scope 안에서 renewal하며, 자신이 만든 작업을 제한 시간 안에 정리합니다.
Manual 방식은 명시적인 checkpoint가 필요하고 모든 release 경로를 caller가 책임질
때만 사용합니다.

| Lifecycle | Renewal | 소유권 checkpoint | Cleanup |
|---|---|---|---|
| Scoped context | 진입 증명 후 `auto_renew=True` 시작 | 되돌릴 수 없는 작업 전 `assert_held()` | context 종료 시 제한된 release 수행 |
| Manual handle | `renew()`를 직접 호출 | caller가 정한 경계에서 `assert_held()` 호출 | caller가 `finally`에서 release해야 함 |

<!-- manual-lifecycle-example -->
```python
from bluetape.leader import LeaderLeaseLostError, NotHeld, RenewBackendFailure


def run_manual(lock, options, value):
    handle = lock.try_acquire("daily-job", options)
    if handle is None:
        return False
    handle.assert_held()
    renewed = handle.renew()
    if isinstance(renewed, NotHeld):
        raise LeaderLeaseLostError()
    if isinstance(renewed, RenewBackendFailure):
        raise renewed.cause
    try:
        update_if_newer(value, fencing_token=handle.lease.fencing_token)
        return True
    finally:
        handle.release()


async def run_manual_async(lock, options, value):
    handle = await lock.try_acquire("daily-job", options)
    if handle is None:
        return False
    await handle.assert_held()
    renewed = await handle.renew()
    if isinstance(renewed, NotHeld):
        raise LeaderLeaseLostError()
    if isinstance(renewed, RenewBackendFailure):
        raise renewed.cause
    try:
        await update_if_newer_async(value, fencing_token=handle.lease.fencing_token)
        return True
    finally:
        await handle.release()
```

`NotHeld` 또는 `RenewBackendFailure` 뒤에는 `release()`를 호출하지 마십시오.
Handle은 이미 terminal 또는 uncertain 상태이며, 명시적 release는 renewal outcome을
lifecycle 예외로 바꿉니다. 예제는 action/release block에 들어가기 전에 해당하는
정제된 lifecycle error를 발생시킵니다.

`is_held()`는 관찰일 뿐 reservation이 아닙니다. Probe 직후 다른 process가 획득할 수
있으므로 check-then-write에는 TOCTOU race가 있습니다. `assert_held()`를 checkpoint로
사용하고, atomic downstream fencing transaction으로 stale write를 최종 차단하십시오.

<!-- leader-scenario:identity -->
## Identity field

| Field | 의미 | 안전성 역할 |
|---|---|---|
| `node_id` | `LeaderElectionOptions`에 전달하는 물리적 caller identity | 운영 상관관계 전용이며 소유권 capability가 아님 |
| `audit_leader_id` | 획득마다 생성되는 상관관계 text | Audit 상관관계 전용이며 exclusion 비교에 사용하지 않음 |
| integer `fencing_token` | fencing backend가 단조 증가 방식으로 발급한 capability | downstream stale-write rejection에 사용하는 유일한 identity field |

이 값들을 log나 외부 표면에 노출하면 안 됩니다. 여기서 “상관관계”는 의미를
설명할 뿐 package-generated message, log, metric label에 넣어도 된다는 뜻이
아닙니다.

<!-- leader-scenario:cancellation -->
## Async cancellation

Async lock과 elector 작업은 자신이 만든 cleanup task를 끝까지 추적합니다. Caller가
작업을 취소하면 adapter는 제한된 cleanup을 수행한 다음 `CancelledError`를 다시
발생시키며 background 작업을 떼어 놓지 않습니다. 빌려 준 backend client는 여전히
caller scope에서 caller가 닫아야 합니다.

```python
import asyncio


async def run_once(async_elector, options):
    try:
        return await async_elector.run_if_leader_result(
            "daily-job",
            perform_async_action,
            options,
        )
    except asyncio.CancelledError:
        raise
```

## Error와 privacy 경계

Public leader error에는 name, ID, key, prefix, client, owner record, backend
reply, fence 값이 포함되지 않습니다. `LeaderBackendError`는 의도적으로 진단 정보를
담지 않으며 backend cause kind를 노출하지 않습니다. `str`, `repr`, traceback,
note에서 원인을 추측하지 말고 caller가 소유한 backend health와 telemetry를 별도로
확인하십시오.

`LeaderExecutionError`는 일반 caller action과 lifecycle cleanup이 모두 실패했음을
뜻합니다. `action_cause`는 caller-owned `Exception`을 보존하고,
`lifecycle_cause`는 ownership safety failure를 나타내는 정제된 `LeaderError`입니다.
두 cause를 모두 처리하는 명시적 caller policy가 없다면 composite를 그대로 전파하십시오.
처리할 때는 안전한 exception type으로 두 attribute를 분류하고, 값이나 text를 log/parse하지
말며 lifecycle failure를 버리지 마십시오.
