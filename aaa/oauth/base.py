"""Provider-agnostic OAuth2 plumbing.

Defines the :class:`OAuthProvider` abstract base class that every social login
provider implements, a small normalised :class:`OAuthUserInfo` value object, and
the :func:`get_provider` factory that maps a provider slug to a configured
instance.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Dict, Optional

import requests
from django.utils.module_loading import import_string

from ..conf import app_settings

# Default network timeout (seconds) for all outbound provider requests.
DEFAULT_TIMEOUT = 10


@dataclass
class OAuthUserInfo:
    """A provider's user profile, normalised to a common shape.

    Every concrete provider maps its raw API payload onto this structure so the
    rest of the code (account linking, user creation) is provider-independent.

    Attributes:
        provider: The provider slug, e.g. ``"google"``.
        provider_user_id: The user's unique id at the provider.
        email: The user's email if available/verified.
        first_name: Given name, if available.
        last_name: Family name, if available.
        raw: The untouched payload returned by the provider.
    """

    provider: str
    provider_user_id: str
    email: Optional[str] = None
    first_name: str = ""
    last_name: str = ""
    raw: Dict = field(default_factory=dict)


class OAuthProvider(abc.ABC):
    """Abstract base class describing the OAuth2 authorization-code flow.

    Subclasses must declare the provider-specific endpoints/scopes as class
    attributes and implement :meth:`get_user_info`. The generic token-exchange
    logic lives here and works for any standard OAuth2 provider.
    """

    #: Short unique slug for the provider (e.g. ``"google"``).
    name: str = ""
    #: The provider's OAuth2 authorization endpoint.
    authorize_url: str = ""
    #: The provider's OAuth2 token endpoint.
    access_token_url: str = ""
    #: Default OAuth scopes requested when none are supplied.
    default_scopes: str = ""

    def __init__(self) -> None:
        """Load this provider's credentials from the ``AAA`` settings."""
        self.client_id = self._setting("CLIENT_ID")
        self.client_secret = self._setting("CLIENT_SECRET")
        self.redirect_uri = self._setting("REDIRECT_URI")

    # -- Configuration helpers ----------------------------------------------
    def _setting(self, suffix: str) -> str:
        """Read ``AAA["<PROVIDER>_<SUFFIX>"]`` for this provider.

        For example the Google provider reads ``GOOGLE_CLIENT_ID`` etc.
        """
        return getattr(app_settings, f"{self.name.upper()}_{suffix}")

    def is_configured(self) -> bool:
        """Return ``True`` if a client id and secret are present."""
        return bool(self.client_id and self.client_secret)

    # -- OAuth2 flow --------------------------------------------------------
    def get_authorization_url(self, state: str, redirect_uri: Optional[str] = None) -> str:
        """Build the URL the browser should be redirected to for consent.

        Args:
            state: An opaque anti-CSRF token the client must echo back.
            redirect_uri: Override for the configured redirect URI (handy when a
                single provider serves multiple front-ends).

        Returns:
            The fully-formed authorization URL including query parameters.
        """
        from urllib.parse import urlencode

        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri or self.redirect_uri,
            "response_type": "code",
            "scope": self.default_scopes,
            "state": state,
        }
        return f"{self.authorize_url}?{urlencode(params)}"

    def exchange_code(self, code: str, redirect_uri: Optional[str] = None) -> Dict:
        """Exchange an authorization ``code`` for an access token.

        Args:
            code: The ``code`` query param the provider sent to the redirect URI.
            redirect_uri: Must match the one used to obtain ``code``.

        Returns:
            The parsed JSON token response (contains ``access_token`` etc.).

        Raises:
            requests.HTTPError: If the token endpoint returns an error status.
        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri or self.redirect_uri,
        }
        # ``Accept: application/json`` makes providers like GitHub return JSON
        # instead of a urlencoded body.
        response = requests.post(
            self.access_token_url,
            data=data,
            headers={"Accept": "application/json"},
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    @abc.abstractmethod
    def get_user_info(self, token_response: Dict) -> OAuthUserInfo:
        """Return the normalised profile for the authenticated provider user.

        Args:
            token_response: The dict returned by :meth:`exchange_code`.

        Returns:
            An :class:`OAuthUserInfo` describing the user.
        """
        raise NotImplementedError


def get_provider(name: str) -> OAuthProvider:
    """Resolve a provider slug to a configured :class:`OAuthProvider` instance.

    Args:
        name: The provider slug, e.g. ``"google"`` or ``"github"``.

    Returns:
        An instantiated provider.

    Raises:
        ValueError: If the slug is not present in ``AAA["OAUTH_PROVIDERS"]``.
    """
    registry = app_settings.OAUTH_PROVIDERS
    if name not in registry:
        raise ValueError(f"Unknown OAuth provider: '{name}'.")
    provider_cls = import_string(registry[name])
    return provider_cls()
