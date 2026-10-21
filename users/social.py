"""
Social login (Google + GitHub) ke helpers.

Flow:
1. Frontend button -> /accounts/<provider>/login/?next=/api/auth/social/complete/
2. Provider (Google/GitHub) par login -> allauth user bana/dhoond leta hai
3. social_complete: allauth session se JWT banata hai aur frontend /auth/callback par bhej deta hai

Desktop app ka flow (Google embedded window mein login nahi karne deta, isliye system browser use hota hai):
1. Desktop app browser kholti hai: /accounts/<provider>/login/?next=/api/auth/social/desktop-complete/?challenge=<sha256(verifier)>
2. Login ke baad social_desktop_complete ek one-time code banata hai aur studentshowcase://auth?code=... se app ko wapas kholta hai
3. App code + verifier + X-Client-ID bhej kar /api/auth/social/desktop-exchange/ se device-bound token leti hai
"""
import base64
import hashlib
import re
import secrets
from html import escape

from django.conf import settings
from django.contrib.auth import get_user_model, logout
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django_ratelimit.decorators import ratelimit
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .authentication import HEADER, _client_is_active

DESKTOP_SCHEME = 'studentshowcase'
DESKTOP_CODE_TTL = 120  # seconds
_CHALLENGE_RE = re.compile(r'^[A-Za-z0-9_-]{43}$')  # base64url(sha256) = 43 chars


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        # GitHub se naya user bane to uska github_username profile mein bhar do
        if sociallogin.account.provider == 'github':
            login = sociallogin.account.extra_data.get('login', '')
            if login and not user.github_username:
                user.github_username = login
                user.save(update_fields=['github_username'])
        return user


class SocialProvidersView(APIView):
    """Frontend ko batata hai ke kaun se social login buttons dikhane hain."""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        enabled = settings.SOCIALACCOUNT_PROVIDERS
        return Response({
            'github': 'github' in enabled,
            'google': 'google' in enabled,
        })


@never_cache
def social_complete(request):
    """Social login ke baad: session user ke liye JWT bana kar frontend par bhejo."""
    frontend = settings.FRONTEND_URL

    if not request.user.is_authenticated:
        return HttpResponseRedirect(f'{frontend}/login?error=social')

    access = str(RefreshToken.for_user(request.user).access_token)

    # Session ki ab zaroorat nahi, website JWT se chalti hai
    logout(request)

    # Token URL fragment (#) mein jata hai taake server logs mein na aaye
    return HttpResponseRedirect(f'{frontend}/auth/callback#access={access}')


def _challenge_for(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode('ascii', 'ignore')).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')


def _desktop_page(title, message, link=None, status=200):
    """Chhota dark page. Link ho to app kholne ka button aur auto-redirect bhi."""
    button = ''
    refresh = ''
    if link:
        safe = escape(link, quote=True)
        refresh = f'<meta http-equiv="refresh" content="0;url={safe}">'
        button = f'<a class="btn" href="{safe}">Open Student Showcase</a>'
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{refresh}
<title>{escape(title)}</title>
<style>
:root{{color-scheme:dark}}
body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:#0b0f17;color:#e6e9ef;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
main{{max-width:420px;padding:32px;text-align:center}}
h1{{font-size:22px;margin:0 0 8px}} p{{color:#9aa3b2;line-height:1.5;margin:0 0 24px}}
.btn{{display:inline-block;background:#e6e9ef;color:#0b0f17;border-radius:8px;padding:10px 20px;
font-weight:600;text-decoration:none}}
</style></head>
<body><main><h1>{escape(title)}</h1><p>{escape(message)}</p>{button}</main></body></html>"""
    return HttpResponse(html, status=status)


@never_cache
def social_desktop_complete(request):
    """Desktop login ke baad: one-time code banao aur desktop app ko wapas kholo."""
    challenge = request.GET.get('challenge', '')

    if not request.user.is_authenticated or not _CHALLENGE_RE.match(challenge):
        logout(request)
        return _desktop_page(
            'Sign-in failed',
            'Please return to the desktop app and try again.',
            status=400,
        )

    code = secrets.token_urlsafe(32)
    cache.set(
        f'desktop_login:{code}',
        {'user_id': request.user.pk, 'challenge': challenge},
        DESKTOP_CODE_TTL,
    )

    # Session ki ab zaroorat nahi
    logout(request)

    return _desktop_page(
        'Sign-in successful',
        'The Student Showcase desktop app should open automatically. If it does not, select the button below, then you may close this tab.',
        link=f'{DESKTOP_SCHEME}://auth?code={code}',
    )


@method_decorator(ratelimit(key='ip', rate='20/m', method='POST', block=True), name='post')
class DesktopExchangeView(APIView):
    """One-time code + verifier se device-bound JWT do."""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        client_id = request.META.get(HEADER, '').strip()
        if not client_id or not _client_is_active(client_id):
            raise PermissionDenied('This desktop app is not registered or has been disabled.')

        code = str(request.data.get('code', ''))
        verifier = str(request.data.get('verifier', ''))

        key = f'desktop_login:{code}'
        data = cache.get(key)
        cache.delete(key)  # ek hi baar chalta hai, galat verifier par bhi jal jata hai
        if not data:
            raise ValidationError({'detail': 'Login code expired or invalid.'})

        if not secrets.compare_digest(_challenge_for(verifier), data['challenge']):
            raise ValidationError({'detail': 'Login code expired or invalid.'})

        user = get_user_model().objects.filter(pk=data['user_id'], is_active=True).first()
        if user is None:
            raise ValidationError({'detail': 'Login code expired or invalid.'})

        refresh = RefreshToken.for_user(user)
        refresh['client_id'] = client_id
        return Response({'access': str(refresh.access_token), 'refresh': str(refresh)})
