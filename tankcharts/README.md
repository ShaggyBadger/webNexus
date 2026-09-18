# Tank Chart Artifacts

`tankcharts` builds field chart PDFs and publishes them through the DMS. The
chart storage service owns cache replacement, source freshness checks, and the
validity metadata embedded in generated documents.

## Safety Invariants

- Active DMS status alone is not sufficient for a current chart download.
- A chart is blocked when its captured estimate is unsafe, its profile version
  changed, its source data is newer than the document, or its mapping vanished.
- Email and download services repeat the safety check at delivery time; callers
  must not trust a previously returned document object.
- Validity is currently carried in the existing `Document.description` JSON.
  No model or migration changes are part of this implementation.

## Focused Verification

```bash
python manage.py test tankcharts.tests.test_dms_storage
python manage.py test genericcharts.tests.test_dms_service dms.tests
```

See the project conventions in `../instructions/development_conventions.md`.
