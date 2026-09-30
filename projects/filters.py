import django_filters
from .models import Project


class ProjectFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(field_name='category__slug', lookup_expr='iexact')
    tech_stack = django_filters.CharFilter(field_name='tech_stack__slug', lookup_expr='iexact')
    batch = django_filters.CharFilter(field_name='owner__batch', lookup_expr='iexact')
    status = django_filters.CharFilter(field_name='status', lookup_expr='iexact')

    class Meta:
        model = Project
        fields = ['category', 'tech_stack', 'batch', 'status']