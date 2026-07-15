# Issue #24 observability architecture diagram review

## Scope ledger

- Reader question: Which responsibilities belong to Bluetape domain producers,
  `bluetape-observability`, and the application-owned OpenTelemetry runtime?
- Diagram kind: static architecture / responsibility and ownership map.
- Canonical SVG:
  `docs/images/readme-diagrams/bluetape-observability-architecture.svg`
- Canonical PNG:
  `docs/images/readme-diagrams/bluetape-observability-architecture.png`
- Exposure targets:
  `packages/bluetape-observability/README.md` and
  `packages/bluetape-observability/README.ko.md`.
- Implementing source:
  `packages/bluetape-observability/src/bluetape/observability/_recording.py`,
  `resilience.py`, and `redis.py`.
- Related-set scan: the repository has a workspace overview and resilience
  diagrams, but no issue #24 or observability-specific SVG/PNG asset.
- Approved visual family:
  `docs/images/readme-diagrams/bluetape-py-workspace-overview.png`.
- Loaded rules:
  `bluetape-diagram/SKILL.md`, `references/common.md`,
  `references/architecture.md`,
  `bluetape-workflow/references/checklist-contract.md`, and
  `fireworks-tech-graph/references/style-1-flat-icon.md`.
- Icon rule: N/A. The cards are Python/API responsibility boundaries rather
  than physical infrastructure or vendor services, so source-backed text-only
  cards avoid invented logos.

## Source-backed model

- `PolicyEvent`, `RedisEvent`, and `RedisCoordinationEvent` enter three public
  adapters.
- The bridge accepts only closed enum values, bounded integers, finite
  non-negative durations, and exact booleans.
- The bridge adds fixed events to the caller's current recording span and
  records fixed counters/histograms through a constructor-cached `Meter`.
- Policy names, Redis keys/values/namespaces, exception messages, arbitrary
  attributes, log context, baggage, and trace identifiers are not promoted.
- Providers, exporters, context propagation, flush, and shutdown remain
  application-owned.

## Instantiated checklist

- [x] **CL-01 — Create before mutation**
  - **Evidence:** this ledger was created before the SVG, PNG, or README was
    changed.
- [x] **CL-02 — Classify every item**
  - **Evidence:** DIA-01..08 and DIA-ARC-01..04 are required;
    DIA-COM-01, 02, 04, 05, 07, 08, and 09 are required. Infrastructure icon
    sourcing, bent-corner repair, and irreversible-action refresh are N/A with
    the text-only, straight-connector, and local-only scope evidence below.
- [x] **CL-03 — Respect dependency order**
  - **Evidence:** ledger creation preceded SVG edit; final SVG preceded PNG
    render; render and audits preceded README exposure; exposure preceded
    targeted tests and final diff validation.
- [x] **CL-04 — Record evidence immediately**
  - **Evidence:** render dimensions, hashes, audit counts, visual observations,
    README lines, and test result are recorded below after their commands were
    read.
- [x] **CL-05 — Fail closed**
  - **Evidence:** the first broad package test stopped at `3 failed, 60 passed,
    3 errors`; no completion claim was made before diagnosing the missing
    optional SDK.
- [x] **CL-06 — Repair skipped or reordered work**
  - **Evidence:** `.github/workflows/ci.yml` proved the default package command
    excludes `observability_sdk` and `observability_workspace`; the exact
    CI-shaped rerun passed `57 passed, 9 deselected`.
- [x] **CL-07 — Refresh irreversible holds**
  - **Evidence:** N/A. This task creates local branch assets only; it does not
    push, create a PR, merge, delete a branch, publish, or dispatch a workflow.
- [x] **CL-08 — Count before completion**
  - **Evidence:** Required checks: 26/26; N/A: 3; Blocked: 0.

- [x] **DIA-01 — Pin asset scope and source model**
  - **Evidence:** canonical paths, exposure targets, source files, reader
    question, related-set scan, and architecture kind are recorded above.
- [x] **DIA-02 — Load common and kind rules**
  - **Evidence:** exact rule list is recorded above; no sequence, class, ERD,
    or chart reference applies.
- [x] **DIA-03 — Complete one SVG edit**
  - **Evidence:** one canonical 1600x920 SVG was created. It contains three
    responsibility lanes, ten cards, eight straight orthogonal connectors,
    one primary marker role, and one ownership footer.
- [x] **DIA-04 — Parse and render the authoritative PNG**
  - **Evidence:** `xmllint --noout` passed; `cairosvg ... -s 2` produced a
    deterministic 3200x1840 PNG. Re-rendering to `/tmp` and `cmp` passed.
- [x] **DIA-05 — Run common and type-specific audits**
  - **Evidence:** connector audit reported `markers=1 connectors=8 cards=10
    intrusions=0 crossings=0`; geometry reported `geometry_failures=0`;
    endpoint and mixed-corner audits passed with `paths=8 q_bends=0
    failures=0`.
- [x] **DIA-06 — Inspect the full-size PNG**
  - **Evidence:** the final 3200x1840 PNG was opened after the last coordinate
    change. High-detail inspection found no clipped/crowded text, inconsistent
    peer alignment, wrong-direction heads, hard corners, crossings, card
    intrusion, or excess lane whitespace. A full-size JPEG conversion was also
    inspected to rule out an original-detail viewer artifact.
