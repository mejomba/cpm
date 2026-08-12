"""Reusable field validators for email and phone-number normalisation.

Keeping validation/normalisation logic in one place means the model, the
serializers and the authentication backend all agree on what a "valid" phone
number or email looks like.
"""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.utils.translation import gettext_lazy as _

# A deliberately permissive E.164-style matcher: an optional leading ``+``
# followed by 8–15 digits. We do not attempt full per-country validation here;
# integrate a library such as ``phonenumbers`` if you need that.
PHONE_REGEX = re.compile(r"^\+?[1-9]\d{7,14}$")

# Reuse Django's battle-tested email validator for the email half.
validate_email = EmailValidator(message=_("Enter a valid email address."))


def validate_phone(value: str) -> None:
    """Validate that ``value`` looks like an international phone number.

    Args:
        value: The raw phone string to validate.

    Raises:
        ValidationError: If the value does not match :data:`PHONE_REGEX`.
    """
    if not PHONE_REGEX.match(value or ""):
        raise ValidationError(
            _(
                "Enter a valid phone number in international format, e.g. "
                "+14155552671."
            ),
            code="invalid_phone",
        )


def normalize_phone(value: str) -> str:
    """Normalise a phone number to a canonical comparable form.

    Strips spaces, dashes and parentheses so that ``"+1 (415) 555-2671"`` and
    ``"+14155552671"`` are treated as the same number.

    Args:
        value: The raw phone string.

    Returns:
        The cleaned phone string (unchanged if ``value`` is falsy).
    """
    if not value:
        return value
    return re.sub(r"[\s\-()]", "", value.strip())


def looks_like_email(value: str) -> bool:
    """Return ``True`` if ``value`` is syntactically an email address.

    Used to decide, given a single "identifier" field at login time, whether the
    user typed an email or a phone number.
    """
    try:
        validate_email(value)
    except ValidationError:
        return False
    return True
