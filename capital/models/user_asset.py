from django.conf import settings
from django.db import models

from .asset import Asset
from core.models import BaseModelWithUser


class UserAsset(BaseModelWithUser):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING)
    asset = models.ForeignKey(Asset, on_delete=models.DO_NOTHING)
    quantity = models.DecimalField(max_digits=settings.MAX_DIGITS, decimal_places=settings.DECIMAL_PLACES)
    price_sar_be_sar = models.DecimalField(max_digits=settings.MAX_DIGITS, decimal_places=settings.DECIMAL_PLACES)
    price_buy = models.DecimalField(max_digits=settings.MAX_DIGITS, decimal_places=settings.DECIMAL_PLACES)
    description = models.TextField(max_length=400, null=True, blank=True)