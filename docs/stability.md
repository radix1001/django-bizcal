# Stability and Support

## Stable import surfaces

The stable public API for consumers is defined at the package level:

- `django_bizcal`
- `django_bizcal.django_api`

These surfaces are contract-tested through exact `__all__` assertions in the
test suite. They are the import paths that will carry the compatibility
guarantees for `1.x`.

## Internal modules

Modules under `src/django_bizcal/` remain importable for advanced users, but
they are not the primary compatibility contract unless their symbols are also
re-exported by one of the stable package-level modules above.

That means:

- `django_bizcal` and `django_bizcal.django_api` are the stable surfaces
- direct imports from implementation modules should be treated as lower-level
- examples and application code should prefer those package-level exports

## Supported runtime policy

`django-bizcal` targets maintained Django release lines and keeps a CI matrix
that follows the officially supported Python combinations for those releases.

Current actively tested Django lines:

- Django `5.2` LTS
- Django `6.0`

Current actively tested Python lines:

- Python `3.11`
- Python `3.12`
- Python `3.13`
- Python `3.14`

The CI matrix intentionally uses supported combinations instead of the full
cartesian product because upstream Django support differs by series.

Current CI combinations:

- Python `3.11` with Django `5.2`
- Python `3.12` with Django `5.2`
- Python `3.13` with Django `5.2`
- Python `3.14` with Django `5.2`
- Python `3.12` with Django `6.0`
- Python `3.13` with Django `6.0`
- Python `3.14` with Django `6.0`

## Backward compatibility target for 1.x

Before `1.0.0`, the project may still add focused hardening or small ergonomic
improvements. Starting with `1.0.0`, the intent is:

- no breaking changes to package-level public imports in `1.x` without a deprecation path
- no silent semantic changes to documented business-time behavior
- no broadening of the ORM persistence scope without explicit documentation and changelog treatment

## What is expected to remain stable

- core calendar operations
- calendar composition semantics
- deadline helper semantics
- declarative builders and policy builders
- public exception types exported from the package-level API
- Django settings names
- Django service entry points exported from `django_bizcal.django_api`
- optional persistence models already published in the Django app

## What is intentionally not promised yet

- distributed cache coordination across processes
- ORM persistence for full calendar graphs
- ORM persistence for full deadline-policy graphs
- performance numbers as hard API guarantees

For repeatable local performance checks, use `examples/performance_benchmark.py`.

## Release gate before 1.0.0

The final pre-`1.0.0` bar should include:

- passing local validation: `ruff`, `mypy`, `pytest`, `build`, `twine check`
- passing CI matrix on supported Django and Python combinations
- stable package-level export tests
- documented production, upgrade, release, and support guidance
