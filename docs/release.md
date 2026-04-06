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

Recommended full validation before cutting a release:

```bash
ruff check src tests examples .github
mypy src
pytest
python -m build
python -m twine check dist/*
```

## Build artifacts

```bash
python -m build
```

Expected outputs:

- `dist/django_bizcal-<version>.tar.gz`
- `dist/django_bizcal-<version>-py3-none-any.whl`

Validate artifacts before uploading:

```bash
python -m twine check dist/*
```

## Preferred publishing flow

The recommended publication path for `django-bizcal` is GitHub Actions plus PyPI Trusted Publishing.

Why:

- No long-lived PyPI token needs to be stored in GitHub.
- PyPI mints short-lived credentials for the exact workflow that is trusted.
- GitHub environments can require additional approval before upload.

### One-time setup in PyPI

For the existing PyPI project `django-bizcal`, configure a Trusted Publisher in PyPI with:

- owner: `radix1001`
- repository: `django-bizcal`
- workflow file: `.github/workflows/publish.yml`
- environment: `pypi`

Recommended follow-up:

1. Go to the PyPI project settings for `django-bizcal`
2. Open `Publishing`
3. Add the GitHub Actions trusted publisher above
4. Revoke any previously used long-lived API tokens that are no longer needed

Official reference:

- [Adding a Trusted Publisher to an existing PyPI project](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
- [Publishing with a Trusted Publisher](https://docs.pypi.org/trusted-publishers/using-a-publisher/)

### One-time setup in GitHub

In the GitHub repository:

1. Create an environment named `pypi`
2. Optionally require manual approval for deployments to that environment
3. Use GitHub Releases or manual workflow dispatch to publish

Recommended hardening:

- Restrict the `pypi` environment to approved branches and tags
- Require reviewer approval before deployment when appropriate

Official reference:

- [Managing environments for deployment](https://docs.github.com/en/actions/reference/environments)

### Publish a release

1. Update version and changelog
2. Push changes to `main`
3. Create and push a tag like `vX.Y.Z`
4. Create a GitHub Release for that tag
5. The `Publish` workflow builds, validates, and uploads the distributions to PyPI

Typical command sequence:

```bash
git push origin main
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

## Fallback manual publishing

Trusted Publishing should be the default. Manual `twine upload` is only a fallback for emergencies or initial setup troubleshooting.

### Publish to TestPyPI

```bash
python -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*
```

### Publish to PyPI

```bash
python -m twine upload dist/*
```

## Token hygiene

If an API token is ever exposed in logs, chat, shell history, or screenshots:

1. Revoke it immediately in PyPI
2. Create a new token only if you still need a fallback manual path
3. Prefer Trusted Publishing so future releases do not require long-lived tokens

Official reference:

- [PyPI help: API tokens and Trusted Publishers](https://pypi.org/help/)

## Trusted Publishing references

- [Trusted Publishing overview](https://docs.pypi.org/trusted-publishers/)
- [Adding a Trusted Publisher to an existing PyPI project](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
- [Publishing with a Trusted Publisher](https://docs.pypi.org/trusted-publishers/using-a-publisher/)

## Versioning

- Follow semver starting at `0.1.0`
- Keep the root package imports stable for v1 users
- Record user-visible changes in `CHANGELOG.md`
- Keep `docs/stability.md` aligned with the tested support matrix before each release
