"""Django REST Framework serializers for the ``aaa`` authentication flows.

Each serializer is intentionally small and single-purpose. Validation that
touches the database (uniqueness, existence) lives here; the views stay thin and
mostly orchestrate serializers + token issuance.
"""

from __future__ import annotations

from typing import Any, Dict

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .conf import app_settings
from .otp import otp_service
from .validators import (
    looks_like_email,
    normalize_phone,
    validate_email,
    validate_phone,
)

User = get_user_model()


def tokens_for_user(user) -> Dict[str, str]:
    """Issue a fresh access/refresh JWT pair for ``user``.

    Args:
        user: The authenticated user.

    Returns:
        A dict with ``"access"`` and ``"refresh"`` JWT strings.
    """
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


class UserSerializer(serializers.ModelSerializer):
    """Read-only-ish representation of a user for API responses.

    Used to embed the user object in auth responses and to power the
    ``/me`` profile endpoint (where a subset of fields is writable).
    """

    class Meta:
        model = User
        fields = [
            "uid",
            "email",
            "phone_number",
            "first_name",
            "last_name",
            "is_email_verified",
            "is_phone_verified",
            "is_verified",
            "is_active",
            "date_joined",
        ]
        # Identity and status fields are managed by the auth flows, not edited
        # directly through the profile endpoint.
        read_only_fields = [
            "uid",
            "email",
            "phone_number",
            "is_email_verified",
            "is_phone_verified",
            "is_verified",
            "is_active",
            "date_joined",
        ]


class RegisterSerializer(serializers.Serializer):
    """Validate and create a new account from an email *or* phone number.

    Exactly one identifier is required (supplying both is allowed and links
    them on the same account). A password is required unless
    ``AAA["REQUIRE_PASSWORD"]`` is ``False``.
    """

    email = serializers.EmailField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        style={"input_type": "password"},
    )

    def validate_email(self, value: str) -> str:
        """Lower-case the email and ensure it is not already registered."""
        if not value:
            return value
        value = value.strip().lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(_("A user with this email already exists."))
        return value

    def validate_phone_number(self, value: str) -> str:
        """Normalise the phone, validate its format and ensure uniqueness."""
        if not value:
            return value
        value = normalize_phone(value)
        validate_phone(value)  # Raises DRF-friendly ValidationError on failure.
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError(
                _("A user with this phone number already exists.")
            )
        return value

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Cross-field checks: identifier presence and password policy."""
        email = attrs.get("email")
        phone = attrs.get("phone_number")
        if not email and not phone:
            raise serializers.ValidationError(
                _("Provide either an email address or a phone number.")
            )

        password = attrs.get("password")
        if app_settings.REQUIRE_PASSWORD and not password:
            raise serializers.ValidationError({"password": _("This field is required.")})

        # Run Django's configured password validators (length, common, etc.).
        if password:
            validate_password(password)
        return attrs

    def create(self, validated_data: Dict[str, Any]):
        """Create the user via the custom manager.

        When ``AAA["REQUIRE_VERIFICATION"]`` is enabled the account is created
        inactive until the identifier is confirmed via OTP.
        """
        password = validated_data.pop("password", None) or None
        user = User.objects.create_user(
            email=validated_data.get("email") or None,
            phone_number=validated_data.get("phone_number") or None,
            password=password,
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            is_active=not app_settings.REQUIRE_VERIFICATION,
        )
        return user


class LoginSerializer(serializers.Serializer):
    """Authenticate a user by email-or-phone identifier + password."""

    # A single field accepting either an email or a phone number.
    identifier = serializers.CharField(
        help_text=_("Your email address or phone number."),
    )
    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Run the authentication backend and attach the user to the result."""
        identifier = attrs.get("identifier")
        password = attrs.get("password")

        # ``authenticate`` walks AUTHENTICATION_BACKENDS; our EmailOrPhoneBackend
        # resolves the identifier to the right column.
        user = authenticate(
            request=self.context.get("request"),
            username=identifier,
            password=password,
        )
        if user is None:
            raise serializers.ValidationError(
                _("Unable to log in with the provided credentials."),
                code="authorization",
            )
        if not user.is_active:
            raise serializers.ValidationError(
                _("This account is inactive. Please verify your account first."),
                code="inactive",
            )

        attrs["user"] = user
        return attrs


