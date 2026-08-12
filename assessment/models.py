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


# ============ Test / savol banki ============

class Quiz(models.Model):
    teacher_assignment = models.ForeignKey(
        "teaching.TeacherAssignment", on_delete=models.CASCADE, related_name="quizzes",
        verbose_name="Fan biriktiruvi"
    )
    title = models.CharField("Test nomi", max_length=200)
    description = models.TextField("Tavsif", blank=True)
    time_limit_minutes = models.PositiveIntegerField("Vaqt chegarasi (daqiqa)", null=True, blank=True)
    is_open = models.BooleanField("Ochiq", default=True)
    deadline = models.DateField("Muddat", null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Test"
        verbose_name_plural = "Testlar"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def question_count(self):
        return self.questions.count()

    @property
    def total_points(self):
        return sum(q.points for q in self.questions.all()) or 0


class Question(models.Model):
    class Kind(models.TextChoices):
        SINGLE = "single", "Bitta to‘g‘ri javob"
        MULTIPLE = "multiple", "Bir nechta to‘g‘ri javob"
        TRUE_FALSE = "true_false", "To‘g‘ri/Noto‘g‘ri"
        SHORT = "short", "Qisqa matnli javob"

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField("Savol matni")
    kind = models.CharField("Turi", max_length=20, choices=Kind.choices, default=Kind.SINGLE)
    points = models.PositiveIntegerField("Ball", default=1)
    correct_text = models.CharField("To‘g‘ri javob (qisqa matn)", max_length=255, blank=True)
    formula_mathml = models.TextField("Formula (MathML)", blank=True)
    order = models.PositiveIntegerField("Tartib", default=0)

    class Meta:
        verbose_name = "Savol"
        verbose_name_plural = "Savollar"
        ordering = ["order", "id"]

    def __str__(self):
        return self.text[:60]


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField("Variant", max_length=255)
    is_correct = models.BooleanField("To‘g‘ri", default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Variant"
        verbose_name_plural = "Variantlar"
        ordering = ["order", "id"]

    def __str__(self):
        return self.text[:40]


class QuizAttempt(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="attempts")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quiz_attempts"
    )
    score = models.DecimalField("Ball (%)", max_digits=5, decimal_places=2, null=True, blank=True)
    submitted_at = models.DateTimeField("Topshirilgan", null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Test urinishi"
        verbose_name_plural = "Test urinishlari"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["quiz", "student"], name="uniq_quiz_attempt")
        ]

    def __str__(self):
        return f"{self.student} · {self.quiz} · {self.score}"


class QuizAnswer(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected = models.ManyToManyField(Choice, blank=True)
    text_answer = models.CharField(max_length=255, blank=True)
    is_correct = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["attempt", "question"], name="uniq_quiz_answer")
        ]


# ============ Rubrika (baholash mezonlari) ============

class AssignmentCriterion(models.Model):
    assignment = models.ForeignKey(
        Assignment, on_delete=models.CASCADE, related_name="criteria", verbose_name="Topshiriq"
    )
    title = models.CharField("Mezon", max_length=200)
    max_points = models.PositiveIntegerField("Maksimal ball", default=10)
    order = models.PositiveIntegerField("Tartib", default=0)

    class Meta:
        verbose_name = "Baholash mezoni"
        verbose_name_plural = "Baholash mezonlari"
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.title} ({self.max_points})"


class CriterionScore(models.Model):
    submission = models.ForeignKey(
        Submission, on_delete=models.CASCADE, related_name="criterion_scores"
    )
    criterion = models.ForeignKey(
        AssignmentCriterion, on_delete=models.CASCADE, related_name="scores"
    )
    ai_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    teacher_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    comment = models.TextField(blank=True)

    class Meta:
        verbose_name = "Mezon bahosi"
        verbose_name_plural = "Mezon baholari"
        constraints = [
            models.UniqueConstraint(fields=["submission", "criterion"], name="uniq_criterion_score")
        ]
