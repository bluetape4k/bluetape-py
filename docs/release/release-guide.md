# Release Guide

이 가이드는 `bluetape-py` Python package의 release flow를 정의합니다.

## 모델

`bluetape-py`는 여러 focused PyPI distribution을 포함하는 Python 3.13+ `uv` workspace입니다. consumer는 PyPI에서 package version을 선택하고, Git tag와 GitHub Release는 repository release state를 기록합니다.

Branch 역할:

- `develop`은 integration branch입니다.
- `main`은 release branch입니다.
- `develop`을 pull request로 승격한 뒤 `main`에서 release tag를 만듭니다.

Versioning:

- `v0.x.0`은 `v1.0.0` 전 milestone feature group에 사용합니다.
- `v0.x.y`는 patch fix와 release hygiene update에 사용합니다.
- `v0` version은 안정적인 public API compatibility를 보장하지 않습니다.

## Release 사전 조건

Release PR을 만들기 전에 다음을 확인합니다.

1. Milestone에 열린 issue가 없습니다.
2. `CHANGELOG.md`에 `## [vX.Y.Z] - YYYY-MM-DD`가 있습니다.
3. `WIP.md`가 대상 release-preparation 상태를 반영합니다.
4. `docs/release/release-guide.md`가 현재 release policy를 반영합니다.
5. 로컬 또는 remote에 `vX.Y.Z` tag가 없습니다.
6. `vX.Y.Z` GitHub Release가 없습니다.
7. 로컬 validation이 통과합니다.
8. 대상 `develop` commit의 GitHub CI가 통과합니다.
9. publish 전에 PyPI credential과 대상 repository를 repository 밖에서 확인합니다.
10. `docs/release/pypi-preflight.md`가 intended distribution을 열거하고 현재 trusted publishing hold 상태를 기록합니다.

유용한 preflight command:

```bash
git status --short --branch
git fetch --prune origin main develop --tags
git log --oneline origin/main..origin/develop
gh issue list --repo bluetape4k/bluetape-py --milestone "X.Y.Z" --state open
gh pr list --repo bluetape4k/bluetape-py --state open
git tag --list "vX.Y.Z"
git ls-remote --tags origin "refs/tags/vX.Y.Z*"
gh release view vX.Y.Z --repo bluetape4k/bluetape-py
rg -n "## \\[vX\\.Y\\.Z\\]" CHANGELOG.md
uv sync --all-packages
uv build --all-packages
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## 표준 Release flow

1. `develop`을 준비합니다.
   - `CHANGELOG.md`를 갱신합니다.
   - `WIP.md`를 갱신합니다.
   - process가 바뀌면 release docs를 갱신합니다.
   - 로컬 validation을 실행합니다.

2. Milestone bookkeeping을 닫습니다.
   - 열린 milestone issue 수가 0인지 확인합니다.
   - GitHub milestone을 닫습니다.

3. `develop`을 `main`으로 승격합니다.
   - base가 `main`, head가 `develop`인 release PR을 엽니다.
   - PR body에 release scope, validation evidence, milestone status, tag plan이 있는지 확인합니다.
   - PR CI가 통과할 때까지 기다립니다.
   - release PR을 merge합니다.

4. Release commit에 tag를 붙입니다.
   - `main`을 fetch합니다.
   - 로컬 `main`을 `origin/main`으로 fast-forward합니다.
   - `main`의 `CHANGELOG.md`에 version section이 있는지 확인합니다.
   - `main`에서 annotated tag를 만듭니다.

```bash
git switch main
git pull --ff-only origin main
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

5. GitHub Release를 만듭니다.
   - 일치하는 `CHANGELOG.md` section을 release note source로 사용합니다.
   - validation evidence와 tag target commit을 포함합니다.

6. Distribution을 publish합니다.
   - build artifact가 tagged commit에 해당하는지 확인합니다.
   - intended distribution만 publish합니다.
   - publication 후 PyPI에서 package metadata와 install behavior를 확인합니다.

## `v0.1.0` Release plan

`v0.1.0`은 다음 초기 Python-native foundation을 포함합니다.

- workspace structure와 Python 3.13+ policy;
- thin `bluetape` meta distribution;
- `bluetape-core`, `bluetape-logging`, `bluetape-testing`;
- English 및 Korean root documentation;
- package README와 release preflight documentation.

첫 release는 정확히 다음 distribution을 publish할 예정입니다.

- `bluetape`
- `bluetape-core`
- `bluetape-logging`
- `bluetape-testing`

PyPI project ownership과 trusted publishing을 repository 밖에서 확인할 때까지 publication은 hold입니다. issue #5가 열려 있는 동안 publish workflow를 dispatch하거나 artifact를 upload하지 않습니다.

완전한 fail-closed workspace classification은 `docs/release/pypi-preflight.md`에서 관리합니다. `bluetape-benchmark`는 build와 test를 수행하지만 private이므로 upload 대상으로 선택해서는 안 됩니다. private classifier는 defense in depth일 뿐이며, 분류되지 않은 workspace distribution이 하나라도 있으면 build artifact를 선택하기 전에 release preflight를 차단합니다.

Release 순서:

1. Milestone `0.1.0`에 열린 issue가 0개인지 확인합니다.
2. `CHANGELOG.md`, `WIP.md`, README locale file, 이 release guide가 `v0.1.0`을 반영하도록 release-readiness PR을 merge합니다.
3. Milestone `0.1.0`을 닫습니다.
4. Release PR로 `develop`을 `main`에 merge합니다.
5. `main`에 `v0.1.0` tag를 붙입니다.
6. GitHub Release `v0.1.0`을 만듭니다.
7. Release preflight issue #5가 닫힌 뒤에만 PyPI distribution을 publish합니다.
