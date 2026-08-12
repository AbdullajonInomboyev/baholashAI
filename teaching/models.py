from django.conf import settings
from django.db import models
from django.utils import timezone

from academics.models import Course, Department


class DepartmentCourse(models.Model):
    """Zam dekan istalgan fanni istalgan kafedraga biriktiradi
    (fan boshqa fakultetga tegishli bo‘lsa ham)."""

    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="course_links", verbose_name="Kafedra"
    )
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="department_links", verbose_name="Fan"
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="department_course_assignments"
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Kafedra fani"
        verbose_name_plural = "Kafedra fanlari"
        constraints = [
            models.UniqueConstraint(fields=["department", "course"], name="uniq_department_course")
        ]

    def __str__(self):
        return f"{self.department} · {self.course.code}"


class TeacherAssignment(models.Model):
    """Kafedra mudiri bitta fanga bir nechta o‘qituvchi biriktirishi mumkin."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Faol"
        REMOVED = "removed", "Olib tashlangan"

    department_course = models.ForeignKey(
        DepartmentCourse, on_delete=models.CASCADE, related_name="teacher_assignments"
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="teaching_assignments",
        verbose_name="O‘qituvchi",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="given_teaching_assignments"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "O‘qituvchi biriktiruvi"
        verbose_name_plural = "O‘qituvchi biriktiruvlari"
        constraints = [
            models.UniqueConstraint(
                fields=["department_course", "teacher"], name="uniq_teacher_per_course"
            )
        ]

    def __str__(self):
        return f"{self.teacher} · {self.department_course.course.code}"


class Resource(models.Model):
    class Kind(models.TextChoices):
        SYLLABUS = "syllabus", "Fan dasturi"
        LECTURE = "lecture", "Ma‘ruza"
        PRACTICE = "practice", "Amaliy material"
        LAB = "lab", "Laboratoriya"
        INDEPENDENT = "independent", "Mustaqil ta‘lim"
        PRESENTATION = "presentation", "Taqdimot"
        VIDEO = "video", "Video"
        TEST = "test", "Test"
        CONTROL_Q = "control_q", "Nazorat savollari"
        LITERATURE = "literature", "Adabiyot"
        OTHER = "other", "Boshqa"

    class Format(models.TextChoices):
        FILE = "file", "Fayl"
        URL = "url", "Havola (URL)"
        PAGE = "page", "Matnli sahifa"
        VIDEO = "video", "Video"

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="resources",
        verbose_name="Yuklagan o‘qituvchi",
    )
    title = models.CharField("Sarlavha", max_length=255)
    resource_format = models.CharField("Ko‘rinishi", max_length=10, choices=Format.choices,
                                       default=Format.FILE)
    file = models.FileField("Fayl", upload_to="resources/", null=True, blank=True)
    url = models.URLField("Havola", blank=True)
    content = models.TextField("Matn (sahifa uchun)", blank=True)
    transcript = models.TextField("Matnli izoh / subtitr (eshitish imkoniyati cheklanganlar uchun)", blank=True)
    kind = models.CharField("Turi", max_length=20, choices=Kind.choices, default=Kind.OTHER)
    created_at = models.DateTimeField(default=timezone.now)

    class ApprovalStatus(models.TextChoices):
        PENDING = "pending", "Kutilmoqda"
        APPROVED = "approved", "Tasdiqlangan"
        REJECTED = "rejected", "Rad etilgan"

    approval_status = models.CharField(
        "Tasdiq holati", max_length=12, choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING
    )
    review_note = models.TextField("Izoh / rad sababi", blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reviewed_resources"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class DeptStatus(models.TextChoices):
        DRAFT = "draft", "Qoralama"
        NEW = "new", "Tekshiruvda"
        APPROVED = "dept_approved", "Kafedra tasdiqladi"
        RETURNED = "returned", "Tuzatishga qaytarilgan"
        FORWARDED = "forwarded", "Zamdekanga yuborilgan"
        ARCHIVED = "archived", "Arxiv"

    dept_status = models.CharField(
        "Kafedra holati", max_length=15, choices=DeptStatus.choices, default=DeptStatus.DRAFT)
    dept_note = models.TextField("Kafedra izohi", blank=True)

    class Meta:
        verbose_name = "Resurs"
        verbose_name_plural = "Resurslar"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class ResourceLink(models.Model):
    """Bitta resurs bir nechta fanga (o‘qituvchi biriktiruviga) ulanishi mumkin."""

    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name="links")
    teacher_assignment = models.ForeignKey(
        TeacherAssignment, on_delete=models.CASCADE, related_name="resource_links"
    )
    topic = models.ForeignKey(
        "academics.SyllabusTopic", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="resource_links", verbose_name="Mavzu"
    )

    class Meta:
        verbose_name = "Resurs biriktiruvi"
        verbose_name_plural = "Resurs biriktiruvlari"
        constraints = [
            models.UniqueConstraint(
                fields=["resource", "teacher_assignment"], name="uniq_resource_link"
            )
        ]

    def __str__(self):
        return f"{self.resource} → {self.teacher_assignment.department_course.course.code}"


class ResourceReview(models.Model):
    """Resurs yuklanishi bilan AI tekshiruvi avtomatik shakllanadi.
    Kafedra mudiri natijani ko‘radi: mavzuga moslik va to‘liqlik."""

    class Status(models.TextChoices):
        PENDING = "pending", "Navbatda"
        PROCESSING = "processing", "Tahlil qilinmoqda"
        COMPLETED = "completed", "Yakunlangan"
        FAILED = "failed", "Xato"

    resource = models.OneToOneField(Resource, on_delete=models.CASCADE, related_name="review")
    ai_model = models.ForeignKey(
        "assessment.AIModel", on_delete=models.SET_NULL, null=True, blank=True, related_name="resource_reviews"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    match_score = models.DecimalField(
        "Mavzuga moslik (%)", max_digits=5, decimal_places=2, null=True, blank=True
    )
    completeness_score = models.DecimalField(
        "To‘liqlik (%)", max_digits=5, decimal_places=2, null=True, blank=True
    )
    feedback = models.TextField("AI xulosasi", blank=True)
    reviewed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Resurs AI tahlili"
        verbose_name_plural = "Resurs AI tahlillari"

    def __str__(self):
        return f"{self.resource} · {self.get_status_display()}"
