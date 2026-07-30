from django.conf import settings
from django.db import models
from django.utils import timezone

from academics.models import AcademicYear, Course, Department, Faculty, StudyForm
from teaching.models import Resource


class ReportExport(models.Model):
    """Zam dekan yuklab olgan hisobotlar tarixi (fakultet yoki kafedra kesimida)."""

    class Scope(models.TextChoices):
        FACULTY = "faculty", "Fakultet"
        DEPARTMENT = "department", "Kafedra"

    class Format(models.TextChoices):
        XLSX = "xlsx", "Excel"
        PDF = "pdf", "PDF"

    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="report_exports"
    )
    scope = models.CharField("Qamrov", max_length=20, choices=Scope.choices)
    faculty = models.ForeignKey(Faculty, on_delete=models.SET_NULL, null=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.SET_NULL, null=True, blank=True)
    file = models.FileField("Fayl", upload_to="reports/", null=True, blank=True)
    file_format = models.CharField(max_length=10, choices=Format.choices, default=Format.XLSX)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Hisobot"
        verbose_name_plural = "Hisobotlar"
        ordering = ["-created_at"]

    def __str__(self):
        target = self.department or self.faculty
        return f"{self.get_scope_display()}: {target}"


class ReviewRemark(models.Model):
    """Zam dekan → kafedra mudiri "buni to‘g‘irla" izohi.
    Konkret resurs/fan/kafedraga ishora qilishi mumkin, holati kuzatiladi."""

    class Status(models.TextChoices):
        OPEN = "open", "Ochiq"
        RESOLVED = "resolved", "Hal qilingan"

    report = models.ForeignKey(
        ReportExport, on_delete=models.SET_NULL, null=True, blank=True, related_name="remarks"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="authored_remarks",
        verbose_name="Zam dekan",
    )
    target = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="received_remarks",
        verbose_name="Kafedra mudiri",
    )
    department = models.ForeignKey(Department, on_delete=models.CASCADE, null=True, blank=True)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True)
    resource = models.ForeignKey(Resource, on_delete=models.SET_NULL, null=True, blank=True)
    message = models.TextField("Izoh")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "To‘g‘irlash izohi"
        verbose_name_plural = "To‘g‘irlash izohlari"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.author} → {self.target}: {self.message[:40]}"


class AuditLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="audit_entries"
    )
    action = models.CharField(max_length=100)   # create, update, delete, grade_change ...
    entity = models.CharField(max_length=100)   # model nomi
    entity_id = models.CharField(max_length=64)
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Audit yozuvi"
        verbose_name_plural = "Audit jurnali"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["entity", "entity_id"])]

    def __str__(self):
        return f"{self.user} · {self.action} · {self.entity}#{self.entity_id}"
