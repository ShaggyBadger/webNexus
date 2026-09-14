# Generic Charts

`genericcharts` generates public `CoreStarterPack` PDF packages from live
webNexus data.

## Structure

- `models.py` — generation history and published-document linkage.
- `version.py` — the generator/package version.
- `pipeline/dataclasses.py` — immutable selection, store, tank, curve, and chart contracts.
- `pipeline/selectors.py` — live ORM selection and mapped/virtual source normalization.
- `pipeline/grouping.py` — pure depth grouping, volume clustering, bucket statistics, and review flags.
- `pipeline/catalog.py` — canonical names, legacy aliases, and collision handling.
- `pipeline/coverage.py` — pure four-tier store/tank coverage mapping and review report.
- `pipeline/review.py` — typed graph layers for original curves, envelopes,
  statistics, analytic curves, and outlier review.
- `pipeline/scope.py` — canonical filename/DMS scope keys for each selection.
- `pipeline/package.py` — typed package assembly shared by review, PDF, and DMS.
- `pdf/` — prototype-faithful map, two-sided depth lookup tables, datasheet,
  section templates, footers, and document-wide page numbering.
- `services/` — generation orchestration, async jobs, and scoped DMS publication.
- `services/tank_estimate_sync.py` — detached admin launch for targeted or
  all-store Veeder geometry repair runs.
- `management/commands/generate_generic_chart_package.py` — worker entry point
  launched only by the authenticated admin workflow.
- `admin.py` and `templates/` — staff configuration, review, and status UI.
- `tests/` — focused tests for each boundary.

## Rules

- Keep ORM access in selectors and services; keep pipeline calculations pure.
- Pass dataclasses between pipeline stages. Do not add JSON as an internal transport layer.
- Keep selection criteria at the selector boundary. The initial selector supports
  state, `FULL`, StoreType selections, and store-number allowlists so future
  region filters do not leak into grouping or rendering.
- Store-type choices come from `tankgauge.StoreType`; the review form persists
  selected StoreType IDs and the selector matches those names against current
  `Store.store_type` text until the future foreign-key migration is completed.
- The admin state control is populated at form initialization from distinct,
  non-empty `Store.state` values, with `FULL - All states` always first.
- Persist `SelectionSpec.package_scope_key` on every generation. State aliases
  and allowlist ordering must resolve to the same key.
- Keep naming, metadata, footer, and page-numbering logic in dedicated modules.
- Render one final master PDF; do not retain intermediate chart PDFs.
- Preserve the printable contract from `~/pyProjects/extracttankdata/`: map rows
  use compact RUL, PREM, PLUS, DSL, and KERO fuel columns, generic charts use
  two-sided lookup tables, and the datasheet uses the landscape layout.
- Use `CoreStarterPack [ STATE ] version X.Y.Z`; use `FULL` for all states.
- Include selected StoreType names in the DMS title and description while using
  stable StoreType IDs in the package scope.
- Increment `PACKAGE_VERSION` only when generator behavior or PDF output changes.
  New source data and regeneration timestamps do not require a version bump.
- Publish the current DMS document as public `ACTIVE`; supersede older versions
  without deleting them automatically.
- Prefill an editable human-readable DMS description during review; retain
  detailed coverage data in the generation summary instead of the public
  document description.
- Keep the DMS category as `FNG` and apply normalized state, core-starter-pack,
  generic-tank-charts, store-tank-map, and selected `store-type-*` tags.
- Keep every user-facing workflow inside Django admin. Review, generation, and
  status access require staff authentication and the generation model's admin
  view permission; do not add public genericcharts URLs or APIs.
- Keep generation asynchronous and preserve the last valid public document if a
  new job fails.
- Only one package worker may run at a time. A pending job is atomically claimed
  before selection, rendering, or publication begins.
- Workers older than 30 minutes are marked failed so a crashed process cannot
  permanently block later admin generations. Worker output is written to
  `logs/generic_chart_generation.log`.
- Tank estimate repair runs are launched from the admin dashboard and retain
  their selected scope, mode, status, and command output in
  `TankEstimateSyncRun`.

## Maintenance

Before changing this app, read this file, the active plan in `instructions/`,
and `instructions/progress_state.json`. Add focused tests with behavior changes.
Update this README when structure, invariants, versioning, or maintenance rules
change. Never commit secrets, private data, database dumps, or generated
operational exports.
