import django_filters
from .models import Project


class ProjectFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(field_name='category__slug', lookup_expr='iexact')
    tech_stack = django_filters.CharFilter(field_name='tech_stack__slug', lookup_expr='iexact')
    batch = django_filters.CharFilter(field_name='owner__batch', lookup_expr='iexact')
    status = django_filters.CharFilter(field_name='status', lookup_expr='iexact')
    featured = django_filters.BooleanFilter(field_name='is_featured')
    has_video = django_filters.BooleanFilter(method='filter_has_video')

    def filter_has_video(self, queryset, name, value):
        if value:
            return queryset.exclude(demo_video='').exclude(demo_video__isnull=True)
        return queryset

    class Meta:
        model = Project
        fields = ['category', 'tech_stack', 'batch', 'status', 'featured', 'has_video']
