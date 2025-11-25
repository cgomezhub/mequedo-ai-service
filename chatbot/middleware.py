# chatbot/middleware.py
from django.http import HttpResponsePermanentRedirect
from django.conf import settings


class HealthCheckMiddleware:
    """
    Permite que /api/health/ funcione sin HTTPS redirect.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Si es el health check, no hacer redirect
        if request.path == '/':
            return self.get_response(request)

        # Para todas las demás rutas, aplicar HTTPS redirect si está configurado
        if not request.is_secure() and settings.SECURE_SSL_REDIRECT:
            url = request.build_absolute_uri(request.get_full_path())
            secure_url = url.replace('http://', 'https://')
            return HttpResponsePermanentRedirect(secure_url)

        return self.get_response(request)
