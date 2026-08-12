"""Serializers for the social-authentication endpoints."""

from __future__ import annotations

from rest_framework import serializers


class OAuthURLResponseSerializer(serializers.Serializer):
    """Response shape for the "build authorization URL" endpoint."""

    authorization_url = serializers.URLField(
        help_text="Redirect the user's browser here to begin consent."
    )
    state = serializers.CharField(
        help_text="Opaque anti-CSRF token; must be echoed back on callback."
    )


class OAuthCallbackSerializer(serializers.Serializer):
    """Input for the callback endpoint that completes the OAuth flow.

    The front-end obtains ``code`` from the provider's redirect and posts it
    here (an SPA-friendly pattern). ``redirect_uri`` is required only if it
    differs from the one configured in settings.
    """

    code = serializers.CharField(help_text="Authorization code from the provider.")
    redirect_uri = serializers.URLField(
        required=False,
        help_text="Must match the redirect URI used to obtain the code.",
    )
