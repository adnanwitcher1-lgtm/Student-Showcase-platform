"""
Social login (Google + GitHub) ke helpers.

Flow:
1. Frontend button -> /accounts/<provider>/login/?next=/api/auth/social/complete/
2. Provider (Google/GitHub) par login -> allauth user bana/dhoond leta hai
3. social_complete: allauth session se JWT banata hai aur frontend /auth/callback par bhej deta hai
"""
from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpResponseRedirect
from django.views.decorators.cache import never_cache
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken


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
