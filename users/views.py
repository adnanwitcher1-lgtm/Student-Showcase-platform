from django.shortcuts import render
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import generics, permissions

from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import RegisterSerializer, ProfileSerializer


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]  # file upload ke liye

    def get_object(self):
        return self.request.user


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer


# JWT Login Rate Limiting (5 attempts per minute per IP)
@method_decorator(
    ratelimit(key='ip', rate='5/m', method='POST', block=True),
    name='post'
)
class RateLimitedTokenObtainPairView(TokenObtainPairView):
    pass