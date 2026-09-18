# ATG Gauge Data Intake

`atg` owns Veeder-Root ticket evidence, structured tank readings, OCR review,
and the staff gauge-data intake workflow.

## Responsibilities

- `models/` preserves ticket images, OCR payloads, decimal Gross/ullage/level
  readings, printed capacity evidence, and acceptance status.
- `services/` handles ticket ingestion, reading validation, preflight, auto-
  mapping, and post-ingest estimation triggers.
- `serializers/` defines staff, review, and OCR reading contracts.
- `views/` exposes authenticated intake/review APIs and the mobile intake page.
- `templates/` and `static/` provide the field-facing Gauge Data Intake UI.

## Data Invariants

- Raw ticket images, OCR text, original line text, and source values are never
  silently rewritten.
- `VeederReading.volume` is Gross gallons; Net gallons are not stored.
- Decimal volume, ullage, and level values retain ticket precision.
- Printed physical capacity and the ullage endpoint are separate facts.
- Only accepted readings participate in geometry estimation.
- Capacity verification belongs to the canonical `tankgauge.StoreTankMapping`
  profile; intake readings preserve evidence but do not silently change it.

## Focused Verification

```bash
python manage.py test atg
python manage.py check
python manage.py makemigrations --check --dry-run
```

Review changes must preserve the API contracts in `../instructions/api_contracts.json`
and the evidence-preservation rules in `../instructions/veeder_capacity_geometry_plan.md`.
