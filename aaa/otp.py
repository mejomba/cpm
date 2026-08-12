"""One-Time-Password (OTP) generation, storage, delivery and verification.

OTPs are short numeric codes sent to a phone or email to prove the user controls
that identifier. They are stored in Django's cache framework (so they expire
automatically) keyed by the destination identifier and a *purpose* (e.g.
``"register"`` vs ``"login"`` vs ``"reset"``).

Delivery is pluggable: the dotted path in ``AAA["OTP_SENDER"]`` is called with
``(destination, code, channel)``. The default implementation simply logs the
code which is convenient in development. Production deployments must point this
at a real SMS/email gateway.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from typing import Optional

from django.core.cache import caches

from .conf import app_settings
from .validators import looks_like_email, normalize_phone

logger = logging.getLogger("aaa.otp")


def default_otp_sender(destination: str, code: str, channel: str) -> None:
    """Fallback OTP "sender" that just logs the code.

    Args:
        destination: The email address or phone number to deliver to.
        code: The freshly generated OTP code.
        channel: Either ``"email"`` or ``"sms"``.

    .. warning::
        This default never actually delivers anything to the user. Override
        ``AAA["OTP_SENDER"]`` with a function that sends a real SMS/email.
    """
    logger.warning(
        "OTP for %s via %s is: %s (override AAA['OTP_SENDER'] in production)",
        destination,
        channel,
        code,
    )


@dataclass
class OTPRecord:
    """The data persisted in the cache for a single outstanding OTP."""

    code: str          # The expected code.
    attempts: int      # How many wrong guesses have been made so far.


class OTPService:
    """Create, deliver and verify OTP codes.

    The service is intentionally stateless aside from the shared cache, so it is
    safe to instantiate freely (or use the module-level :data:`otp_service`).
    """

    def __init__(self) -> None:
        # Resolve the configured cache lazily on each access so test overrides of
        # ``CACHES``/``AAA`` are respected.
        pass

    @property
    def _cache(self):
        """Return the configured cache backend instance."""
        return caches[app_settings.OTP_CACHE_ALIAS]

    @staticmethod
    def _normalize_destination(destination: str) -> str:
        """Canonicalise the destination so generate/verify keys always match."""
        if looks_like_email(destination):
            return destination.strip().lower()
        return normalize_phone(destination)

    @staticmethod
    def _channel_for(destination: str) -> str:
        """Return ``"email"`` or ``"sms"`` based on the destination shape."""
        return "email" if looks_like_email(destination) else "sms"

    def _cache_key(self, destination: str, purpose: str) -> str:
        """Build the namespaced cache key for a destination + purpose pair."""
        return f"aaa:otp:{purpose}:{self._normalize_destination(destination)}"

    def generate_code(self) -> str:
        """Return a cryptographically-secure numeric OTP code.

        Uses :func:`secrets.randbelow` so codes are not predictable. The length
        is controlled by ``AAA["OTP_LENGTH"]``.
        """
        length = app_settings.OTP_LENGTH
        upper_bound = 10 ** length
        # Zero-pad so codes always have exactly ``length`` digits.
        return str(secrets.randbelow(upper_bound)).zfill(length)

    def send(self, destination: str, purpose: str = "login") -> str:
        """Generate, store and deliver an OTP for ``destination``.

        Args:
            destination: Email or phone number to send the code to.
            purpose: A short string scoping the code to a flow (e.g.
                ``"register"``, ``"login"``, ``"reset"``). Codes for different
                purposes are stored independently.

        Returns:
            The generated code. (Returned mainly so callers/tests can assert on
            it; the value is never exposed through the API.)
        """
        code = self.generate_code()
        record = OTPRecord(code=code, attempts=0)
        self._cache.set(
            self._cache_key(destination, purpose),
            record.__dict__,
            timeout=app_settings.OTP_TTL_SECONDS,
        )

        # Deliver via the configured (possibly overridden) sender callable.
        sender = app_settings.OTP_SENDER
        sender(destination, code, self._channel_for(destination))
        return code

    def verify(self, destination: str, code: str, purpose: str = "login") -> bool:
        """Check ``code`` against the stored OTP for ``destination``.

        On success the code is consumed (deleted) so it cannot be reused. On
        failure the attempt counter is incremented and, once
        ``AAA["OTP_MAX_ATTEMPTS"]`` is exceeded, the code is invalidated to
        thwart brute-force guessing.

        Args:
            destination: Email or phone number the code was sent to.
            code: The code supplied by the user.
            purpose: Must match the purpose used in :meth:`send`.

        Returns:
            ``True`` if the code is valid and now consumed, else ``False``.
        """
        key = self._cache_key(destination, purpose)
        stored: Optional[dict] = self._cache.get(key)
        if not stored:
            # No outstanding code (never sent or already expired/consumed).
            return False

        record = OTPRecord(**stored)

        if secrets.compare_digest(record.code, str(code)):
            # Correct code: consume it so it is single-use.
            self._cache.delete(key)
            return True

        # Wrong code: count the attempt and possibly burn the code.
        record.attempts += 1
        if record.attempts >= app_settings.OTP_MAX_ATTEMPTS:
            self._cache.delete(key)
        else:
            # Preserve the original TTL where the backend supports it; falling
            # back to resetting the TTL is acceptable for this purpose.
            self._cache.set(key, record.__dict__, timeout=app_settings.OTP_TTL_SECONDS)
        return False


# Module-level singleton for convenient importing.
otp_service = OTPService()
