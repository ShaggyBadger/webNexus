# TankGauge

`tankgauge` owns the canonical store and tank records used by webNexus fuel
operations.

## Responsibilities

- `models/store_models.py` — canonical stores and store-to-tank assignments.
- `models/hardware_models.py` — tank types and official tank charts.
- `models/estimation_models.py` and `models/virtual_estimation.py` — generated
  tank geometry and estimation history.
- `logic/` — tank calculations, source selection, limits, and shared domain
  rules.
- `admin/` — staff administration for canonical tank and estimation records.
- `management/commands/` — maintenance and data export commands.

## Store Types

`StoreType` is the reference table for standardized store or brand names. It
currently contains only a unique `name`; existing `Store.store_type` text data
is intentionally not migrated to this table yet. Future work may add metadata
and foreign-key relationships after the reference list has been reviewed.

## Boundaries

- Keep canonical store and tank data here; proposal workflow records remain in
  `siteintel` until approved.
- Keep complex calculations in `logic/` rather than models or views.
- Preserve source and estimation history; do not silently destroy operational
  evidence.
- `StoreTankMapping.canonical_fuel_type` is the stored identity key for profile
  resolution. Capacity edits are versioned in `TankCapacityProfileHistory`; the
  backfill command is preview-only unless `--apply` is supplied and never
  recalculates geometry implicitly.
- `StoreTankMapping.tank_index` is unique within a store because it identifies
  one physical ATG tank. Admin validation rejects duplicate assignments; repair
  legacy duplicates before changing profile data.
- Use migrations for schema changes and regenerate
  `instructions/database_schema.dbml` afterward.

## Focused Verification

```bash
python manage.py test tankgauge
python manage.py check
python manage.py makemigrations --check --dry-run
```

See the project conventions in [`../instructions/development_conventions.md`](../instructions/development_conventions.md).
