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
