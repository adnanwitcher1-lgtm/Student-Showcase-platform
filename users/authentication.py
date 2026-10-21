"""
Device-bound JWT (desktop app ke liye).

- Login: agar request mein X-Client-ID header ho to wo registered + active hona chahiye,
  aur banne wale token mein client_id claim lag jata hai.
- Har API request: token mein client_id claim ho to same X-Client-ID header zaroori hai.
  Chori hua token browser/curl se bina is header ke kaam nahi karta.
- Web ke normal tokens (bina claim) pehle jaise chalte hain.
"""
import secrets

from django.core.cache import cache
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import DesktopClient

HEADER = 'HTTP_X_CLIENT_ID'


def _client_is_active(client_id):
    key = f'desktop_client_active:{client_id}'
    active = cache.get(key)
    if active is None:
        active = DesktopClient.objects.filter(client_id=client_id, is_active=True).exists()
        cache.set(key, active, timeout=60)
    return active


class DeviceAwareTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)

        request = self.context.get('request')
        client_id = request.META.get(HEADER, '').strip() if request else ''
        if not client_id:
            return data  # normal web login

        if not _client_is_active(client_id):
            raise PermissionDenied('This desktop app is not registered or has been disabled.')

        refresh = self.get_token(self.user)
        refresh['client_id'] = client_id
        data['refresh'] = str(refresh)
        data['access'] = str(refresh.access_token)
        return data


class DeviceBoundJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None

        user, token = result
        bound_to = token.get('client_id')
        if bound_to:
            sent = request.META.get(HEADER, '')
            if not sent or not secrets.compare_digest(sent, bound_to) or not _client_is_active(bound_to):
                raise AuthenticationFailed('This session belongs to the desktop app.')

        return user, token
