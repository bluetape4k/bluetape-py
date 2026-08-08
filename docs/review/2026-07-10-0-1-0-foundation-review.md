# 0.1.0 기반 검토

## 범위

- 브랜치: `feat/0.1.0-foundation-closure`
- 기준: `origin/develop`
- 이슈: #1, #2, #3, #5
- 적용 지침: `bluetape4k-workflow`, `bluetape-py-patterns`,
  테스트 주도 개발, worktree 격리

## 발견 사항

- P0: 0
- P1: 0

새 `bluetape-core` helper는 validation package의 범위를 좁게 유지한다.
`require_instance`는 성공하면 타입이 지정된 값을 반환하고, 타입 계약을
위반하면 `TypeError`를 발생시킨다. presence, blank-string, empty-sized 값에
대한 기존 `ValueError` 계약은 변경하지 않았다.

`bluetape-logging`은 runtime에서 계속 stdlib만 사용한다. context merge 동작은
기본적으로 opt-out에 안전하며, `override=False`를 사용하면 호출자가 scoped
logging context의 중복 key를 차단할 수 있다. Redaction은 이제 기본적으로
대소문자를 구분하지 않는 key matching을 사용하므로, 원래 mapping을 변경하지
않고 일반적인 HTTP header capitalization을 처리한다.

`bluetape-testing`은 internal-first 원칙을 유지하고 runtime dependency로
`pytest`만 사용한다. `eventually`와 `eventually_async`는 이제 `0` 같은
falsy non-`None` 값을 성공한 probe result로 처리하며, `None`과 `False`는
여전히 미충족으로 처리한다. 0 이하의 timeout과 interval 입력은
`ValueError`로 즉시 실패한다.

Release readiness는 의도적으로 아직 pre-publish 상태다. CI는 모든 workspace
distribution을 빌드하며, `docs/release/pypi-preflight.md`에는 대상
distribution set과 trusted-publishing hold가 기록되어 있다.

## 검증

- `uv sync --all-packages`: 통과
- `uv run pytest`: 통과, 21 tests
- `uv run ruff check .`: 통과
- `uv run ruff format --check .`: 통과
- `uv build --all-packages`: 통과, 8 artifacts
- Import 및 metadata smoke: 통과
- `actionlint`: 통과
- `rg -n "\\'" .github/workflows || true`: 통과, 일치 항목 없음
- `git diff --check`: 통과

## 잔여 위험

PyPI trusted-publishing 설정은 문서화했지만 이 브랜치에서는 수행하지 않았다.
Repository ownership과 PyPI project configuration을 소스 트리 외부에서
확인할 때까지 publishing은 차단된다.
