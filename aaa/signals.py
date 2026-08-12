"""Signal handlers for the ``aaa`` package.

Currently this module is a placeholder that exists so :meth:`AaaConfig.ready`
has something to import. Add ``@receiver``-decorated handlers here (e.g. to send
a welcome email on ``post_save`` of a new user) and they will be registered
automatically when the app loads.
"""

from __future__ import annotations

# Example pattern (left commented as documentation):
#
# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from .models import User
#
# @receiver(post_save, sender=User)
# def on_user_created(sender, instance, created, **kwargs):
#     if created:
#         ...  # e.g. enqueue a welcome notification
