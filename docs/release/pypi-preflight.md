# PyPI 사전 점검

이 문서는 첫 `bluetape-py` release의 publication 경계를 기록합니다. publication 권한이 아니라 preflight checklist입니다.

## 대상 release

- Version: `v0.1.0`
- Release PR 전 source branch: `develop`
- Release branch: `main`
- Tag: `v0.1.0`

## 대상 distribution

| Distribution | Import path | Default `bluetape` dependency | `v0.1.0`에 publish |
|---|---|---:|---:|
| `bluetape` | none | yes | yes |
| `bluetape-core` | `bluetape.core` | yes | yes |
| `bluetape-logging` | `bluetape.logging` | no | yes |
| `bluetape-testing` | `bluetape.testing` | no | yes |

`bluetape` meta distribution의 default dependency list는 `bluetape-core`로 제한해야 합니다.

## Fail-closed workspace 분류

현재 workspace의 모든 distribution을 아래 두 집합 중 하나로 분류합니다. workspace member가 어느 집합에도 없으면 release tooling과 review가 실패해야 합니다.

명시적인 release 승인과 대상 release 표의 적용을 전제로 publish할 수 있는 distribution:

- `bluetape`
- `bluetape-async`
- `bluetape-audit`
- `bluetape-cache`
- `bluetape-cache-redis`
- `bluetape-codec`
- `bluetape-collections`
- `bluetape-compression`
- `bluetape-core`
- `bluetape-id`
- `bluetape-jwt`
- `bluetape-leader`
- `bluetape-leader-redis`
- `bluetape-logging`
- `bluetape-measure`
- `bluetape-money`
- `bluetape-observability`
- `bluetape-resilience`
- `bluetape-serde`
- `bluetape-testcontainers`
- `bluetape-testing`

절대로 publish하지 않는 private distribution:

- `bluetape-benchmark`

`bluetape-benchmark`의 classifier는 PyPI 방어를 위한 보조 장치입니다. 정확한 release selection이 주 통제 수단이므로 알 수 없는 member가 있으면 preflight가 차단되며, publish command는 publishable set에서 명시적으로 승인한 subset만 사용해야 합니다.

## Trusted publishing 상태

상태: hold.

publish 전에 repository 밖에서 다음을 확인합니다.

1. 모든 대상 distribution의 PyPI project ownership.
2. 각 project에 GitHub Actions trusted publishing이 설정되어 있는지 여부.
3. publish를 허용하는 GitHub environment가 있는 경우 그 이름.
4. PyPI 전에 TestPyPI dry-run publication이 필요한지 여부.

release owner가 publish 단계를 명시적으로 승인하기 전에는 tag, GitHub Release, workflow dispatch 또는 `uv publish` command를 실행하지 않습니다.

## 로컬 검증

release candidate commit에서 다음 명령을 실행합니다.

```bash
uv sync --all-packages
uv build --all-packages
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

release tag를 만들기 전 CI도 `uv build --all-packages`를 실행해야 합니다.
