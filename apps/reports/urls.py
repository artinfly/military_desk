from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.ReportListView.as_view(), name="list"),
    path("filter/", views.FilterReportView.as_view(), name="filter"),
    path("<slug:slug>/", views.ReportDownloadView.as_view(), name="download"),
]
