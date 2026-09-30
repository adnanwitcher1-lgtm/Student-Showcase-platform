from django.contrib import admin

# Register your models here.
from django.contrib.auth.admin import UserAdmin
from .models import User


class CustomUserAdmin(UserAdmin):
    model = User
    fieldsets = UserAdmin.fieldsets + (
        ('Extra Info', {'fields': ('role', 'avatar', 'bio', 'batch', 'github_username')}),
    )
    list_display = ('username', 'email', 'role', 'is_staff')


admin.site.register(User, CustomUserAdmin)