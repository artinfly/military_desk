from django.urls import path

from . import views

app_name = "personnel"

urlpatterns = [
    path("", views.PersonListView.as_view(), name="list"),
]
