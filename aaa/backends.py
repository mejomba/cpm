"""Authentication backends for the ``aaa`` package.

Django delegates ``authenticate()`` to each backend in
``settings.AUTHENTICATION_BACKENDS``. The default backend only understands the
``USERNAME_FIELD``; ours additionally lets a user log in by **phone number** so
a single login form/endpoint can accept either identifier.
"""

from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

from .validators import looks_like_email, normalize_phone

User = get_user_model()


class EmailOrPhoneBackend(ModelBackend):
    """Authenticate using an email address *or* a phone number plus password.

    The ``username`` argument passed by :func:`django.contrib.auth.authenticate`
    is treated as a generic *identifier*: if it looks like an email we match the
    ``email`` column, otherwise we match the normalised ``phone_number`` column.
    """

    def authenticate(
        self,
        request,
        username: Optional[str] = None,
        password: Optional[str] = None,
        **kwargs,
    ):
        """Return the matching, password-valid user or ``None``.

        Args:
            request: The current request (may be ``None``).
            username: The identifier typed by the user (email or phone). We also
                accept it under the ``identifier`` keyword for clarity.
            password: The raw password to verify.

        Returns:
            The authenticated ``User`` instance, or ``None`` if authentication
            fails for any reason.
        """
        # Allow callers to pass the identifier as ``identifier=...`` too.
        identifier = username or kwargs.get("identifier")
        if identifier is None or password is None:
            return None

        # Build a query targeting the right column based on the identifier shape.
        if looks_like_email(identifier):
            query = Q(email__iexact=identifier.strip())
        else:
            query = Q(phone_number=normalize_phone(identifier))

        try:
            user = User.objects.get(query)
        except User.DoesNotExist:
            # Run the default password hasher once even when the user is missing
            # to mitigate timing attacks that probe for valid accounts.
            User().set_password(password)
            return None
        except User.MultipleObjectsReturned:  # pragma: no cover - defensive
            # Shouldn't happen given the unique constraints, but be safe.
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
