from django.contrib import admin

from .models import (
    AIEvaluation, AIModel, AIModuleConfig, Assignment, AssignmentType,
    Submission, TeacherReview,
)


@admin.register(AIModel)
class AIModelAdmin(admin.ModelAdmin):
    list_display = ("name", "provider", "model_identifier", "is_active")
    list_filter = ("provider", "is_active")


@admin.register(AIModuleConfig)
class AIModuleConfigAdmin(admin.ModelAdmin):
    list_display = ("assignment_type", "ai_model")


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("title", "assignment_type", "status", "due_date")
    list_filter = ("status", "assignment_type")


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("student", "assignment", "status", "created_at")
    list_filter = ("status",)


admin.site.register(AssignmentType)
admin.site.register(AIEvaluation)
admin.site.register(TeacherReview)