- [x] **DIA-07 — Verify exposure and diff hygiene**
  - **Evidence:** both README locales embed the PNG at line 12 and link the SVG
    at line 14; both resolved assets exist; `git diff --check` passed.
- [x] **DIA-08 — Render the evidence ledger**
  - **Evidence:** every required row has a command, count, path, or observed
    result below; Required checks: 26/26; N/A: 3; Blocked: 0.

- [x] **DIA-COM-01 — Verify source and related-set scope**
  - **Evidence:** both README locales and all three implementing modules were
    read; the related-set scan found no observability asset.
- [x] **DIA-COM-02 — Preserve readable text and theme**
  - **Evidence:** the final PNG uses Architects Daughter headings and Comic
    Mono details with the approved light canvas and rounded-card family;
    adapter titles were split after the first visual inspection to restore
    comfortable card padding.
- [x] **DIA-COM-03 — Use verified infrastructure icons**
  - **Evidence:** N/A for text-only API/component cards; no technology logo or
    infrastructure pictogram will be introduced.
- [x] **DIA-COM-04 — Verify markers in PNG**
  - **Evidence:** one fixed `markerUnits=userSpaceOnUse` primary marker is
    14x14; marker audit reported `markers=1`, and all eight visible arrowheads
    have the same solid slate color, size, and direction in the PNG.
- [x] **DIA-COM-05 — Verify connector endpoints and routes**
  - **Evidence:** endpoint audit passed; connector and geometry audits reported
    `connectors=8 intrusions=0 crossings=0 geometry_failures=0`. All routes
    enter left/right card edges perpendicularly and stay clear of corners.
- [x] **DIA-COM-06 — Verify every bent corner**
  - **Evidence:** N/A with targeted fallback: XPath reported
    `connectors=8 bent_connectors=0`; every connector is a single horizontal
    `M ... H ...` path, so no turn exists to round.
- [x] **DIA-COM-07 — Synchronize lanes, canvas, and whitespace**
  - **Evidence:** XPath reported `lanes=3 cards=10`. Canvas side margins are
    52px each, the lane bottom is y=766, content ends at y=730, and the 36px
    content gap remains balanced before the footer at y=808.
- [x] **DIA-COM-08 — Run required local commands**
  - **Evidence:** XML, CairoSVG scale 2, deterministic `cmp`, connector,
    geometry, endpoint, mixed-corner, XPath fallback, and `git diff --check`
    commands all passed with the concrete counts in this ledger.
- [x] **DIA-COM-09 — Verify review exposure**
  - **Evidence:** both README locales point to the canonical pair, and this
    review page links the same [PNG](../images/readme-diagrams/bluetape-observability-architecture.png)
    and [SVG](../images/readme-diagrams/bluetape-observability-architecture.svg).

- [x] **DIA-ARC-01 — Confirm static architecture semantics**
  - **Evidence:** the asset answers a responsibility and ownership question;
    it does not model ordered calls, retries, or lifecycle timing.
- [x] **DIA-ARC-02 — Match an approved visual family**
  - **Evidence:** the repo-local workspace overview PNG was opened at original
    size; the new asset will preserve its light canvas, rounded cards,
    Architects Daughter headings, Comic Mono details, and restrained palette.
- [x] **DIA-ARC-03 — Choose layout from the reader question**
  - **Evidence:** a horizontal input / bridge / caller-owned runtime map keeps
    three responsibility boundaries visible without connector doglegs.
- [x] **DIA-ARC-04 — Verify architectural connectors**
  - **Evidence:** eight straight responsibility links connect concrete cards or
    the bounded core boundary; automated audits found zero crossings,
    intrusions, endpoint failures, diagonal segments, or geometry failures,
    and the PNG shows clear standoff from lane titles and card text.

## Evidence ledger

| Gate | Evidence |
|---|---|
| Scope | Canonical SVG+PNG pair exists; related-set scan found exactly 2 observability assets |
| Source | README locales plus `_recording.py`, `resilience.py`, and `redis.py` |
| XML | `xmllint --noout` passed |
| Render | CairoSVG scale 2; 3200x1840; deterministic re-render `cmp` passed |
| Kind rules | `common.md` and `architecture.md` loaded |
| Connector audits | `markers=1 connectors=8 cards=10 intrusions=0 crossings=0`; all failures=0 |
| Type-specific audit | 3 lanes, 10 cards, 8 straight links, 0 bent/diagonal paths; ownership boundaries preserved |
| Visual inspection | Final 3200x1840 PNG: clipping=0, crowding=0, crossings=0, inconsistent heads=0 |
| Review exposure | Both README locales: PNG line 12, SVG line 14; review links resolve |
| Diff hygiene | `git diff --check` passed; focused test `57 passed, 9 deselected` |

## Asset hashes

- SVG SHA-256:
  `747c7fbccf5eb989434c7de923b1410b658b2cce8ef365657bbd2cacdc32ab57`
- PNG SHA-256:
  `5e891e3aeac5a05bfcae2fc6bb27a1dfcfa7d333cbfbbdeb03d3ab112049b168`
