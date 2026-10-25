from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("filter/", views.FilterReportView.as_view(), name="filter"),
]
