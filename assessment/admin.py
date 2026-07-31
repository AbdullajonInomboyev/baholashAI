from django.contrib import admin

from .models import (
    AIEvaluation, AIModel, AIModuleConfig, Assignment, AssignmentCriterion, AssignmentType,
    Submission, TeacherReview,
)


@admin.register(AIModel)
class AIModelAdmin(admin.ModelAdmin):
    list_display = ("name", "provider", "model_identifier", "is_active")
    list_filter = ("provider", "is_active")


@admin.register(AIModuleConfig)
class AIModuleConfigAdmin(admin.ModelAdmin):
    list_display = ("assignment_type", "ai_model")


class CriterionInline(admin.TabularInline):
    model = AssignmentCriterion
    extra = 0


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    inlines = [CriterionInline]
    list_display = ("title", "assignment_type", "status", "due_date")
    list_filter = ("status", "assignment_type")


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("student", "assignment", "status", "created_at")
    list_filter = ("status",)


admin.site.register(AssignmentType)
admin.site.register(AIEvaluation)
admin.site.register(TeacherReview)


from .models import Choice, Question, Quiz, QuizAttempt  # noqa: E402


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 0


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    show_change_link = True


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ("title", "teacher_assignment", "is_open", "created_at")
    list_filter = ("is_open",)
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("text", "quiz", "kind", "points")
    list_filter = ("kind",)
    inlines = [ChoiceInline]


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ("quiz", "student", "score", "submitted_at")
