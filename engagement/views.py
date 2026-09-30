from django.shortcuts import render

# Create your views here.
from datetime import timedelta
from django.utils import timezone
from django.db.models.functions import TruncWeek
from django.db.models import Count
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions

from projects.models import Project, ProjectView
from projects.permissions import IsInstructorOrAdmin
from users.models import User


class DashboardStatsView(APIView):
    permission_classes = [IsInstructorOrAdmin]

    def get(self, request):
        total_projects = Project.objects.count()
        total_students = User.objects.filter(role='student').count()

        top_liked = list(
            Project.objects.order_by('-likes_count')[:5]
            .values('title', 'slug', 'likes_count')
        )

        eight_weeks_ago = timezone.now() - timedelta(weeks=8)
        weekly_views = (
            ProjectView.objects.filter(viewed_at__gte=eight_weeks_ago)
            .annotate(week=TruncWeek('viewed_at'))
            .values('week')
            .annotate(count=Count('id'))
            .order_by('week')
        )
        weekly_views_trend = [
            {"week": entry['week'].strftime('%Y-%m-%d'), "views": entry['count']}
            for entry in weekly_views
        ]

        return Response({
            "total_projects": total_projects,
            "total_students": total_students,
            "top_liked_projects": top_liked,
            "weekly_views_trend": weekly_views_trend,
        })