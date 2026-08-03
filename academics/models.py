from django.conf import settings
from django.db import models
from django.utils import timezone


class StudyForm(models.TextChoices):
    FULL_TIME = "kunduzgi", "Kunduzgi"
    EVENING = "kechki", "Kechki"
    DISTANCE = "masofaviy", "Masofaviy"


class Faculty(models.Model):
    name = models.CharField("Nomi", max_length=255)
    dean = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deaned_faculties",
        verbose_name="Zam dekan",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Fakultet"
        verbose_name_plural = "Fakultetlar"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Department(models.Model):
    faculty = models.ForeignKey(
        Faculty, on_delete=models.CASCADE, related_name="departments", verbose_name="Fakultet"
    )
    name = models.CharField("Nomi", max_length=255)
    head = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="headed_departments",
        verbose_name="Kafedra mudiri",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Kafedra"
        verbose_name_plural = "Kafedralar"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Direction(models.Model):
    faculty = models.ForeignKey(
        Faculty, on_delete=models.CASCADE, related_name="directions", verbose_name="Fakultet"
    )
    department = models.ForeignKey(
        "academics.Department", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="directions", verbose_name="Mas‘ul kafedra"
    )
    code = models.CharField("Kod", max_length=50, unique=True)
    name = models.CharField("Nomi", max_length=255)

    class Meta:
        verbose_name = "Yo‘nalish"
        verbose_name_plural = "Yo‘nalishlar"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} — {self.name}"


class AcademicYear(models.Model):
    faculty = models.ForeignKey(
        Faculty, on_delete=models.CASCADE, related_name="academic_years", verbose_name="Fakultet"
    )
    title = models.CharField("O‘quv yili", max_length=20)  # 2025-2026
    is_active = models.BooleanField("Faol", default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "O‘quv yili"
        verbose_name_plural = "O‘quv yillari"
        ordering = ["-title"]
        constraints = [
            models.UniqueConstraint(fields=["faculty", "title"], name="uniq_year_per_faculty")
        ]

    def __str__(self):
        return self.title


class ExcelImport(models.Model):
    class Status(models.TextChoices):
        PROCESSING = "processing", "Jarayonda"
        SUCCESS = "success", "Muvaffaqiyatli"
        FAILED = "failed", "Xato"

    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name="imports", verbose_name="O‘quv yili"
    )
    file = models.FileField("Fayl", upload_to="oquv_reja/")
    study_form = models.CharField("Ta‘lim shakli", max_length=20, choices=StudyForm.choices)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="excel_imports",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROCESSING)
    log = models.TextField("Import jurnali", blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Excel import"
        verbose_name_plural = "Excel importlar"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.academic_year} · {self.get_study_form_display()}"


class Semester(models.Model):
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name="semesters"
    )
    number = models.PositiveSmallIntegerField("Semestr")

    class Meta:
        verbose_name = "Semestr"
        verbose_name_plural = "Semestrlar"
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(fields=["academic_year", "number"], name="uniq_semester")
        ]

    def __str__(self):
        return f"{self.number}-semestr"


class Curriculum(models.Model):
    """O‘quv reja = yo‘nalish × o‘quv yili × ta‘lim shakli.
    Bir yo‘nalish har o‘quv yilida alohida rejaga ega bo‘ladi."""

    direction = models.ForeignKey(
        Direction, on_delete=models.CASCADE, related_name="curricula", verbose_name="Yo‘nalish"
    )
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name="curricula", verbose_name="O‘quv yili"
    )
    study_form = models.CharField("Ta‘lim shakli", max_length=20, choices=StudyForm.choices)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "O‘quv reja"
        verbose_name_plural = "O‘quv rejalar"
        ordering = ["academic_year", "direction", "study_form"]
        constraints = [
            models.UniqueConstraint(
                fields=["direction", "academic_year", "study_form"], name="uniq_curriculum"
            )
        ]

    def __str__(self):
        return f"{self.direction.code} · {self.academic_year.title} · {self.get_study_form_display()}"


