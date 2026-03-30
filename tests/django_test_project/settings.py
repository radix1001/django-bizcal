"""Django settings used by pytest-django."""

SECRET_KEY = "django-bizcal-tests"
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django_bizcal",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
USE_TZ = True
TIME_ZONE = "UTC"
ROOT_URLCONF = "tests.django_test_project.urls"

