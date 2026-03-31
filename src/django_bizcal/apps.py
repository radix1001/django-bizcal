"""Django AppConfig."""

from django.apps import AppConfig


class DjangoBizcalConfig(AppConfig):  # type: ignore[misc]
    """Reusable app configuration for django-bizcal."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "django_bizcal"
    verbose_name = "Django Business Calendar"

    def ready(self) -> None:
        from . import signals  # noqa: F401
