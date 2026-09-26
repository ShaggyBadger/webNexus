# Document Management System

`dms` stores uploaded and generated operational documents and owns the common
download and email delivery boundaries.

Generated charts are published as downloadable snapshots. An active chart
remains available even when newer profiles, estimates, source data, or unsafe
validity metadata differ from the snapshot. The DMS lifecycle status, normal
access rules, and file-existence checks still apply; superseded and archived
documents are not available. Non-chart document safety behavior is unchanged.

CoreStarterPack packages are refreshed by explicitly generating a new package.
Publishing the new package supersedes the previous document in that scope while
retaining it as historical evidence. Per-store tank chart cache refresh behavior
is unchanged.

## Failed Download Events

The routed document download endpoint records expected failures in the
append-only `DocumentDownloadFailure` event table after the download service's
atomic block has rolled back. The event stores a stable reason code, document ID
and title snapshots, timestamp, optional user, and request trace ID. It does not
store exception text, storage paths, IP addresses, or user-agent values.

Staff with the model's Django Admin view permission can search and filter the
read-only **Document Download Failures** listing. The admin UI is themed with
Jazzmin; static assets are served through Django's staticfiles pipeline.

## Focused Verification

```bash
python manage.py test dms.tests
```
