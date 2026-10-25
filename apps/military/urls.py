from django.urls import path

from . import views

app_name = "military"

urlpatterns = [
    path("operations/", views.OperationsView.as_view(), name="operations"),
]
