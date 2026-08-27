from django.conf import settings
from django.db import models
from django.utils import timezone


class QuestionBank(models.Model):
    """Yozma ish savollar banki."""
    title = models.CharField("Nomi", max_length=200)
    course = models.ForeignKey("academics.Course", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="question_banks", verbose_name="Fan")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   related_name="question_banks")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Savollar banki"
        verbose_name_plural = "Savollar banklari"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def question_count(self):
        return Question.objects.filter(group__bank=self).count()


class QuestionGroup(models.Model):
    bank = models.ForeignKey(QuestionBank, on_delete=models.CASCADE, related_name="groups")
    name = models.CharField("Guruh nomi", max_length=255)
    order = models.PositiveIntegerField("Tartib", default=0)
    pick_count = models.PositiveIntegerField("Nechta tanlanadi", default=1)

    class Meta:
        verbose_name = "Savollar guruhi"
        verbose_name_plural = "Savollar guruhlari"
        ordering = ["order"]

    def __str__(self):
        return f"{self.bank.title} — {self.name}"


class Question(models.Model):
    class Difficulty(models.TextChoices):
        EASY = "easy", "Oson"
        MEDIUM = "medium", "O‘rta"
        HARD = "hard", "Qiyin"

    group = models.ForeignKey(QuestionGroup, on_delete=models.CASCADE, related_name="questions")
    content_html = models.TextField("HTML matn", blank=True)
    raw_text = models.TextField("Oddiy matn", blank=True)
    formula_omml = models.TextField("Formula (OMML)", blank=True)
    formula_mathml = models.TextField("Formula (MathML)", blank=True)
    image_data = models.TextField("Rasm (data URL)", blank=True)
    raw_content_json = models.JSONField("Bloklar (JSON)", default=dict, blank=True)
    difficulty = models.CharField("Qiyinlik", max_length=10, choices=Difficulty.choices,
                                  default=Difficulty.MEDIUM)
    accessible = models.BooleanField("Moslashuvchan", default=True)
    allowed_answer_types = models.JSONField("Javob turlari", default=list, blank=True)
    image = models.ImageField("Rasm", upload_to="questions/", null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Savol (bank)"
        verbose_name_plural = "Savollar (bank)"

    def __str__(self):
        return (self.raw_text or "Savol")[:50]


class QuestionImage(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField("Rasm", upload_to="questions/")

    def __str__(self):
        return f"Rasm #{self.pk}"


class TestBank(models.Model):
    """Test savollari banki."""
    title = models.CharField("Nomi", max_length=200)
    course = models.ForeignKey("academics.Course", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="test_banks", verbose_name="Fan")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   related_name="test_banks")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Test banki"
        verbose_name_plural = "Test banklari"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def question_count(self):
        return self.questions.count()


class TestQuestion(models.Model):
    bank = models.ForeignKey(TestBank, on_delete=models.CASCADE, related_name="questions")
    question_html = models.TextField("Savol (HTML)", blank=True)
    raw_text = models.TextField("Savol matni", blank=True)
    formula_omml = models.TextField("Formula (OMML)", blank=True)
    formula_mathml = models.TextField("Formula (MathML)", blank=True)
    image_data = models.TextField("Rasm (data URL)", blank=True)
    raw_content_json = models.JSONField("Bloklar (JSON)", default=dict, blank=True)
    correct_answer = models.CharField("To‘g‘ri javob", max_length=500, blank=True)
    option1 = models.CharField("Muqobil 1", max_length=500, blank=True)
    option2 = models.CharField("Muqobil 2", max_length=500, blank=True)
    option3 = models.CharField("Muqobil 3", max_length=500, blank=True)
    correct_img = models.TextField("To‘g‘ri javob rasmi (data URL)", blank=True)
    option1_img = models.TextField("Muqobil 1 rasmi", blank=True)
    option2_img = models.TextField("Muqobil 2 rasmi", blank=True)
    option3_img = models.TextField("Muqobil 3 rasmi", blank=True)
    accessible = models.BooleanField("Moslashuvchan", default=True)
    image = models.ImageField("Rasm", upload_to="test_questions/", null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Test savoli (bank)"
        verbose_name_plural = "Test savollari (bank)"

    def __str__(self):
        return (self.raw_text or "Test savoli")[:50]


class WrittenExam(models.Model):
    """Yozma savollar bankidan tuzilgan imtihon."""
    bank = models.ForeignKey(QuestionBank, on_delete=models.CASCADE, related_name="exams")
    teacher_assignment = models.ForeignKey(
        "teaching.TeacherAssignment", on_delete=models.CASCADE, related_name="written_exams")
    title = models.CharField("Nomi", max_length=200)
    is_open = models.BooleanField("Ochiq", default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   related_name="written_exams")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Yozma imtihon"
        verbose_name_plural = "Yozma imtihonlar"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def question_count(self):
        return Question.objects.filter(group__bank=self.bank).count()


class WrittenExamSubmission(models.Model):
    exam = models.ForeignKey(WrittenExam, on_delete=models.CASCADE, related_name="submissions")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="written_submissions")
    submitted_at = models.DateTimeField(default=timezone.now)
    total_score = models.DecimalField("Umumiy ball", max_digits=6, decimal_places=2, null=True, blank=True)
    reviewed = models.BooleanField("Baholangan", default=False)

    class Meta:
        verbose_name = "Yozma imtihon topshirig‘i"
        verbose_name_plural = "Yozma imtihon topshiriqlari"
        unique_together = [("exam", "student")]
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.student} — {self.exam}"


class WrittenAnswer(models.Model):
    submission = models.ForeignKey(WrittenExamSubmission, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="written_answers")
    answer_text = models.TextField("Javob", blank=True)
    score = models.DecimalField("Ball", max_digits=5, decimal_places=2, null=True, blank=True)
    feedback = models.CharField("Izoh", max_length=500, blank=True)

    class Meta:
        verbose_name = "Yozma javob"
        verbose_name_plural = "Yozma javoblar"

    def __str__(self):
        return f"Javob #{self.pk}"
