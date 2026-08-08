# PR #6 Python Pattern 검토

## 범위

- PR: <https://github.com/bluetape4k/bluetape-py/pull/6>
- 기준: `develop` at `0f331dc`
- Head: 현재 PR head의 `docs/readme-ecosystem-overview`
- 적용 지침: `bluetape4k-workflow` 및 `bluetape-py-patterns`

## 발견 사항

- P0: 0
- P1: 0

README package boundary는 Python-native distribution 계약과 일치한다.
`bluetape`는 thin meta distribution으로 남고, default install은
`bluetape-core`만 dependency로 가지며, `packages/bluetape/pyproject.toml`은
`packages = []`를 유지해 root distribution이 root `bluetape/__init__.py`
import surface를 만들지 않는다.

README usage snippet은 기존 public import path를 사용한다:
`bluetape.core.require_not_blank`, `bluetape.logging.ContextLogFilter`,
`bluetape.logging.log_context`, `bluetape.testing.eventually`.

계획된 package는 planned 상태로 명확히 표시되어 현재 installable import
surface로 제시하지 않는다. Install section은 첫 PyPI release 이후에 public
`pip install` shape가 적용된다고도 명시한다.

README hero는 sibling bluetape ecosystem README hero와 유사한 generated
bitmap identity visual을 사용한다. Package relationship diagram은 hero와
중복하지 않고 별도의 workspace overview asset으로 유지한다.

Ecosystem backlog는 milestone `0.2.0`에서 issue #7-#34로 추적한다.
Research-first issue #10, #14, #16, #21, #23, #31, #34는 구현 전에 source-backed
평가가 필요한 Python package boundary와 dependency 선택을 다룬다.

Project-management document shape는 `bluetape-go`를 따른다. 상세한 planning과
task queue는 `WIP.md`, 완료된 user-facing 변경은 `CHANGELOG.md`, release policy는
`docs/release*`, package boundary rule은 `docs/package-layout.md`, research gate는
`docs/research/`에 둔다.

## 검증

- `git diff --check`: 통과
- `rg -n "WIP.md|CHANGELOG.md|docs/release|docs/research|docs/package-layout.md" README.md README.ko.md`: 통과
- `uv sync --all-packages`: 통과
- `uv build --all-packages`: 통과
- `uv run pytest`: 통과, 11 tests
- `uv run ruff check .`: 통과
- `uv run ruff format --check .`: 통과
- `xmllint --noout docs/images/readme-diagrams/bluetape-py-workspace-overview.svg`: 통과
- `/Users/debop/.local/bin/cairosvg docs/images/readme-diagrams/bluetape-py-workspace-overview.svg -o docs/images/readme-diagrams/bluetape-py-workspace-overview.png -s 2`: 통과
- README hero 및 workspace overview PNG asset의 `file`/`sips` dimension check: 통과
- `actionlint`: 통과

## 참고

최종 render 근거로 Python-package `cairosvg` import를 사용하지 않았다. 로컬
Python이 system cairo library를 로드하지 못했기 때문이다. 설치된 CairoSVG
CLI `/Users/debop/.local/bin/cairosvg`는 workspace overview PNG를 hero 이동 후
성공적으로 render했다.
