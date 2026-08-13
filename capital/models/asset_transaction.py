from core.models import BaseModelWithUser, BaseModel
from .user_asset import UserAsset

from django.conf import settings
from django.db import models


class TransactionType(BaseModel):
    title = models.CharField(max_length=250)
    title_en = models.CharField(max_length=250)
    description = models.TextField(max_length=400, null=True, blank=True)
    

class Transaction(BaseModelWithUser):
    transaction_type = models.ForeignKey(TransactionType, on_delete=models.DO_NOTHING)
    user_asset = models.ForeignKey(UserAsset, on_delete=models.DO_NOTHING)
    price = models.DecimalField(max_digits=settings.MAX_DIGITS, decimal_places=settings.DECIMAL_PLACES, help_text="قیمت تراکنش")
    fee = models.DecimalField(max_digits=settings.MAX_DIGITS, decimal_places=settings.DECIMAL_PLACES, help_text="کارمزد تراکنس")
    quantity = models.DecimalField(max_digits=settings.MAX_DIGITS, decimal_places=settings.DECIMAL_PLACES, help_text="تعداد دارایی معامله شده")
    description = models.TextField(max_length=400, null=True, blank=True)

    @property
    def total_fee(self):
        raise

    @property
    def total_price(self):
        raise
    
    