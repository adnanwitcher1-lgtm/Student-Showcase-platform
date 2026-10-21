from django.contrib import admin

# Register your models here.
from django.contrib.auth.admin import UserAdmin
from .models import User, DesktopClient


class CustomUserAdmin(UserAdmin):
    model = User
    fieldsets = UserAdmin.fieldsets + (
        ('Extra Info', {'fields': ('role', 'avatar', 'bio', 'batch', 'github_username')}),
    )
    list_display = ('username', 'email', 'role', 'is_staff')


admin.site.register(User, CustomUserAdmin)


@admin.register(DesktopClient)
class DesktopClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'client_id', 'is_active', 'created_at')
    readonly_fields = ('client_id', 'created_at')
    list_filter = ('is_active',)
