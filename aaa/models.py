"""Database models for the ``aaa`` authentication package.

The central model is :class:`User`, a custom user that authenticates with an
**email address or a phone number** instead of a username. A companion
:class:`SocialAccount` model links third-party (Google/GitHub/...) identities to
local users.
"""

from __future__ import annotations

import uuid
from typing import Optional

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .managers import UserManager
from .validators import normalize_phone, validate_phone


class User(AbstractBaseUser, PermissionsMixin):
    """A user identified by a unique email address and/or phone number.

    Inherits:
        * ``AbstractBaseUser`` for the password & last-login machinery.
        * ``PermissionsMixin`` for the ``is_superuser``/groups/permissions API
          so the model is fully compatible with Django admin and the standard
          permission framework.

    Identity rules:
        * ``email`` and ``phone_number`` are both **optional but unique**.
        * The manager enforces that at least one of them is present.
        * ``USERNAME_FIELD`` is ``email`` (Django requires a single field), but
          the bundled authentication backend lets users log in with *either*
          identifier — see :mod:`aaa.backends`.
    """

    # A stable, non-sequential public identifier. Useful for exposing the user
    # in URLs/APIs without leaking the auto-increment primary key.
    uid = models.UUIDField(
        _("public id"),
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text=_("Stable public identifier safe to expose in APIs."),
    )

    email = models.EmailField(
        _("email address"),
        unique=True,
        null=True,
        blank=True,
        help_text=_("Unique email address. Optional if a phone number is set."),
    )

    phone_number = models.CharField(
        _("phone number"),
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        validators=[validate_phone],
        help_text=_(
            "Unique phone number in international format. Optional if an email "
            "is set."
        ),
    )

    # Basic profile fields. Kept minimal on purpose; extend via a related
    # profile model in your own project if you need more.
    first_name = models.CharField(_("first name"), max_length=150, blank=True)
    last_name = models.CharField(_("last name"), max_length=150, blank=True)

    # -- Verification flags --------------------------------------------------
    is_email_verified = models.BooleanField(
        _("email verified"),
        default=False,
        help_text=_("Designates whether the email address has been verified."),
    )
    is_phone_verified = models.BooleanField(
        _("phone verified"),
        default=False,
        help_text=_("Designates whether the phone number has been verified."),
    )
    is_verified = models.BooleanField(
        _("verified"),
        default=False,
        help_text=_(
            "Designates whether the account has completed verification "
            "(at least one identifier confirmed)."
        ),
    )

    # -- Standard Django user flags -----------------------------------------
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_(
            "Designates whether this user should be treated as active. "
            "Unselect this instead of deleting accounts."
        ),
    )
    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Designates whether the user can log into the admin site."),
    )

    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)

    # Wire up the custom manager defined in :mod:`aaa.managers`.
    objects = UserManager()

    # Django requires a single username field. We use ``email`` here, but note
    # the auth backend additionally supports logging in by phone number.
    USERNAME_FIELD = "email"
    # No extra required fields at ``createsuperuser`` time; the manager handles
    # the "email or phone" rule itself.
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        # Helpful indexes for the two identifier lookups performed at login.
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["phone_number"]),
        ]

    def __str__(self) -> str:
        """Human-readable representation: prefer email, else phone, else uid."""
        return self.email or self.phone_number or str(self.uid)

    def clean(self) -> None:
        """Normalise identifiers before validation/save."""
        super().clean()
        if self.email:
            self.email = self.email.lower().strip()
        if self.phone_number:
            self.phone_number = normalize_phone(self.phone_number)

    def save(self, *args, **kwargs):
        """Persist the user, keeping the aggregate ``is_verified`` flag fresh."""
        # ``is_verified`` is a convenience roll-up: it becomes True as soon as
        # any identifier is verified (or it was explicitly set, e.g. for
        # superusers), and is never silently downgraded here.
        self.is_verified = bool(
            self.is_verified or self.is_email_verified or self.is_phone_verified
        )
        super().save(*args, **kwargs)

    # -- Convenience helpers -------------------------------------------------
    @property
    def full_name(self) -> str:
        """Return the user's full name, trimmed."""
        return f"{self.first_name} {self.last_name}".strip()

    def get_full_name(self) -> str:
        """Django-compatible alias for :attr:`full_name`."""
        return self.full_name

    def get_short_name(self) -> str:
        """Return the user's short name (first name)."""
        return self.first_name

    @property
    def primary_identifier(self) -> Optional[str]:
        """Return the email if present, otherwise the phone number."""
        return self.email or self.phone_number


class SocialAccount(models.Model):
    """A third-party identity (Google, GitHub, ...) linked to a local user.

    A single local :class:`User` may have several social accounts (e.g. both a
    Google and a GitHub login). The pair ``(provider, provider_user_id)`` is
    unique so the same external identity cannot be linked twice.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="social_accounts",
        help_text=_("The local user this external identity belongs to."),
    )

    # Short slug identifying the provider, e.g. ``"google"`` or ``"github"``.
    provider = models.CharField(_("provider"), max_length=40)

    # The user's unique id *as reported by the provider* (the ``sub`` claim for
    # Google, the numeric account id for GitHub, etc.).
    provider_user_id = models.CharField(_("provider user id"), max_length=255)

    # Raw profile payload returned by the provider, kept for debugging/auditing.
    extra_data = models.JSONField(_("extra data"), default=dict, blank=True)

    date_connected = models.DateTimeField(_("date connected"), default=timezone.now)

    class Meta:
        verbose_name = _("social account")
        verbose_name_plural = _("social accounts")
        # The same external identity may not be linked more than once.
        unique_together = ("provider", "provider_user_id")

    def __str__(self) -> str:
        return f"{self.provider}:{self.provider_user_id} -> {self.user}"
