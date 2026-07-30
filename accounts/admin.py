from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, UserRole


class UserRoleInline(admin.TabularInline):
    model = UserRole
    fk_name = "user"
    extra = 0
    autocomplete_fields = ["faculty", "department"]


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [UserRoleInline]
    list_display = ("username", "full_name", "email", "password_status", "is_active")
    list_filter = ("password_status", "is_active", "roles__role")
    search_fields = ("username", "full_name", "email")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Qo‘shimcha", {"fields": ("full_name", "phone", "password_status")}),
    )


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "faculty", "department")
    list_filter = ("role",)
    autocomplete_fields = ["user", "faculty", "department"]
