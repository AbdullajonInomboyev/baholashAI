from django.contrib import admin

from .models import AuditLog, ReportExport, ReviewRemark, Notification


@admin.register(ReportExport)
class ReportExportAdmin(admin.ModelAdmin):
    list_display = ("scope", "faculty", "department", "generated_by", "created_at")
    list_filter = ("scope", "file_format")


@admin.register(ReviewRemark)
class ReviewRemarkAdmin(admin.ModelAdmin):
    list_display = ("author", "target", "department", "status", "created_at")
    list_filter = ("status",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "entity", "entity_id")
    list_filter = ("action", "entity")
    search_fields = ("entity_id",)


admin.site.register(Notification)


from .models import Message

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("sender", "recipient", "created_at")
    search_fields = ("body",)
