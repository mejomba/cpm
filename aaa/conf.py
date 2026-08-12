"""Centralised, override-able settings for the ``aaa`` package.

All configurable behaviour is funnelled through the :data:`app_settings`
singleton so that the rest of the code base never reads ``django.conf.settings``
directly for *our* options. Consumers customise the package by adding an
``AAA`` dictionary to their project ``settings.py``::

    AAA = {
        "OTP_LENGTH": 6,
        "OTP_TTL_SECONDS": 300,
        "GOOGLE_CLIENT_ID": "...",
        "GOOGLE_CLIENT_SECRET": "...",
        "GITHUB_CLIENT_ID": "...",
        "GITHUB_CLIENT_SECRET": "...",
    }

Anything not provided falls back to the values in :data:`DEFAULTS`.
"""

from __future__ import annotations

from typing import Any, Dict

from django.conf import settings
from django.test.signals import setting_changed

# ---------------------------------------------------------------------------
# Default values for every option the package understands.
# ---------------------------------------------------------------------------
DEFAULTS: Dict[str, Any] = {
    # -- One-Time-Password (OTP) behaviour ---------------------------------
    "OTP_LENGTH": 6,                 # Number of digits in a generated OTP.
    "OTP_TTL_SECONDS": 300,          # How long an OTP stays valid (5 minutes).
    "OTP_MAX_ATTEMPTS": 5,           # Verification attempts before invalidation.
    # The cache alias used to store OTP codes. OTPs are short lived so a cache
    # backend (Redis/Memcached/LocMem) is a natural fit.
    "OTP_CACHE_ALIAS": "default",
    # Dotted path to a callable ``send_otp(destination, code, channel)`` used to
    # actually deliver OTP codes. The default just logs them which is fine for
    # development; production projects MUST override this.
    "OTP_SENDER": "aaa.otp.default_otp_sender",

    # -- Registration / login policy --------------------------------------
    # Require email/phone to be verified (via OTP) before the account becomes
    # active. When False, accounts are usable immediately after registration.
    "REQUIRE_VERIFICATION": False,
    # Whether a password is mandatory at registration. Set to False if you only
    # want passwordless OTP login.
    "REQUIRE_PASSWORD": True,

    # -- Social / OAuth providers -----------------------------------------
    "GOOGLE_CLIENT_ID": "",
    "GOOGLE_CLIENT_SECRET": "",
    # The redirect URI registered with Google. Must match exactly.
    "GOOGLE_REDIRECT_URI": "",

    "GITHUB_CLIENT_ID": "",
    "GITHUB_CLIENT_SECRET": "",
    "GITHUB_REDIRECT_URI": "",

    # Registry of available social providers mapping a short ``provider`` slug
    # to the dotted path of its :class:`~aaa.oauth.base.OAuthProvider` subclass.
    "OAUTH_PROVIDERS": {
        "google": "aaa.oauth.google.GoogleOAuthProvider",
        "github": "aaa.oauth.github.GitHubOAuthProvider",
    },
}

# Settings whose values are dotted import paths that should be resolved to the
# actual objects when accessed.
IMPORT_STRINGS = {"OTP_SENDER"}


def _perform_import(value: Any, setting_name: str) -> Any:
    """Resolve a dotted path (or list of them) into the referenced object(s)."""
    if value is None:
        return None
    if isinstance(value, str):
        return _import_from_string(value, setting_name)
    if isinstance(value, (list, tuple)):
        return [_import_from_string(item, setting_name) for item in value]
    return value


def _import_from_string(dotted_path: str, setting_name: str) -> Any:
    """Import a class/function/object from a ``"pkg.module.attr"`` string."""
    from django.utils.module_loading import import_string

    try:
        return import_string(dotted_path)
    except ImportError as exc:  # pragma: no cover - defensive branch
        raise ImportError(
            f"Could not import '{dotted_path}' for AAA setting "
            f"'{setting_name}': {exc}."
        ) from exc


class AppSettings:
    """Lazy accessor for the ``AAA`` settings dictionary.

    Reading an attribute (e.g. ``app_settings.OTP_LENGTH``) looks the value up
    first in the project's ``settings.AAA`` dict and falls back to
    :data:`DEFAULTS`. Values listed in :data:`IMPORT_STRINGS` are transparently
    imported from their dotted paths. Results are cached until the relevant
    setting changes (handy for tests using ``override_settings``).
    """

    def __init__(self, defaults: Dict[str, Any], import_strings: set) -> None:
        self.defaults = defaults
        self.import_strings = import_strings
        # Holds resolved values so repeated access is cheap.
        self._cache: Dict[str, Any] = {}

    @property
    def _user_settings(self) -> Dict[str, Any]:
        """The ``AAA`` dict from the project settings (possibly empty)."""
        return getattr(settings, "AAA", {})

    def __getattr__(self, name: str) -> Any:
        if name not in self.defaults:
            raise AttributeError(f"Invalid AAA setting: '{name}'")

        if name in self._cache:
            return self._cache[name]

        # User-provided value wins, otherwise fall back to the package default.
        try:
            value = self._user_settings[name]
        except KeyError:
            value = self.defaults[name]

        if name in self.import_strings:
            value = _perform_import(value, name)

        self._cache[name] = value
        return value

    def reload(self) -> None:
        """Clear the cache so the next access re-reads project settings."""
        self._cache.clear()


# The singleton imported across the code base.
app_settings = AppSettings(DEFAULTS, IMPORT_STRINGS)


def _reload_app_settings(*, setting, **kwargs) -> None:
    """Invalidate the cache whenever the ``AAA`` setting is overridden."""
    if setting == "AAA":
        app_settings.reload()


# Keep cached settings in sync with ``override_settings`` during tests.
setting_changed.connect(_reload_app_settings)
