from django.contrib import admin

from capital.models.asset import Asset, AssetType
from capital.models.user_asset import UserAsset
from capital.models.asset_transaction import Transaction, TransactionType

admin.site.register([Asset, AssetType, UserAsset, Transaction, TransactionType])
