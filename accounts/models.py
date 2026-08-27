from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    ADMIN = "admin", "Administrator"
    VICE_DEAN = "vice_dean", "Zam dekan"
    DEPT_HEAD = "dept_head", "Kafedra mudiri"
    TEACHER = "teacher", "O‘qituvchi"
    STUDENT = "student", "Talaba"


class PasswordStatus(models.TextChoices):
    TEMPORARY = "temporary", "Vaqtinchalik"
    ACTIVE = "active", "O‘rnatilgan"


class User(AbstractUser):
    full_name = models.CharField("F.I.Sh.", max_length=255, blank=True)
    phone = models.CharField("Telefon", max_length=30, blank=True)
    birth_date = models.DateField("Tug‘ilgan sana", null=True, blank=True)
    position = models.CharField("Lavozim", max_length=120, blank=True)
    academic_degree = models.CharField("Ilmiy daraja", max_length=120, blank=True)
    academic_title = models.CharField("Ilmiy unvon", max_length=120, blank=True)

    class DisabilityType(models.TextChoices):
        NONE = "", "Yo‘q"
        VISION = "vision", "Ko‘rish"
        HEARING = "hearing", "Eshitish"
        MOBILITY = "mobility", "Harakat"
        SPEECH = "speech", "Nutq"
        OTHER = "other", "Boshqa"

    is_disabled = models.BooleanField("Imkoniyati cheklangan", default=False)
    disability_type = models.CharField(
        "Imkoniyat turi", max_length=12, choices=DisabilityType.choices, blank=True)
    tts_enabled = models.BooleanField("Ovozli o‘qish", default=False)
    tts_rate = models.DecimalField("Ovoz tezligi", max_digits=3, decimal_places=2, default=0.95)
    high_contrast = models.BooleanField("Yuqori kontrast", default=False)
    large_font = models.BooleanField("Katta shrift", default=False)
    dyslexia_font = models.BooleanField("Disleksiya shrifti", default=False)
    reduce_motion = models.BooleanField("Harakatni kamaytirish", default=False)
    reading_guide = models.BooleanField("O‘qish yo‘riqchisi", default=False)
    password_status = models.CharField(
        "Parol holati",
        max_length=20,
        choices=PasswordStatus.choices,
        default=PasswordStatus.TEMPORARY,
    )
    is_guest = models.BooleanField("Mehmon (bir martalik test)", default=False)

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"

    def __str__(self):
        return self.full_name or self.get_username()

    @property
    def must_change_password(self):
        return self.password_status == PasswordStatus.TEMPORARY

    def has_role(self, role, *, faculty=None, department=None):
        qs = self.roles.filter(role=role)
        if faculty is not None:
            qs = qs.filter(faculty=faculty)
        if department is not None:
            qs = qs.filter(department=department)
        return qs.exists()

    def role_codes(self):
        return list(self.roles.values_list("role", flat=True).distinct())


class UserRole(models.Model):
    """Bir foydalanuvchi bir nechta rolga ega bo‘lishi mumkin.
    Har bir rol o‘z fakultet/kafedra doirasi (scope) bilan biriktiriladi."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="roles"
    )
    role = models.CharField("Rol", max_length=20, choices=Role.choices)
    faculty = models.ForeignKey(
        "academics.Faculty",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="role_scopes",
    )
    department = models.ForeignKey(
        "academics.Department",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="role_scopes",
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="granted_roles",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Rol biriktirish"
        verbose_name_plural = "Rol biriktirishlar"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role", "faculty", "department"],
                name="uniq_user_role_scope",
            )
        ]

    def __str__(self):
        scope = self.department or self.faculty
        return f"{self.user} — {self.get_role_display()}" + (f" ({scope})" if scope else "")


class StudentProfile(models.Model):
    """Talabaning to‘liq HEMIS ma'lumotlari (pasport/akademik/ijtimoiy)."""

    class Gender(models.TextChoices):
        MALE = "male", "Erkak"
        FEMALE = "female", "Ayol"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="student_profile", verbose_name="Talaba")

    # Identifikatsiya
    student_id = models.CharField("Talaba ID", max_length=32, blank=True, db_index=True)
    pinfl = models.CharField("JSHSHIR (PINFL)", max_length=20, blank=True, db_index=True)
    passport_number = models.CharField("Pasport raqami", max_length=20, blank=True)
    passport_issued = models.DateField("Pasport berilgan sana", null=True, blank=True)
    gender = models.CharField("Jins", max_length=6, choices=Gender.choices, blank=True)

    # Fuqarolik / hudud
    citizenship = models.CharField("Fuqarolik", max_length=120, blank=True)
    country = models.CharField("Davlat", max_length=80, blank=True)
    nationality = models.CharField("Millat", max_length=80, blank=True)
    region = models.CharField("Viloyat", max_length=120, blank=True)
    district = models.CharField("Tuman", max_length=120, blank=True)

    # Akademik
    course = models.CharField("Kurs", max_length=20, blank=True)
    faculty_name = models.CharField("Fakultet", max_length=255, blank=True)
    group_name = models.CharField("Guruh", max_length=50, blank=True)
    education_language = models.CharField("Ta'lim tili", max_length=40, blank=True)
    academic_year = models.CharField("O‘quv yili", max_length=20, blank=True)
    semester = models.CharField("Semestr", max_length=20, blank=True)
    is_graduating = models.BooleanField("Bitiruvchi", default=False)
    specialty_code = models.CharField("Mutaxassislik kodi", max_length=40, blank=True)
    education_type = models.CharField("Ta'lim turi", max_length=40, blank=True)   # Bakalavr/Magistr
    education_form = models.CharField("Ta'lim shakli", max_length=40, blank=True)  # Kunduzgi/Sirtqi

    # Moliya / toifa
    payment_form = models.CharField("To‘lov shakli", max_length=60, blank=True)
    grant_type = models.CharField("Grant turi", max_length=60, blank=True)
    previous_education = models.TextField("Avvalgi ta'lim ma'lumoti", blank=True)
    student_category = models.CharField("Talaba toifasi", max_length=60, blank=True)
    social_category = models.CharField("Ijtimoiy toifa", max_length=60, blank=True)
    cohabitants_count = models.PositiveIntegerField("Birga yashaydiganlar soni", null=True, blank=True)
    cohabitants_category = models.CharField("Birga yashaydiganlar toifasi", max_length=80, blank=True)
    residence_status = models.CharField("Yashash joyi statusi", max_length=80, blank=True)
    residence_geo = models.CharField("Yashash joyi geolokatsiyasi", max_length=120, blank=True)

    # Hujjat / natija
    order_info = models.CharField("Buyruq", max_length=120, blank=True)
    gpa = models.DecimalField("GPA", max_digits=4, decimal_places=2, null=True, blank=True)
    contract_number = models.CharField("Kontrakt №", max_length=60, blank=True)
    contract_type = models.CharField("Shartnoma turi", max_length=80, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Talaba ma'lumoti (HEMIS)"
        verbose_name_plural = "Talaba ma'lumotlari (HEMIS)"

    def __str__(self):
        return f"{self.user.full_name or self.user.username} — {self.student_id or self.pinfl}"
