from django.urls import path

from . import views

app_name = "references"

urlpatterns = [
    path("", views.CatalogView.as_view(), name="catalog"),
    path("<slug:slug>/", views.ReferenceListView.as_view(), name="list"),
    path("<slug:slug>/add/", views.ReferenceFormView.as_view(), name="add"),
    path("<slug:slug>/<int:pk>/", views.ReferenceFormView.as_view(), name="edit"),
]
