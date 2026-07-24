# AGENTS Documentation

## Build, Lint, and Test Commands

### Build Command
To build the project, execute:
```bash
python manage.py build
```

### Lint Command
To lint the codebase, run:
```bash
black .
```

### Test Command
To run all tests, use:
```bash
python manage.py test
```
To run a specific test, use the following format:
```bash
python manage.py test <app_name>.<TestClassName>.<test_method>
```
For example:
```bash
python manage.py test homepage.tests.HomePageTests.test_home
```

## Code Style Guidelines

### Imports
- Group imports in the following order:
  1. Standard library imports.
  2. Related third-party imports.
  3. Local application/library imports.
- Do not use wildcard imports.

### Formatting
- Use [Black](https://black.readthedocs.io/en/stable/) for automatic code formatting.
- Keep lines to a maximum of 88 characters.

### Types
- Use type hints for all public methods.
- Follow PEP 484 for type hinting conventions.

### Naming Conventions
- Use `lowercase_with_underscores` for function and variable names.
- Use `CamelCase` for class names.
- Constants should be `UPPERCASE_WITH_UNDERSCORES`.

### Error Handling
- Use Exceptions for managing errors.
- Catch specific exceptions rather than using bare `except` clauses.

### Function Documentation
- Use docstrings to describe the purpose of the function and its parameters following PEP 257 standards.

### Classes
- Each class should have a docstring at its beginning explaining its purpose and usage.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
