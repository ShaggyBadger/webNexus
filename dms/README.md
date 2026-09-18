# Document Management System

`dms` stores uploaded and generated operational documents and owns the common
download and email delivery boundaries.

Generated chart safety is delegated to
`dms.services.chart_artifact_safety`; ordinary uploaded documents retain their
existing lifecycle and access behavior. Chart documents must be `ACTIVE`, have
operational state `USABLE`, and pass their source-specific runtime validity
check before download or email. Unsafe and superseded files remain retained as
historical evidence.

## Focused Verification

```bash
python manage.py test dms.tests
```
