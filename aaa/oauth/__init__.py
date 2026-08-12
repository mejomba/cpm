"""Social / OAuth2 authentication for the ``aaa`` package.

This sub-package implements "Login with Google / GitHub / ..." on top of the
local :class:`~aaa.models.User` model. The design is provider-agnostic:

* :class:`~aaa.oauth.base.OAuthProvider` defines the contract every provider
  implements (build an authorization URL, exchange a code for a token, fetch the
  user's normalised profile).
* Concrete providers live alongside it (:mod:`aaa.oauth.google`,
  :mod:`aaa.oauth.github`).
* :func:`~aaa.oauth.base.get_provider` resolves a provider slug
  (``"google"``) to an instance using the ``AAA["OAUTH_PROVIDERS"]`` registry.

Add your own provider by subclassing ``OAuthProvider`` and registering its
dotted path in ``AAA["OAUTH_PROVIDERS"]``.
"""

from .base import OAuthProvider, OAuthUserInfo, get_provider

__all__ = ["OAuthProvider", "OAuthUserInfo", "get_provider"]
