from django.urls import path

from . import certificates, views

app_name = "reports"

urlpatterns = [
    path("", views.ReportListView.as_view(), name="list"),
    path("filter/", views.FilterReportView.as_view(), name="filter"),
    path("certificates/", certificates.CertificatesView.as_view(), name="certificates"),
    path(
        "certificates/template/",
        certificates.CertificateTemplateView.as_view(),
        name="certificate_template",
    ),
    path(
        "certificates/<int:pk>/",
        certificates.CertificatesView.as_view(),
        name="certificate",
    ),
    path("<slug:slug>/", views.ReportDownloadView.as_view(), name="download"),
]
