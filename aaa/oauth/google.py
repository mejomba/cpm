"""Google OAuth2 / OpenID Connect provider implementation."""

from __future__ import annotations

from typing import Dict

import jwt  # PyJWT – used to decode the OIDC id_token.

from .base import OAuthProvider, OAuthUserInfo


class GoogleOAuthProvider(OAuthProvider):
    """"Login with Google" using the OpenID Connect authorization-code flow.

    Google returns an ``id_token`` (a signed JWT) in the token response that
    already contains the user's profile claims, so we can read identity straight
    from it without an extra userinfo request.
    """

    name = "google"
    authorize_url = "https://accounts.google.com/o/oauth2/v2/auth"
    access_token_url = "https://oauth2.googleapis.com/token"
    # ``openid`` is required for the id_token; ``email``/``profile`` add claims.
    default_scopes = "openid email profile"

    def get_user_info(self, token_response: Dict) -> OAuthUserInfo:
        """Decode the ``id_token`` JWT and map its claims to ``OAuthUserInfo``.

        Note:
            We decode without verifying the signature because the token was just
            received directly from Google's TLS-protected token endpoint in
            response to our authenticated request. For defence in depth you may
            instead verify against Google's JWKS.
        """
        id_token = token_response.get("id_token")
        if not id_token:
            raise ValueError("Google token response did not include an id_token.")

        # ``options`` disables signature/audience verification since the token is
        # trusted by virtue of its TLS-authenticated origin.
        claims = jwt.decode(
            id_token,
            options={"verify_signature": False, "verify_aud": False},
        )

        return OAuthUserInfo(
            provider=self.name,
            provider_user_id=claims["sub"],
            email=claims.get("email"),
            first_name=claims.get("given_name", ""),
            last_name=claims.get("family_name", ""),
            raw=claims,
        )
