"""Персональные данные не должны сохраняться в HTTP-кешах."""

from django.utils.cache import patch_cache_control


class PrivatePagesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if getattr(request, "user", None) is not None and request.user.is_authenticated:
            patch_cache_control(response, private=True, no_store=True)
        return response
