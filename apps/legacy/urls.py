from django.urls import path

from .views import CodesView, ExchangeView, SprView

app_name = "legacy"
urlpatterns = [
    path("", ExchangeView.as_view(), name="exchange"),
    path("spr/", SprView.as_view(), name="spr"),
    path("codes/", CodesView.as_view(), name="codes"),
]
