from django.contrib import admin

from .models import (
    DepartmentCourse, Resource, ResourceLink, ResourceReview, TeacherAssignment,
)


@admin.register(DepartmentCourse)
class DepartmentCourseAdmin(admin.ModelAdmin):
    list_display = ("department", "course", "assigned_by", "created_at")
    list_filter = ("department",)


@admin.register(TeacherAssignment)
class TeacherAssignmentAdmin(admin.ModelAdmin):
    list_display = ("teacher", "department_course", "status", "created_at")
    list_filter = ("status",)


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "uploaded_by", "created_at")
    list_filter = ("kind",)


@admin.register(ResourceReview)
class ResourceReviewAdmin(admin.ModelAdmin):
    list_display = ("resource", "status", "match_score", "completeness_score", "ai_model")
    list_filter = ("status",)


admin.site.register(ResourceLink)
