"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from users.views import RegisterView, RateLimitedTokenObtainPairView
from users.views import RegisterView
from engagement.views import DashboardStatsView
from projects.views import SentryTestView
from users.views import ProfileView
from rest_framework.routers import DefaultRouter
from projects.views import (
    ProjectViewSet, ProjectScreenshotUploadView,
    CommentListCreateView, CommentDeleteView,
    ProjectGitHubMetaView, ProjectDemoUrlView,
    ProjectSourcePreviewView,
)
from projects.views import ProjectViewSet, ProjectScreenshotUploadView, CommentListCreateView, CommentDeleteView

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')
from projects.views import (
    ProjectViewSet, ProjectScreenshotUploadView,
    CommentListCreateView, CommentDeleteView, ProjectGitHubMetaView,
)
from projects.views import (
    ProjectViewSet, ProjectScreenshotUploadView,
    CommentListCreateView, CommentDeleteView,
    ProjectGitHubMetaView, ProjectDemoUrlView,
)
from projects.views import (
    ProjectViewSet, ProjectScreenshotUploadView,
    CommentListCreateView, CommentDeleteView,
    ProjectGitHubMetaView, ProjectDemoUrlView,
    ProjectSourcePreviewView, StaticSiteUploadView, StaticSiteStatusView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/register/', RegisterView.as_view()),
    path('api/auth/login/', TokenObtainPairView.as_view()),
    path('api/auth/refresh/', TokenRefreshView.as_view()),
    path('accounts/', include('allauth.urls')),
    path('api/users/me/', ProfileView.as_view()),
    path('api/', include(router.urls)),
    path('api/projects/<slug:slug>/screenshots/', ProjectScreenshotUploadView.as_view()),
    path('api/projects/<slug:slug>/comment/', CommentListCreateView.as_view()),
    path('api/projects/<slug:slug>/comments/<int:comment_id>/', CommentDeleteView.as_view()),
    path('api/projects/<slug:slug>/github-meta/', ProjectGitHubMetaView.as_view()),
    path('api/projects/<slug:slug>/demo-url/', ProjectDemoUrlView.as_view()),
    path('api/projects/<slug:slug>/source-preview/', ProjectSourcePreviewView.as_view()),
    path('api/projects/<slug:slug>/static-site/', StaticSiteUploadView.as_view()),
    path('api/projects/<slug:slug>/static-site-url/', StaticSiteStatusView.as_view()),
    path('api/dashboard/stats/', DashboardStatsView.as_view()),
    path('api/auth/login/', RateLimitedTokenObtainPairView.as_view()),
    path('api/sentry-test/', SentryTestView.as_view()),
    path('', include('django_prometheus.urls')),
]