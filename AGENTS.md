# Agent Instructions

## Environment Boundary

- This workspace is the laptop development environment for `webNexus`.
- The deployed production instance is hosted on a Linode server.
- Treat local commands, database changes, migrations, test data, and generated
  files as development-only unless the user explicitly requests a production
  operation.
- Do not infer, store, or request production credentials, private hostnames,
  tokens, or connection details from this file.
- Before recommending or performing a production deployment, migration, or
  destructive data operation, confirm the target environment and obtain
  explicit user direction.

Before working:

1. Read `README.md`.
2. Read the relevant documents in `instructions/`.
3. Read the README for every app being changed. If one is missing, ask whether
   an app-specific README should be created.
4. Read `instructions/progress_state.json` before non-trivial work.
5. Follow the project conventions in
   `instructions/development_conventions.md`.
6. Use Graphify according to the project instructions and update it after
   significant code changes.

Confirm that you have familiarized yourself with the project before proceeding.

Use the commands documented in `README.md` and the relevant app README.
