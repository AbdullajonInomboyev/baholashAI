from django.contrib import admin
from .models import (QuestionBank, QuestionGroup, Question, QuestionImage,
                     TestBank, TestQuestion, WrittenExam, WrittenExamSubmission, WrittenAnswer)


@admin.register(QuestionBank)
class QuestionBankAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "created_by", "created_at")


@admin.register(TestBank)
class TestBankAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "created_by", "created_at")


admin.site.register(QuestionGroup)
admin.site.register(Question)
admin.site.register(QuestionImage)
admin.site.register(TestQuestion)


admin.site.register(WrittenExam)
admin.site.register(WrittenExamSubmission)
admin.site.register(WrittenAnswer)
