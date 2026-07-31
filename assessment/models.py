from django.conf import settings
from django.db import models
from django.utils import timezone

from teaching.models import TeacherAssignment


class AssignmentType(models.Model):
    name = models.CharField("Nomi", max_length=100, unique=True)  # Test, Yozma ish, Amaliy ...

    class Meta:
        verbose_name = "Topshiriq turi"
        verbose_name_plural = "Topshiriq turlari"

    def __str__(self):
        return self.name


class AIModel(models.Model):
    class Provider(models.TextChoices):
        OPENAI = "openai", "OpenAI"
        GOOGLE = "google", "Google"
        ANTHROPIC = "anthropic", "Anthropic"

    name = models.CharField("Nomi", max_length=100)
    provider = models.CharField("Provayder", max_length=20, choices=Provider.choices)
    model_identifier = models.CharField("Model ID", max_length=100)
    is_active = models.BooleanField("Faol", default=True)

    class Meta:
        verbose_name = "AI model"
        verbose_name_plural = "AI modellar"
        ordering = ["provider", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_provider_display()})"


class AIModuleConfig(models.Model):
    """Dinamik AI: qaysi topshiriq turida qaysi model ishlatilishi.
    Model ID ni almashtirsang, kod o‘zgarmasdan butun tizim yangi AI ga o‘tadi."""

    assignment_type = models.OneToOneField(
        AssignmentType, on_delete=models.CASCADE, related_name="ai_config", verbose_name="Topshiriq turi"
    )
    ai_model = models.ForeignKey(
        AIModel, on_delete=models.PROTECT, related_name="module_configs", verbose_name="AI model"
    )

    class Meta:
        verbose_name = "AI modul sozlamasi"
        verbose_name_plural = "AI modul sozlamalari"

    def __str__(self):
        return f"{self.assignment_type} → {self.ai_model}"


class Assignment(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Qoralama"
        OPEN = "open", "Ochiq"
        CLOSED = "closed", "Yopilgan"

    teacher_assignment = models.ForeignKey(
        TeacherAssignment, on_delete=models.CASCADE, related_name="assignments"
    )
    assignment_type = models.ForeignKey(
        AssignmentType, on_delete=models.PROTECT, related_name="assignments", verbose_name="Turi"
    )
    title = models.CharField("Sarlavha", max_length=255)
    description = models.TextField("Tavsif", blank=True)
    due_date = models.DateField("Muddat", null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Topshiriq"
        verbose_name_plural = "Topshiriqlar"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Submission(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Topshirilgan"
        AI_EVALUATED = "ai_evaluated", "AI baholadi"
        TEACHER_REVIEWED = "teacher_reviewed", "O‘qituvchi tasdiqladi"

    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="submissions")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="submissions"
    )
    file = models.FileField("Fayl", upload_to="submissions/", null=True, blank=True)
    text_answer = models.TextField("Onlayn matn javob", blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Topshirilgan ish"
        verbose_name_plural = "Topshirilgan ishlar"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["assignment", "student"], name="uniq_submission")
        ]

    def __str__(self):
        return f"{self.student} · {self.assignment}"


class AIEvaluation(models.Model):
    submission = models.OneToOneField(
        Submission, on_delete=models.CASCADE, related_name="ai_evaluation"
    )
    ai_model = models.ForeignKey(AIModel, on_delete=models.SET_NULL, null=True, related_name="evaluations")
    score = models.DecimalField("AI bahosi", max_digits=5, decimal_places=2, null=True, blank=True)
    feedback = models.TextField("AI izohi", blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "AI baho"
        verbose_name_plural = "AI baholar"

    def __str__(self):
        return f"{self.submission} · {self.score}"


class TeacherReview(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Tasdiqlangan"
        MODIFIED = "modified", "O‘zgartirilgan"

    submission = models.OneToOneField(
        Submission, on_delete=models.CASCADE, related_name="teacher_review"
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reviews"
    )
    final_score = models.DecimalField("Yakuniy baho", max_digits=5, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CONFIRMED)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "O‘qituvchi tasdig‘i"
        verbose_name_plural = "O‘qituvchi tasdiqlari"

    def __str__(self):
        return f"{self.submission} · {self.final_score}"
