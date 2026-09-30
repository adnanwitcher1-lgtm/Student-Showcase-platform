from django.http import JsonResponse
from django.conf import settings


class DemoOriginValidationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.endswith('/demo-url/'):
            origin = request.headers.get('Origin') or request.headers.get('Referer')
            if origin:
                origin = origin.rstrip('/')
                allowed = any(origin.startswith(o) for o in settings.DEMO_ALLOWED_ORIGINS)
                if not allowed:
                    return JsonResponse(
                        {"detail": "Forbidden: invalid origin."},
                        status=403,
                    )
        return self.get_response(request)