class OTPRequestSerializer(serializers.Serializer):
    """Request that an OTP code be sent to an email or phone number."""

    destination = serializers.CharField(
        help_text=_("Email address or phone number to send the code to."),
    )
    # Scopes the code to a flow so a register-OTP can't be used to log in, etc.
    purpose = serializers.ChoiceField(
        choices=["register", "login", "verify", "reset"],
        default="login",
    )

    def validate_destination(self, value: str) -> str:
        """Validate the destination is a well-formed email or phone number."""
        value = value.strip()
        if looks_like_email(value):
            validate_email(value)
            return value.lower()
        normalized = normalize_phone(value)
        validate_phone(normalized)
        return normalized

    def save(self, **kwargs) -> str:
        """Generate and dispatch the OTP, returning its destination."""
        destination = self.validated_data["destination"]
        purpose = self.validated_data["purpose"]
        otp_service.send(destination, purpose=purpose)
        return destination


class OTPVerifySerializer(serializers.Serializer):
    """Verify an OTP code and (for the login/verify purpose) return tokens.

    Behaviour by purpose:
        * ``login``  – find/return the user and mark the identifier verified.
        * ``verify`` – mark the current/identified user's identifier verified.
        * ``register`` – activate a freshly registered account.
    """

    destination = serializers.CharField()
    code = serializers.CharField()
    purpose = serializers.ChoiceField(
        choices=["register", "login", "verify", "reset"],
        default="login",
    )

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Normalise the destination and check the supplied OTP code."""
        destination = attrs["destination"].strip()
        is_email = looks_like_email(destination)
        destination = destination.lower() if is_email else normalize_phone(destination)
        attrs["destination"] = destination
        attrs["is_email"] = is_email

        if not otp_service.verify(destination, attrs["code"], purpose=attrs["purpose"]):
            raise serializers.ValidationError(
                {"code": _("Invalid or expired verification code.")}
            )
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    """Let an authenticated user change their password."""

    old_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_old_password(self, value: str) -> str:
        """Ensure the supplied current password is correct."""
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError(_("Your current password is incorrect."))
        return value

    def validate_new_password(self, value: str) -> str:
        """Run Django's password validators against the new password."""
        validate_password(value, user=self.context["request"].user)
        return value

    def save(self, **kwargs):
        """Persist the new password hash on the user."""
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Reset a forgotten password using an OTP sent to email/phone.

    The client first calls the OTP-request endpoint with ``purpose="reset"``;
    this serializer then validates the code and sets the new password.
    """

    destination = serializers.CharField()
    code = serializers.CharField()
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve the user from the destination and verify the OTP code."""
        destination = attrs["destination"].strip()
        is_email = looks_like_email(destination)
        destination = destination.lower() if is_email else normalize_phone(destination)

        # Locate the account the reset is for.
        lookup = {"email": destination} if is_email else {"phone_number": destination}
        try:
            user = User.objects.get(**lookup)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"destination": _("No account found for this email or phone number.")}
            )

        if not otp_service.verify(destination, attrs["code"], purpose="reset"):
            raise serializers.ValidationError(
                {"code": _("Invalid or expired verification code.")}
            )

        validate_password(attrs["new_password"], user=user)
        attrs["user"] = user
        return attrs

    def save(self, **kwargs):
        """Set the new password on the resolved user."""
        user = self.validated_data["user"]
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


class LogoutSerializer(serializers.Serializer):
    """Blacklist a refresh token to log the user out.

    Requires ``rest_framework_simplejwt.token_blacklist`` to be installed and in
    ``INSTALLED_APPS`` for the blacklist to actually take effect.
    """

    refresh = serializers.CharField(help_text=_("The refresh token to invalidate."))

    def save(self, **kwargs) -> None:
        """Attempt to blacklist the provided refresh token."""
        try:
            token = RefreshToken(self.validated_data["refresh"])
            token.blacklist()
        except Exception as exc:  # Invalid/expired token, or blacklist app absent.
            raise serializers.ValidationError(
                {"refresh": _("Invalid or expired refresh token.")}
            ) from exc
