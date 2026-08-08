# Release Guide

상세 release 절차: [`docs/release/release-guide.md`](release/release-guide.md)
PyPI package preflight: [`docs/release/pypi-preflight.md`](release/pypi-preflight.md)

## Branch

- `develop`은 default integration branch입니다.
- `main`은 release 전용이며 pull request로 `develop`에서 갱신해야 합니다.

## Versioning

첫 tag를 publish한 뒤 semantic versioning을 사용합니다.

- `v0.1.0`: 첫 foundation release.
- `v0.x.0`: 새 package family 또는 의미 있는 feature group.
- `v0.x.y`: bug fix, docs, compatibility 조정, 작은 non-breaking 개선.

`v1.0.0` 전에는 public API가 바뀔 수 있습니다. Breaking change는 `CHANGELOG.md`에 기록합니다.

## Release tag 기준

- `README.md`와 `README.ko.md`가 release scope에 맞게 최신입니다.
- publish하는 모든 distribution의 package README가 최신입니다.
- `CHANGELOG.md`에 대상 `vX.Y.Z` section으로 전환할 수 있는 `Unreleased` section이 있습니다.
- `WIP.md`가 대상 release-preparation 상태를 기록합니다.
- 일치하는 milestone이 열린 issue 0개로 닫혀 있습니다.
- 로컬에서 `uv sync --all-packages`가 통과합니다.
- 로컬에서 `uv build --all-packages`가 통과합니다.
- 로컬에서 `uv run pytest`가 통과합니다.
- 로컬에서 `uv run ruff check .`가 통과합니다.
- 로컬에서 `uv run ruff format --check .`가 통과합니다.
- `uv build --all-packages` distribution build를 포함한 GitHub Actions CI가 `develop`에서 통과합니다.
- publish action 전에 PyPI credential 또는 trusted publishing을 명시적으로 확인합니다.
- Release selection이 `docs/release/pypi-preflight.md`의 정확한 allowlist로 모든 workspace distribution을 분류합니다. 알 수 없는 workspace member는 preflight를 차단하며 `bluetape-benchmark`는 private이므로 절대로 upload하지 않습니다.

## Changelog 규칙

`CHANGELOG.md`는 Keep a Changelog 형식을 유지합니다.

- `Added`
- `Changed`
- `Deprecated`
- `Removed`
- `Fixed`
- `Security`

Tag를 만들 때 `Unreleased` entry를 version section으로 옮깁니다.

## Tag 절차

1. `develop`이 green인지 확인합니다.
2. `CHANGELOG.md`를 갱신합니다.
3. `WIP.md`를 갱신합니다.
4. `develop`을 base로 `main`을 향하는 release PR을 열고 merge합니다.
5. `main`에 tag를 붙입니다.
6. tag를 push합니다.
7. `CHANGELOG.md`로 GitHub release note를 만듭니다.
8. 검증된 release commit에서만 PyPI artifact를 publish합니다.
