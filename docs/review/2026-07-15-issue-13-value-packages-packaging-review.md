# Issue #13 Value Packages Packaging 검토

날짜: 2026-07-15

## 확인된 통합

- `bluetape-id`, `bluetape-measure`, `bluetape-money`를 각각 publishable
  workspace distribution으로 분류했다.
- Historical `v0.1.0` target table은 기존 네 distribution으로 제한하며
  세 value package는 release target이 아니다.
- `scripts/verify-value-wheels.sh`가 모든 workspace distribution에 대해 wheel
  하나씩을 build하고 focused install, `id`, `measure`, `money`, `values`,
  `dev`, `all`, default meta environment를 검증한다.
- External dependency는 hash가 있는 `uv export --locked --no-emit-local`에서
  준비한다. Workspace wheel은 `UV_OFFLINE=1`, `--offline`, `--no-index`,
  `--no-deps`로 전환한 뒤에만 설치한다.
- 모든 environment가 `uv pip check`와 checkout 밖 `python -I` module-origin
  probe를 통과한다. Default meta environment는 `bluetape.core`만 노출하고
  세 value module은 노출하지 않는다.
- Focused wheel metadata에 runtime dependency가 없고 focused wheel 어디에도
  `bluetape/__init__.py`가 없다.

## Workflow registration 검토

Repository에는 `.github/workflows/ci.yml`과
`.github/workflows/fory-conformance.yml`만 있다. Generic CI는 path filter가
없고 workspace Ruff, pytest discovery, `uv build --all-packages`를 이미 실행한다.
Workflow file은 변경하지 않았다.

- Dedicated value-package workflow: N/A. Stdlib/data-only package이며 generic
  discovery가 test와 build를 실행한다.
- Nightly registration: N/A. Nightly workflow나 이 package가 소유하는 external
  service, container, clock, provider matrix가 없다.
- Example registration: 이 task에서는 N/A. Installed-wheel README example은
  documentation task에서 추가하고 검증한다.
- Coverage aggregation: N/A. Repository에 coverage aggregation workflow가 없다.
- `actionlint`: Workflow file을 변경하지 않아 이 task에서는 N/A.

## 중복 결정

Value-wheel verifier는 `verify-observability-wheels.sh`와 domain-specific probe를
분리한다. 두 script는 generic shell setup, wheel count, isolated import concept만
공유한다. Observability verifier는 OpenTelemetry API/SDK와 Redis observer를
소유하고, value verifier는 three-way focused/meta-extra/default absence matrix,
lock hash, 모든 workspace wheel hash, stdlib-only focused metadata를 소유한다.
안정된 shared contract 없이 common framework를 추출하면 새 abstraction이 되므로
추출하지 않았다.
