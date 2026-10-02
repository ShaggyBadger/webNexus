# Site Intelligence

`siteintel` owns field-submitted site proposals and their administrative review
workflow. Approved store proposals synchronize shared `Location` data and
canonical `tankgauge.Store` and `StoreTankMapping` records.

## Boundaries and invariants

- Proposal rows remain separate from canonical store and tank records until
  approval succeeds.
- Approval synchronization runs atomically. Failed attempts remain pending and
  can be corrected and retried.
- Tank mappings are durable identities referenced by capacity history and tank
  estimates. Store proposal synchronization reuses a mapping for the same
  physical index/fuel, creates validated new mappings, and never deletes or
  silently repurposes existing mappings.
- Tank indexes must be positive and unique within both the submitted tank list
  and the store's canonical assignments. A fuel mismatch at an existing index
  fails closed for separate review.
- New canonical mappings require a selected `TankType`. An existing mapping
  keeps its current type when the proposal does not select one.
- Omitted mappings remain unchanged. Tank retirement/deactivation is not part
  of this proposal sync workflow.
- Capacity-profile fields and `TankCapacityProfileHistory` are maintained by
  their capacity-profile workflows, not by `TankUpdate.reported_capacity`.

## Package responsibilities

- `models/` — `Location`, `StoreUpdate`, `TankUpdate`, site specializations, and
  intelligence records.
- `forms/` — field proposal forms and tank inline formsets.
- `views/` — proposal submission, directory lookup, and site intelligence pages.
- `admin/` — administrative review, approval, and canonical synchronization
  entry points.
- `logic/proposal_processor.py` — transactional orchestration for `Location`
  and specialized canonical records.
- `logic/tank_mapping_sync.py` — preflight validation and non-destructive tank
  mapping reconciliation called inside the proposal transaction.
- `services/` — focused integration services such as geocoding.

## Store proposal flow

1. Authenticated field submissions create a pending `StoreUpdate` and related
   `TankUpdate` rows.
2. An administrator approves the proposal through the bulk action or the
   change form. The change-form path saves inline tank rows before applying the
   proposal so synchronization uses the submitted values.
3. `StoreUpdate.apply_update()` delegates to `logic.proposal_processor`.
4. `apply_proposal()` updates or creates the shared location and store inside
   one atomic transaction.
5. `tank_mapping_sync.sync_store_tank_mappings()` validates the complete
   proposed tank set before writing mappings. It matches by physical tank index,
   then verifies normalized fuel identity. It updates existing mappings without
   replacing their primary keys or profile fields, creates missing mappings
   with a selected tank type, and preserves unmentioned mappings.
6. Chart-relevant mapping changes schedule store-chart refresh after commit.
   Validation or synchronization failures roll back canonical changes and
   restore the proposal's pre-approval state, leaving the proposal retryable.

## Focused verification

```bash
python manage.py test siteintel --noinput
python manage.py check
python manage.py makemigrations --check --dry-run
```

Chart refresh behavior is covered by:

```bash
python manage.py test tankcharts.tests.test_signals --noinput
```

See the project-wide engineering and documentation workflow in
[`../instructions/development_conventions.md`](../instructions/development_conventions.md).
