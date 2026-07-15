# Issue #13 value package boundary diagram review

Date: 2026-07-15

Result: **PASS** (required checks 22/22, N/A 2, blocked 0)

## Scope ledger

- Reader question: Which concerns are owned by `bluetape-id`,
  `bluetape-measure`, and `bluetape-money`, and which inputs or policies remain
  caller-owned?
- Diagram kind: static architecture / package responsibility boundary map.
- Canonical assets:
  [SVG](../images/readme-diagrams/value-packages-boundary.svg) and
  [PNG](../images/readme-diagrams/value-packages-boundary.png).
- Exposure targets: root `README.md` and `README.ko.md`.
- Source authorities:
  `packages/bluetape-id/src/bluetape/id/__init__.py`,
  `packages/bluetape-measure/src/bluetape/measure/__init__.py`,
  `packages/bluetape-money/src/bluetape/money/__init__.py`, and
  `packages/bluetape-money/src/bluetape/money/_iso4217.py`.
- Packaging authorities: the root and meta-distribution `pyproject.toml` files.
- Loaded rules: `bluetape-diagram/SKILL.md`, `references/common.md`,
  `references/architecture.md`, `fireworks-tech-graph/SKILL.md`,
  `references/style-1-flat-icon.md`, and `references/icons.md`.
- Approved visual family:
  `docs/images/readme-diagrams/bluetape-observability-architecture.png`.
- Icon rule: N/A. These are Python value/API boundaries, not physical
  infrastructure or vendor services, so text-only cards avoid invented icons.

## Checklist and evidence

- [x] **DIA-01 — Pin scope and source model.** The reader question, canonical
  paths, exposure targets, and implementation/packaging authorities are listed
  above.
- [x] **DIA-02 — Load common and architecture rules.** The exact rule set and
  visual family are listed above. Sequence, ERD, class, and chart rules do not
  apply.
- [x] **DIA-03 — Create one authoritative SVG.** The `1300x800` SVG contains
  three package cards, six caller/source cards, and explicit responsibility
  and installation relationships.
- [x] **DIA-04 — Parse and render.** `xmllint --noout` passed; CairoSVG scale 2
  produced a `2600x1600` RGB PNG; a fresh temporary render was byte-identical.
- [x] **DIA-05 — Audit connectors.** Connector audit reported
  `markers=3 connectors=12 cards=9 intrusions=0 crossings=0`; geometry reported
  `geometry_failures=0`; endpoint passed; mixed-corner passed with
  `paths=12 q_bends=0 failures=0`.
- [x] **DIA-06 — Inspect the final full-size PNG.** Original-detail inspection
  after the final ASCII label repair found no tofu glyphs, clipping, card
  intrusion, crossings, inconsistent arrowheads, or unbalanced whitespace.
- [x] **DIA-07 — Verify exposure.** Both root README locales link the PNG and
  SVG and link both locale READMEs for all three packages. The assets resolve.
- [x] **DIA-08 — Preserve reproducible evidence.** Dimensions, hashes, audit
  counts, visual observations, and the validator fallback are recorded here.
- [x] **DIA-COM-01 — Keep text readable and source-backed.** Architects
  Daughter headings and Comic Mono details match the approved family; package
  and caller responsibilities map to public APIs and package boundaries.
- [x] **DIA-COM-02 — Use fixed markers.** Three `14x14`,
  `markerUnits=userSpaceOnUse` definitions bind exactly to the referenced
  install/source/caller marker roles.
- [x] **DIA-COM-03 — Keep routes clear.** Automated audits found zero card
  intrusions, crossings, diagonal failures, endpoint failures, or mixed corner
  failures.
- [x] **DIA-COM-04 — Verify architecture semantics.** The asset communicates
  ownership and dependency boundaries; it does not imply runtime chronology.
- [x] **DIA-COM-05 — Keep peer geometry consistent.** Three equal package
  cards and six aligned lower cards preserve a common grid and balanced
  margins.
- [x] **DIA-COM-06 — Verify bent corners.** N/A: the connector paths are
  straight horizontal or vertical segments and report `q_bends=0`.
- [x] **DIA-COM-07 — Use verified infrastructure icons.** N/A for the
  source-backed text-only package/API model.
- [x] **DIA-COM-08 — Run local commands.** XML, deterministic render,
  connector, geometry, endpoint, mixed-corner, marker fallback, README tests,
  and diff hygiene all passed.
- [x] **DIA-ARC-01 — Choose layout from the question.** The three-column
  package layout keeps package ownership distinct while aligning each source
  and caller responsibility below its owner.
- [x] **DIA-ARC-02 — Preserve install semantics.** The meta-distribution is
  shown as an opt-in installer, not as a runtime owner or root import surface.
- [x] **DIA-ARC-03 — Preserve caller ownership.** Entropy/clock, registry and
  conversion policy, and exchange-rate/rounding inputs remain outside package
  ownership.
- [x] **DIA-ARC-04 — Verify review exposure.** This review links the same
  canonical pair exposed by both root README locales.

## Validator fallback

`fireworks-tech-graph/scripts/validate-svg.sh` passed XML, tag balance,
attributes, entities, collisions, closing tag, and render checks, but reported
`Missing marker: arrow-install`. Its marker extraction deletes every character
in the shell character set `id="`, which changes `arrow-install` before the
comparison. An ElementTree fallback found marker IDs and references both equal
to `arrow-caller`, `arrow-install`, and `arrow-source`, with `missing=[]`,
`cards=9`, and `packages=3`. The dedicated Bluetape connector audit also passed
all three marker definitions, so this is a validator false positive rather than
an asset defect.

## Asset hashes

- SVG SHA-256:
  `85fea63f6d3fd78b2bc9261365e9762a95dd5a8daa35a458cda26b55a2b42cf8`
- PNG SHA-256:
  `cb32923b6ef512bf06636e9e1554081658576a3890372f03c29409c9ccb33b4d`

`uv run pytest packages/bluetape/tests/test_value_readmes.py -q` reported
`2 passed`; Ruff and `git diff --check` also passed.
