"""URL routing for the ``aaa`` authentication API.

Include this in your project's root ``urls.py``::

    urlpatterns = [
        path("api/auth/", include("aaa.urls")),
    ]

which mounts all endpoints under ``/api/auth/``.
"""

from __future__ import annotations

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from .oauth.views import SocialAuthCallbackView, SocialAuthURLView
from .views import (
    LoginView,
    LogoutView,
    MeView,
    OTPRequestView,
    OTPVerifyView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterView,
)

# Namespacing lets consumers reverse URLs as ``aaa:login`` etc.
app_name = "aaa"

urlpatterns = [
    # -- Core credential auth ----------------------------------------------
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),

    # -- JWT token lifecycle (refresh / verify) ----------------------------
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),

    # -- OTP (passwordless login & verification) ---------------------------
    path("otp/request/", OTPRequestView.as_view(), name="otp_request"),
    path("otp/verify/", OTPVerifyView.as_view(), name="otp_verify"),

    # -- Password management -----------------------------------------------
    path("password/change/", PasswordChangeView.as_view(), name="password_change"),
    path("password/reset/", PasswordResetRequestView.as_view(), name="password_reset"),
    path(
        "password/reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),

    # -- Current user profile ----------------------------------------------
    path("me/", MeView.as_view(), name="me"),

    # -- Social / OAuth2 login ---------------------------------------------
    # ``<provider>`` is a slug from AAA["OAUTH_PROVIDERS"] (e.g. google, github).
    path(
        "social/<str:provider>/url/",
        SocialAuthURLView.as_view(),
        name="social_url",
    ),
    path(
        "social/<str:provider>/",
        SocialAuthCallbackView.as_view(),
        name="social_callback",
    ),
]
