"""Custom manager for the :class:`~aaa.models.User` model.

Because our ``User`` is keyed on *email or phone* rather than ``username``, the
default :class:`django.contrib.auth.models.UserManager` (which insists on a
``username``) cannot be used. This module provides a drop-in replacement whose
``create_user``/``create_superuser`` accept ``email`` and/or ``phone_number``.
"""

from __future__ import annotations

from typing import Optional

from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _

from .validators import normalize_phone


class UserManager(BaseUserManager):
    """Manager that creates users identified by an email and/or phone number."""

    # Tells Django the manager is usable inside migrations.
    use_in_migrations = True

    def _create_user(
        self,
        email: Optional[str] = None,
        phone_number: Optional[str] = None,
        password: Optional[str] = None,
        **extra_fields,
    ):
        """Create and persist a ``User``.

        At least one of ``email`` or ``phone_number`` must be supplied; this is
        the core invariant of the whole authentication system.

        Args:
            email: The user's email address (optional if a phone is given).
            phone_number: The user's phone number (optional if an email given).
            password: Raw password; hashed via ``set_password``. May be ``None``
                for passwordless (OTP/social) accounts.
            **extra_fields: Any other model fields (e.g. ``is_staff``).

        Returns:
            The newly created and saved ``User`` instance.

        Raises:
            ValueError: If neither an email nor a phone number is provided.
        """
        if not email and not phone_number:
            raise ValueError(
                _("Users must have either an email address or a phone number.")
            )

        # Normalise both identifiers so lookups are consistent.
        if email:
            email = self.normalize_email(email).lower()
        if phone_number:
            phone_number = normalize_phone(phone_number)

        user = self.model(
            email=email or None,
            phone_number=phone_number or None,
            **extra_fields,
        )

        # ``set_password`` hashes the password; ``set_unusable_password`` marks
        # the account as having no usable password (social/OTP-only login).
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_user(
        self,
        email: Optional[str] = None,
        phone_number: Optional[str] = None,
        password: Optional[str] = None,
        **extra_fields,
    ):
        """Create a regular (non-staff, non-superuser) account.

        Mirrors Django's contract by defaulting ``is_staff`` and
        ``is_superuser`` to ``False``.
        """
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, phone_number, password, **extra_fields)

    def create_superuser(
        self,
        email: Optional[str] = None,
        phone_number: Optional[str] = None,
        password: Optional[str] = None,
        **extra_fields,
    ):
        """Create an admin account with all permissions.

        Enforces ``is_staff=True`` and ``is_superuser=True`` and validates that
        the caller did not try to override them with falsy values (matching the
        behaviour of Django's built-in manager).
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        # Superusers are considered verified/active out of the box.
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_verified", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))

        return self._create_user(email, phone_number, password, **extra_fields)

    # -- Convenience lookup helpers -----------------------------------------
    def get_by_email(self, email: str):
        """Fetch a user by (normalised) email; raises ``DoesNotExist`` if none."""
        return self.get(email=self.normalize_email(email).lower())

    def get_by_phone(self, phone_number: str):
        """Fetch a user by (normalised) phone; raises ``DoesNotExist`` if none."""
        return self.get(phone_number=normalize_phone(phone_number))
