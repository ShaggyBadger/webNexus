# webNexus

webNexus is a Django-based field operations command center for fuel and tank
data workflows.

## Before Working

1. Read the relevant documents in [`instructions/`](instructions/), especially:
   - [`development_conventions.md`](instructions/development_conventions.md)
   - [`progress_state.json`](instructions/progress_state.json)
   - [`api_contracts.json`](instructions/api_contracts.json) for API changes
   - [`database_schema.dbml`](instructions/database_schema.dbml) for database work
2. Check the current initiative and active plans before making non-trivial changes.
3. When touching an app, check for that app's `README.md`.
4. If the app has no README, prompt the project owner before implementation and
   ask whether an app-specific README should be created.

## App README Standard

Each substantial Django app should have a concise, maintained `README.md` that
documents:

- purpose, operational boundary, and ownership
- package structure and module responsibilities
- data flow and integration points
- architectural invariants and important decisions
- app-specific configuration, versioning, and naming rules
- focused test and validation commands
- maintenance instructions and a short change history when useful

Keep responsibilities in focused modules. Update the app README when behavior,
structure, public contracts, or maintenance procedures change. Do not turn it
into a duplicate of the project-wide conventions; document only app-specific
knowledge and link back here or to `instructions/` when appropriate.

## Development Commands

```bash
python manage.py build
python manage.py test
black .
python manage.py makemigrations --check --dry-run
```

Use focused tests during development, then run the broadest practical
verification before completing substantial work.

## Public Repository Rules

This is public-repository documentation and source code.

- Never commit passwords, tokens, API keys, private keys, database dumps, or
  `.env` files.
- Do not publish private infrastructure details, personal data, or sensitive
  operational records.
- Use placeholders and environment-variable names in examples.
- Review generated files and documentation for secrets before committing.
- Preserve raw operational data only in approved private storage, never in the
  public repository.

## Documentation Workflow

For a non-trivial change:

1. Read `instructions/` and the README for every app being changed.
2. If an app README is missing, stop and ask whether to create one.
3. Create or update the relevant plan under `instructions/` before coding.
4. Keep `instructions/progress_state.json` current during implementation.
5. Update API contracts, DBML, app READMEs, and tests when applicable.
6. Archive completed plans and update the progress state when the work is done.

Keep documentation concise, explicit, and useful to the next contributor.
