# TankGauge Mathematical Mode Fix Plan

## Objective

Align implementation with `temp_thoughts.md` mandates, eliminate mode-routing defects, and make Mathematical Mode operationally safe for production rollout.

## Scope

- `tankgauge/logic`
- `tankgauge/views`
- `tankgauge/templates`
- `tankgauge/models`
- Targeted tests for mode, estimation, and API behavior

## Non-Goals

- Full UI redesign
- Broad refactors outside the tank mode pipeline
- Historical data backfill beyond estimation persistence requirements

---

## Phase 0: Baseline and Guardrails

### Tasks

- Capture current behavior before edits:
  - `python manage.py test tankgauge`
  - Add temporary logging snapshots for mode decisions and source metadata in calculation path.
- Define success criteria upfront:
  - No successful path returns zeroed gallons unless input is truly zero.
  - Mode labels and mode execution are consistent for official, mapped-estimated, and virtual-estimated paths.
  - Confidence gates match mission thresholds.

### Deliverable

- A short "before" behavior matrix (`mode input -> expected output`) to compare against post-fix behavior.

---

## Phase 1: Mode Contract Unification (Highest Priority)

### Problem

`MODE_EXPERIMENTAL` is returned, but calculation functions currently execute geometry logic only for `MODE_MATHEMATICAL`.

### Files

- `tankgauge/logic/calculations.py`
- `tankgauge/templates/tankgauge/components/tank_card.html`

### Tasks

- Choose one contract:
  1. Preferred: use a single non-chart mode (`MATHEMATICAL`) for both persisted and virtual estimates.
  2. Alternate: keep both labels but ensure both execute identical geometry logic end-to-end.
- Update mode branching in:
  - `get_volume_from_depth(...)`
  - `get_depth_from_volume(...)`
- Align UI mode badges so every backend mode is represented correctly.

### Acceptance Criteria

- Persisted estimation path produces non-zero volume/depth outputs.
- UI mode indicator matches backend execution mode.
- No dead mode constants or unreachable branches remain.

---

## Phase 2: Confidence Gate Enforcement

### Problem

Current thresholds are permissive and do not match mission specification.

### File

- `tankgauge/logic/estimation_service.py`

### Tasks

- Set threshold constants to mission values:
  - `MIN_READINGS = 3`
  - `MIN_HEIGHT_SPREAD = 5.0`
- Add an explicit minimum confidence threshold check after geometry engine execution.
- Add structured logs for gate failures (gate name, measured value, required value).

### Acceptance Criteria

- Below-threshold tanks resolve to non-estimated/`UNAVAILABLE` behavior consistently.
- Boundary behavior is test-covered (`2 vs 3` readings, `4.9 vs 5.0` spread, confidence threshold edge).

---

## Phase 3: Virtual Estimation Persistence Model Decision

### Problem

Virtual on-the-fly estimates cannot be persisted immutably with current FK-only `TankEstimation` design.

### Files

- `tankgauge/models/estimation_models.py`
- `tankgauge/logic/estimation_service.py`
- `tankgauge/logic/calculations.py`
- Related migrations

### Decision Options

1. Extend `TankEstimation` with virtual identity fields (`store`, `fuel_type`, `tank_index`) plus validation rules.
2. Create a dedicated `VirtualTankEstimation` model keyed by `(store, fuel_type, tank_index, created_at/is_active)`.

### Recommendation

- Prefer option 2 for cleaner data semantics and immutable evidence lineage.

### Acceptance Criteria

- Virtual mode reuses active cached estimates.
- New virtual estimation versions are append-only, with previous active row deactivated.
- Virtual query path does not depend on non-existent `StoreTankMapping` records.

---

## Phase 4: Data Matching Hardening

### Problem

Mixed exact and case-insensitive fuel matching can cause silent misses.

### Files

- `tankgauge/logic/estimation_service.py`
- `tankgauge/logic/tank_lookup.py`
- `tankgauge/views/estimation_views.py`
- `tankgauge/views/api_views.py`

### Tasks

- Standardize canonical fuel matching:
  - Normalize app-side input (`strip`, case normalization).
  - Use `__iexact` where source data casing may vary.
- Ensure `tank_index` is required and validated for virtual calculation path.

### Acceptance Criteria

- Same physical tank resolves consistently regardless of fuel-type capitalization.
- Virtual resolver cannot run against ambiguous or missing tank index.

---

## Phase 5: UI/Template Consistency Pass

### Problems

- Missing complete mode indicator coverage in template.
- Virtual cards can rely on absent `max_depth` and default JS fallback depth.

### Files

- `tankgauge/templates/tankgauge/components/tank_card.html`
- `tankgauge/views/estimation_views.py`
- `tankgauge/static/tankgauge/js/tankgauge_intel.js`

### Tasks

- Ensure all cards receive explicit `max_depth`:
  - Official mode from `TankType`.
  - Mathematical mode from estimate (`radius * 2`) when appropriate.
- Remove silent magic fallback depth behavior, or explicitly communicate fallback as provisional.
- Tie warning copy/version label to backend-provided algorithm metadata.

### Acceptance Criteria

- Input validation max depth aligns with actual model/chart depth.
- No hidden fallback depth is used without operator visibility.

---

## Phase 6: API-First Alignment (Mission Compliance)

### Problem

Mission requires API-first DRF exposure; current calculation endpoint is a classic Django JSON view.

### Files

- `tankgauge/views/api_views.py`
- New/updated DRF serializers and views
- `tankgauge/urls.py` (or DRF router module)

### Tasks

- Implement DRF serializer for calculation request/response contract.
- Port calculation endpoint to DRF while preserving current frontend behavior.
- Optionally keep legacy endpoint as compatibility shim during migration.

### Acceptance Criteria

- Functional parity with current AJAX client.
- Validation and error shapes are consistent and serializer-driven.

---

## Phase 7: Test Expansion (Required Before Production-Ready Claim)

### Current Gap

Existing tests primarily cover lookup behavior, not full mode and calculation branching.

### Add Tests For

- Mode selection precedence:
  - official chart > persisted estimate > on-the-fly estimate > unavailable
- Persisted estimation execution path returns valid gallons/depth.
- Virtual estimation path with and without sufficient readings.
- Confidence gate boundary conditions.
- Fuel normalization and case-insensitivity scenarios.
- API response schema for each mode and key error paths.

### Acceptance Criteria

- Critical branches in `calculations.py` and `estimation_service.py` are covered.
- New tests pass locally and in CI.

---

## Rollout Strategy

### Order

1. Phase 1 + Phase 2 + tests
2. Phase 4 + Phase 5 + tests
3. Phase 3 (model/migration updates) + tests + data checks
4. Phase 6 (DRF alignment) + frontend verification

### Safety Controls

- Add a feature flag for virtual cached mode if persistence model changes.
- Keep verbose mode-selection logs enabled during first production week.

### Post-Rollout Monitoring

- Track count by mode (`OFFICIAL`, `MATHEMATICAL`, `UNAVAILABLE`, if applicable).
- Track no-fit warning frequency.
- Track confidence distribution trends.
- Audit estimation active/inactive state transitions for correctness.

---

## Definition of Done

- Mode routing is correct across chart and non-chart paths.
- Confidence gates match mission spec and are test-covered.
- Virtual estimation is either explicitly non-persistent by policy or fully persisted with immutable versioning.
- UI labels and input limits reflect backend truth.
- API layer aligns with API-first direction.
- Test suite includes mode/calc/gate coverage beyond lookup utilities.
