from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import StudentProfile, User, UserRole


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


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "student_id", "pinfl", "gender", "course", "group_name", "gpa")
    search_fields = ("user__full_name", "user__username", "student_id", "pinfl", "passport_number")
    list_filter = ("gender", "education_type", "payment_form", "is_graduating")
