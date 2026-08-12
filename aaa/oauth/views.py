"""DRF views for the social-authentication (OAuth2) flow.

Two endpoints per provider, designed for single-page-application front-ends:

1. ``GET  /auth/social/<provider>/url/`` – returns the provider authorization
   URL plus a CSRF ``state`` value. The SPA redirects the browser there.
2. ``POST /auth/social/<provider>/``     – the SPA sends back the ``code`` from
   the provider's redirect; the server exchanges it, links/creates a local user
   and returns a JWT token pair.
"""

from __future__ import annotations

import secrets

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import SocialAccount
from ..serializers import UserSerializer, tokens_for_user
from .base import OAuthUserInfo, get_provider
from .serializers import OAuthCallbackSerializer, OAuthURLResponseSerializer

User = get_user_model()


@transaction.atomic
def get_or_create_user_from_oauth(info: OAuthUserInfo) -> User:
    """Resolve an :class:`OAuthUserInfo` to a local user, creating links as needed.

    Resolution order:
        1. An existing :class:`SocialAccount` for ``(provider, id)`` → its user.
        2. An existing local user with the same verified email → link & return.
        3. Otherwise create a brand new user and link the social account.

    Args:
        info: The normalised profile returned by a provider.

    Returns:
        The local :class:`User` corresponding to the social identity.
    """
    # 1. Already linked? Return the associated user.
    social = SocialAccount.objects.filter(
        provider=info.provider, provider_user_id=info.provider_user_id
    ).first()
    if social:
        return social.user

    # 2. Match by email to link the social login onto an existing account.
    user = None
    if info.email:
        user = User.objects.filter(email__iexact=info.email).first()

    # 3. No match anywhere – create a fresh, pre-verified account.
    if user is None:
        user = User.objects.create_user(
            email=info.email or None,
            first_name=info.first_name,
            last_name=info.last_name,
            # Social logins prove control of the email, so mark it verified.
            is_email_verified=bool(info.email),
            is_active=True,
        )

    # Link the external identity to the (found or created) user.
    SocialAccount.objects.create(
        user=user,
        provider=info.provider,
        provider_user_id=info.provider_user_id,
        extra_data=info.raw,
    )
    return user


class SocialAuthURLView(APIView):
    """``GET /auth/social/<provider>/url/`` – build a provider authorization URL."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, provider: str):
        try:
            oauth = get_provider(provider)
        except ValueError:
            return Response(
                {"detail": f"Unknown provider '{provider}'."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not oauth.is_configured():
            return Response(
                {"detail": f"Provider '{provider}' is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # A random, unguessable anti-CSRF token. Stateless front-ends should
        # persist this (e.g. in sessionStorage) and compare it on callback.
        state = secrets.token_urlsafe(32)
        url = oauth.get_authorization_url(state=state)

        payload = OAuthURLResponseSerializer(
            {"authorization_url": url, "state": state}
        ).data
        return Response(payload, status=status.HTTP_200_OK)


class SocialAuthCallbackView(APIView):
    """``POST /auth/social/<provider>/`` – exchange the code and issue tokens."""

    permission_classes = [permissions.AllowAny]

    def post(self, request, provider: str):
        try:
            oauth = get_provider(provider)
        except ValueError:
            return Response(
                {"detail": f"Unknown provider '{provider}'."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = OAuthCallbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            # 1. Swap the authorization code for an access/id token.
            token_response = oauth.exchange_code(
                code=serializer.validated_data["code"],
                redirect_uri=serializer.validated_data.get("redirect_uri"),
            )
            # 2. Fetch the normalised user profile from the provider.
            info = oauth.get_user_info(token_response)
        except Exception as exc:  # Network error, bad code, malformed response...
            return Response(
                {"detail": f"Social authentication failed: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Map the external identity to a local user and issue our own JWTs.
        user = get_or_create_user_from_oauth(info)
        return Response(
            {
                "user": UserSerializer(user).data,
                "tokens": tokens_for_user(user),
            },
            status=status.HTTP_200_OK,
        )
