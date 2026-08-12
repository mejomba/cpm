"""Django admin integration for the ``aaa`` models."""

from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import SocialAccount, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin configuration tailored to the email/phone-based user model.

    We subclass Django's :class:`~django.contrib.auth.admin.UserAdmin` to reuse
    its password-change handling, but redefine the fieldsets/list config because
    our model has no ``username`` field.
    """

    # Columns shown in the change list.
    list_display = (
        "email",
        "phone_number",
        "full_name",
        "is_verified",
        "is_active",
        "is_staff",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "is_verified")
    search_fields = ("email", "phone_number", "first_name", "last_name")
    ordering = ("-date_joined",)
    readonly_fields = ("uid", "date_joined", "last_login")

    # Layout of the change form.
    fieldsets = (
        (None, {"fields": ("uid", "email", "phone_number", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name")}),
        (
            _("Verification"),
            {"fields": ("is_email_verified", "is_phone_verified", "is_verified")},
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

    # Layout of the "add user" form (uses Django's wide CSS class).
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "phone_number",
                    "password1",
                    "password2",
                ),
            },
        ),
    )


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    """Read-mostly admin view of linked third-party accounts."""

    list_display = ("user", "provider", "provider_user_id", "date_connected")
    list_filter = ("provider",)
    search_fields = ("user__email", "user__phone_number", "provider_user_id")
    readonly_fields = ("date_connected",)
