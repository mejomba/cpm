from django.urls import path

from .views.capital import my_capital_list, datatable_api, capital_detail_api


app_name = "capital"

urlpatterns = [
    path("me", my_capital_list, name="my.capital.list"),
    path("api/my-capital/", datatable_api, name="api.my.capital.list"),
    path("api/my-capital/<int:id>/detail/", capital_detail_api, name="api.my.capital.detail"),
]
