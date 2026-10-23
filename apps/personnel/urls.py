from django.urls import path

from . import views

app_name = "personnel"

urlpatterns = [
    path("", views.PersonListView.as_view(), name="list"),
    path("add/", views.PersonFormView.as_view(), name="add"),
    path("<int:pk>/", views.PersonDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.PersonFormView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.PersonDeleteView.as_view(), name="delete"),
    # Разделы карточки (?tab=<slug>): добавить, изменить, удалить запись;
    # одиночный раздел (воинский учёт) правится по адресу <slug>/edit/
    path(
        "<int:pk>/<slug:slug>/add/", views.SectionFormView.as_view(), name="section_add"
    ),
    path(
        "<int:pk>/<slug:slug>/edit/",
        views.SectionFormView.as_view(),
        name="section_single",
    ),
    path(
        "<int:pk>/<slug:slug>/<int:item>/",
        views.SectionFormView.as_view(),
        name="section_edit",
    ),
    path(
        "<int:pk>/<slug:slug>/<int:item>/delete/",
        views.SectionDeleteView.as_view(),
        name="section_delete",
    ),
]
