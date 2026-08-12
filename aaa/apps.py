"""Django application configuration for the ``aaa`` package."""

from django.apps import AppConfig


class AaaConfig(AppConfig):
    """App config for the authentication system.

    Registering this app in ``INSTALLED_APPS`` wires up the custom user model,
    the admin integration and the management of signals (if any).
    """

    # Use ``BigAutoField`` for the implicit primary key of any model that does
    # not define one explicitly. Matches modern Django project defaults.
    default_auto_field = "django.db.models.BigAutoField"

    # The importable name of the application.
    name = "aaa"

    # A human readable name shown in the Django admin.
    verbose_name = "Authentication (aaa)"

    def ready(self) -> None:
        """Hook executed once the app registry is fully populated.

        We import the signal handlers module here so that the ``@receiver``
        decorators inside it get registered. Importing at module import time
        would risk triggering "app not ready" errors, hence doing it in
        ``ready()``.
        """
        # Imported for its side effects (signal registration). The ``# noqa``
        # silences the "imported but unused" linter warning.
        from . import signals  # noqa: F401