class Course(models.Model):
    curriculum = models.ForeignKey(
        Curriculum, on_delete=models.CASCADE, related_name="courses", verbose_name="O‘quv reja"
    )
    code = models.CharField("Fan kodi", max_length=50)
    name = models.CharField("Fan nomi", max_length=255)
    is_elective = models.BooleanField("Tanlov fani", default=False)

    total_hours = models.PositiveIntegerField("Umumiy soat", null=True, blank=True)
    lecture_hours = models.PositiveIntegerField("Ma‘ruza", null=True, blank=True)
    practice_hours = models.PositiveIntegerField("Amaliy", null=True, blank=True)
    lab_hours = models.PositiveIntegerField("Laboratoriya", null=True, blank=True)
    seminar_hours = models.PositiveIntegerField("Seminar", null=True, blank=True)
    course_project_hours = models.PositiveIntegerField("Kurs loyihasi/ishi", null=True, blank=True)
    independent_hours = models.PositiveIntegerField("Mustaqil ta‘lim", null=True, blank=True)

    credit = models.DecimalField("Kredit", max_digits=5, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Fan"
        verbose_name_plural = "Fanlar"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["curriculum", "code"], name="uniq_course_per_curriculum")
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"

    # Shablon va kod moslashuvi uchun qulay xossalar
    @property
    def direction(self):
        return self.curriculum.direction

    @property
    def academic_year(self):
        return self.curriculum.academic_year

    @property
    def study_form(self):
        return self.curriculum.study_form

    def get_study_form_display(self):
        return self.curriculum.get_study_form_display()

    def save(self, *args, **kwargs):
        if self.credit is None and self.total_hours:
            per = settings.ACADEMIC_HOURS_PER_CREDIT
            self.credit = round(self.total_hours / per, 2)
        super().save(*args, **kwargs)


class CourseSemester(models.Model):
    """Fan qaysi semestrda o‘qitiladi + o‘sha semestrdagi kredit va haftalik soat."""

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="placements")
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name="placements")
    credits = models.DecimalField("Kredit", max_digits=5, decimal_places=2, null=True, blank=True)
    weekly_hours = models.PositiveSmallIntegerField("Haftalik soat", null=True, blank=True)

    class Meta:
        verbose_name = "Fan-semestr"
        verbose_name_plural = "Fan-semestr taqsimoti"
        constraints = [
            models.UniqueConstraint(fields=["course", "semester"], name="uniq_course_semester")
        ]

    def __str__(self):
        return f"{self.course.code} · {self.semester}"


class SyllabusTopic(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="topics")
    order = models.PositiveSmallIntegerField("Tartib")
    title = models.CharField("Mavzu", max_length=500)
    description = models.TextField("Izoh", blank=True)

    class Meta:
        verbose_name = "Fan dasturi mavzusi"
        verbose_name_plural = "Fan dasturi mavzulari"
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(fields=["course", "order"], name="uniq_topic_order")
        ]

    def __str__(self):
        return f"{self.order}. {self.title}"


class StudentEnrollment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "O‘qimoqda"
        EXPELLED = "expelled", "Chetlashtirilgan"
        GRADUATED = "graduated", "Bitirgan"
        ACADEMIC_LEAVE = "academic_leave", "Akademik ta‘til"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enrollments"
    )
    direction = models.ForeignKey(Direction, on_delete=models.PROTECT, related_name="enrollments")
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name="enrollments"
    )
    study_form = models.CharField("Ta‘lim shakli", max_length=20, choices=StudyForm.choices)
    group_name = models.CharField("Guruh", max_length=50)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Talaba biriktiruvi"
        verbose_name_plural = "Talaba biriktiruvlari"
        constraints = [
            models.UniqueConstraint(
                fields=["student", "academic_year"], name="uniq_enrollment_per_year"
            )
        ]

    def __str__(self):
        return f"{self.student} · {self.group_name}"
