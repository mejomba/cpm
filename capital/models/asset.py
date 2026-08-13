from django.conf import settings
from django.db import models
from core.models import BaseModel

from core.utils import Utils


class AssetType(BaseModel):
    """
    Bank Account
    Crypto
    Stock
    and ...
    """
    title = models.CharField(max_length=250, unique=True)
    symbol = models.CharField(max_length=16)
    thumbnail = models.ImageField(upload_to=Utils.generic_image_path, null=True, blank=True)
    description = models.TextField(max_length=400, null=True, blank=True)


class Asset(BaseModel):
    """
    BTC_USD
    BTC_IRR
    FOLAD
    and ...
    """
    FEE_STRATEGY_CHOICE = (("1", "only_percent"), 
                           ("2", "only_fixed_value"),
                           ("3", "buy_percent__sell_fixed"), 
                           ("4", "buy_fixed__sell_percent"),
                           ("5", "percent_to_max_fixed"))
    title = models.CharField(max_length=250, unique=True)
    symbol = models.CharField(max_length=16)
    thumbnail = models.ImageField(upload_to=Utils.generic_image_path, null=True, blank=True)
    description = models.TextField(max_length=400, null=True, blank=True)
    today_price = models.DecimalField(max_digits=settings.MAX_DIGITS, decimal_places=settings.DECIMAL_PLACES)
    asset_type = models.ForeignKey(AssetType, on_delete=models.DO_NOTHING)
    max_decimal_point = models.PositiveSmallIntegerField(default=settings.DECIMAL_PLACES)

    fee_sell = models.DecimalField(max_digits=settings.MAX_DIGITS, decimal_places=settings.DECIMAL_PLACES, default=0.0, help_text="درصد کارمزد فروش")
    fee_buy = models.DecimalField(max_digits=settings.MAX_DIGITS, decimal_places=settings.DECIMAL_PLACES, default=0.0, help_text="درصد کارمزد خرید")
    fee_sell_fixed_value = models.DecimalField(max_digits=settings.MAX_DIGITS, decimal_places=settings.DECIMAL_PLACES, default=0.0, help_text="مقدار ثابت کارمزد فروش")
    fee_buy_fixed_value = models.DecimalField(max_digits=settings.MAX_DIGITS, decimal_places=settings.DECIMAL_PLACES, default=0.0, help_text="مقدار ثابت کارمزد خرید")
    fee_strategy = models.CharField(max_length=32, choices=FEE_STRATEGY_CHOICE, null=True, blank=True)
