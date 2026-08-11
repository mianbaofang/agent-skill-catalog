# Contributing

Thanks for improving Agent Skill Catalog.

## Development

The project uses only the Python standard library. Use Python 3.10 or newer.

```text
python tools/validate_package.py .
python tests/test_build_catalog.py
```

Keep scanned roots read-only. Add deterministic fixtures for behavior changes and avoid writing machine-specific paths into the repository or generated fixtures.

## Pull requests

Explain the user-visible behavior, include the validation commands, and keep changes scoped. Do not commit generated catalogs, local reports, credentials, or private skill content.
