"""Django REST Framework views implementing the authentication endpoints.

The views are deliberately thin: they validate input with the serializers from
:mod:`aaa.serializers`, perform the side effect (create user, issue token, ...)
and return a JSON response. Token issuance uses ``djangorestframework-simplejwt``.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .conf import app_settings
from .otp import otp_service
from .serializers import (
    LoginSerializer,
    LogoutSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    RegisterSerializer,
    UserSerializer,
    tokens_for_user,
)

User = get_user_model()


class RegisterView(APIView):
    """``POST /auth/register/`` – create a new account.

    Anonymous endpoint. On success returns the serialized user. If
    ``AAA["REQUIRE_VERIFICATION"]`` is disabled the response also includes a JWT
    token pair so the client is logged in immediately; otherwise an OTP is sent
    and the client must verify before logging in.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        data = {"user": UserSerializer(user).data}

        if app_settings.REQUIRE_VERIFICATION:
            # Account starts inactive: send a verification OTP to the supplied
            # identifier and tell the client to complete verification.
            destination = user.email or user.phone_number
            otp_service.send(destination, purpose="register")
            data["detail"] = (
                "Account created. A verification code has been sent; verify to "
                "activate your account."
            )
            http_status = status.HTTP_201_CREATED
        else:
            # Immediate login: hand back tokens.
            data["tokens"] = tokens_for_user(user)
            http_status = status.HTTP_201_CREATED

        return Response(data, status=http_status)


class LoginView(APIView):
    """``POST /auth/login/`` – authenticate with identifier + password.

    Returns a JWT token pair and the serialized user on success.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        return Response(
            {
                "user": UserSerializer(user).data,
                "tokens": tokens_for_user(user),
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """``POST /auth/logout/`` – blacklist the caller's refresh token.

    Requires authentication. The access token remains valid until it expires
    naturally; the refresh token is blacklisted so it can no longer mint new
    access tokens.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OTPRequestView(APIView):
    """``POST /auth/otp/request/`` – send an OTP to an email/phone.

    Anonymous endpoint used for passwordless login, registration verification
    and password reset (distinguished by the ``purpose`` field).
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        destination = serializer.save()
        return Response(
            {"detail": f"A verification code has been sent to {destination}."},
            status=status.HTTP_200_OK,
        )


class OTPVerifyView(APIView):
    """``POST /auth/otp/verify/`` – verify an OTP and act on its purpose.

    * ``purpose=login``   – passwordless login; creates the user if necessary
      and returns a JWT token pair.
    * ``purpose=register``/``verify`` – marks the identifier verified and
      activates the account.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        destination = serializer.validated_data["destination"]
        is_email = serializer.validated_data["is_email"]
        purpose = serializer.validated_data["purpose"]

        # Resolve (or, for passwordless login, lazily create) the user.
        lookup = {"email": destination} if is_email else {"phone_number": destination}
        user = User.objects.filter(**lookup).first()

        if user is None:
            if purpose == "login":
                # Passwordless first-time login: provision a verified account.
                user = User.objects.create_user(**lookup)
            else:
                return Response(
                    {"detail": "No account found for this identifier."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # Mark the relevant identifier verified and (re)activate the account.
        if is_email:
            user.is_email_verified = True
        else:
            user.is_phone_verified = True
        user.is_active = True
        user.save()

        return Response(
            {
                "user": UserSerializer(user).data,
                "tokens": tokens_for_user(user),
            },
            status=status.HTTP_200_OK,
        )


class PasswordChangeView(APIView):
    """``POST /auth/password/change/`` – change password while logged in."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": "Password updated successfully."}, status=status.HTTP_200_OK
        )


class PasswordResetRequestView(APIView):
    """``POST /auth/password/reset/`` – start a forgotten-password reset.

    Thin wrapper around the OTP-request flow that forces ``purpose="reset"``.
    Always returns 200 regardless of whether the account exists, to avoid
    leaking which identifiers are registered.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data = {**request.data, "purpose": "reset"}
        serializer = OTPRequestSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        # Only actually send if an account exists, but respond identically.
        destination = serializer.validated_data["destination"]
        from django.db.models import Q

        if User.objects.filter(
            Q(email=destination) | Q(phone_number=destination)
        ).exists():
            otp_service.send(destination, purpose="reset")
        return Response(
            {"detail": "If an account exists, a reset code has been sent."},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    """``POST /auth/password/reset/confirm/`` – set a new password via OTP."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": "Password has been reset. You can now log in."},
            status=status.HTTP_200_OK,
        )


class MeView(generics.RetrieveUpdateAPIView):
    """``GET/PATCH /auth/me/`` – read or update the current user's profile."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        """Always operate on the authenticated user."""
        return self.request.user
