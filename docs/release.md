# Release

## Local development

Install in editable mode with development tooling:

```bash
pip install -e ".[dev]"
```

## Run tests

```bash
pytest
```

## Build artifacts

```bash
python -m build
```

Expected outputs:

- `dist/django_bizcal-<version>.tar.gz`
- `dist/django_bizcal-<version>-py3-none-any.whl`

## Publish to TestPyPI

```bash
python -m twine upload --repository testpypi dist/*
```

## Publish to PyPI

```bash
python -m twine upload dist/*
```

## Trusted Publishing

The repository includes a GitHub Actions workflow prepared for PyPI Trusted Publishing.

Recommended flow:

1. Create a release tag such as `v0.1.0`
2. Build and test in CI
3. Use the publish workflow with PyPI environment protection

## Versioning

- Follow semver starting at `0.1.0`
- Keep the root package imports stable for v1 users
- Record user-visible changes in `CHANGELOG.md`

