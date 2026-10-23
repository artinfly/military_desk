"""Все справочники в админке — по реестру, с одинаковыми настройками."""

from django.contrib import admin

from .registry import REFERENCES


class ReferenceAdmin(admin.ModelAdmin):
    list_filter = ("is_active",)
    search_fields = ("name", "code")
    list_per_page = 50

    def get_list_display(self, request):
        ref = next(r for r in REFERENCES if r.model is self.model)
        return (*ref.list_fields, "code", "sort_order", "is_active")


for _ref in REFERENCES:
    admin.site.register(_ref.model, ReferenceAdmin)
