# Issue #55 Redis Load Coordination 교훈

## 배경과 결정

이 기능은 독립된 process 사이의 cold load를 조정하지만 Redis를 L2 cache로 바꾸지는
않는다. local cache는 local hit와 in-process flight ownership의 authoritative source로
남고, Redis는 짧은 lease, 하나의 bounded atomic snapshot, owner-checked atomic
publication만 제공한다.

public contract는 `ResultEnvelopeCodec`를 통해 serialization을 caller-owned로
유지하고, digest-only Redis key를 사용하며, unbounded provider policy를 거부하고,
대응하는 sync/async surface를 제공한다. Lease loss가 발생하면 caller-loaded value를
local에서 반환하지만 distributed publication success를 주장하지 않는다.

## 구현으로 확인한 내용

- loop boundary에서만 확인하지 말고 각 backend command 직전에 wall deadline을 확인한다.
  token generation과 poll sleep도 deadline을 넘길 수 있는 작업이다.
- backoff 계산 자체가 overflow할 수 있으므로 poll count 제한만으로는 충분하지 않다.
  configured interval ratio로 exponent를 제한한다.
- socket timeout은 blocking connection-pool admission을 제한하지 않는다. acquisition
  wait가 command policy 범위를 벗어나는 pool은 거부한다.
- Async parity는 happy-path API만의 문제가 아니라 failure contract의 의무다. loader,
  codec, provider, artifact, cleanup, cancellation, invalid-input 경로에 직접적인
  증거가 필요하다.
- primary failure 또는 cancellation은 cleanup failure가 발생해도 보존해야 한다. 정적
  note와 low-cardinality `cleanup_failed` signal이 backend detail을 대체하거나 누출하는
  것보다 안전하다.
- ACL success proof는 coordinator가 실제로 요구하는 command만 사용해야 한다. teardown은
  앞선 cleanup 단계가 실패해도 provider close, user deletion, admin close를 모두 시도한다.

## 예상 밖의 문제와 향후 보호 장치

marker가 active인 동안 atomic snapshot이 bounded result prefix를 읽는 것은 필연적이다.
승인된 bounded contract에서는 허용되지만, production capacity claim을 하기 전에는
다시 검토해야 한다.

`CLEANUP_FAILURE`는 모든 안전한 cleanup이 기존 primary failure를 따르므로 자연스러운
standalone state가 없다. API를 안정화하기 전에 이를 reserved로 유지하거나
remove/deprecate한다. 오해를 부르는 cleanup-only failure path를 새로 만들지 않는다.

closeout ladder를 유지한다. focused unit 및 README test, serial real Redis, repeated
contention/cancellation, full pytest, Ruff, all-package build, actionlint, diff check,
six-perspective P0/P1 convergence, 이후 PR CI 순서로 실행한다. 모든 필수 check가
성공하기 전에는 merge를 허용하지 않는다.
