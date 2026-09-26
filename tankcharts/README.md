# Tank Chart Artifacts

`tankcharts` builds field chart PDFs and publishes them through the DMS. The
chart storage service owns cache replacement, source freshness checks, and the
validity metadata embedded in generated documents.

## Published Snapshot Availability

- Active tank-chart documents remain downloadable and emailable as generated
  snapshots, even when current profile versions, estimates, source data, or
  captured validity metadata change later.
- Superseded/archived DMS lifecycle status, access permissions, and missing files
  still block delivery.
- Per-store source freshness checks continue to decide whether the chart cache
  should be regenerated; they no longer invalidate delivery of the currently
  published chart while a replacement is unavailable.
- Validity is currently carried in the existing `Document.description` JSON.
  No model or migration changes are part of this implementation.

## Focused Verification

```bash
python manage.py test tankcharts.tests.test_dms_storage
python manage.py test genericcharts.tests.test_dms_service dms.tests
```

See the project conventions in `../instructions/development_conventions.md`.
