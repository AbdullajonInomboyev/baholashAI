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
    password_status = models.CharField(
        "Parol holati",
        max_length=20,
        choices=PasswordStatus.choices,
        default=PasswordStatus.TEMPORARY,
    )

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
