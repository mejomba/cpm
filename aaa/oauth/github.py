"""GitHub OAuth2 provider implementation."""

from __future__ import annotations

from typing import Dict, Optional

import requests

from .base import DEFAULT_TIMEOUT, OAuthProvider, OAuthUserInfo


class GitHubOAuthProvider(OAuthProvider):
    """"Login with GitHub" using the standard OAuth2 authorization-code flow.

    Unlike Google, GitHub does not return identity in the token response, so we
    make follow-up calls to the REST API to fetch the user profile and (because
    a user's primary email can be private) their verified email addresses.
    """

    name = "github"
    authorize_url = "https://github.com/login/oauth/authorize"
    access_token_url = "https://github.com/login/oauth/access_token"
    # ``read:user`` for the profile; ``user:email`` to read private emails.
    default_scopes = "read:user user:email"

    #: GitHub REST API endpoints used after the token exchange.
    user_api_url = "https://api.github.com/user"
    emails_api_url = "https://api.github.com/user/emails"

    def get_user_info(self, token_response: Dict) -> OAuthUserInfo:
        """Fetch the GitHub profile and best email, returning ``OAuthUserInfo``."""
        access_token = token_response.get("access_token")
        if not access_token:
            raise ValueError("GitHub token response did not include an access_token.")

        headers = {
            "Authorization": f"token {access_token}",
            "Accept": "application/vnd.github+json",
        }

        # 1. Core profile.
        profile = requests.get(
            self.user_api_url, headers=headers, timeout=DEFAULT_TIMEOUT
        )
        profile.raise_for_status()
        data = profile.json()

        # 2. Email may be ``null`` on the profile if the user keeps it private,
        #    so fall back to the dedicated emails endpoint.
        email = data.get("email") or self._fetch_primary_email(headers)

        # GitHub exposes a single ``name`` field; split it into first/last best
        # effort for our model.
        full_name = (data.get("name") or "").strip()
        first_name, _, last_name = full_name.partition(" ")

        return OAuthUserInfo(
            provider=self.name,
            provider_user_id=str(data["id"]),
            email=email,
            first_name=first_name,
            last_name=last_name,
            raw=data,
        )

    def _fetch_primary_email(self, headers: Dict[str, str]) -> Optional[str]:
        """Return the user's primary, verified email or ``None``.

        Args:
            headers: Authorization headers built in :meth:`get_user_info`.
        """
        resp = requests.get(
            self.emails_api_url, headers=headers, timeout=DEFAULT_TIMEOUT
        )
        if resp.status_code != 200:
            return None
        emails = resp.json()
        # Prefer the address GitHub marks as both primary and verified.
        for entry in emails:
            if entry.get("primary") and entry.get("verified"):
                return entry.get("email")
        # Otherwise accept any verified address.
        for entry in emails:
            if entry.get("verified"):
                return entry.get("email")
        return None
