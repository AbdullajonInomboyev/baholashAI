from django.db import models
from django.utils import timezone


class Building(models.Model):
    name = models.CharField("Bino nomi", max_length=120)
    address = models.CharField("Manzil", max_length=255, blank=True)
    is_active = models.BooleanField("Faol", default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Bino"
        verbose_name_plural = "Binolar"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def room_count(self):
        return self.rooms.count()


class Room(models.Model):
    class Kind(models.TextChoices):
        LECTURE = "lecture", "Ma‘ruza xonasi"
        PRACTICE = "practice", "Amaliy xona"
        LAB = "lab", "Laboratoriya"
        COMPUTER = "computer", "Kompyuter sinfi"
        OTHER = "other", "Boshqa"

    building = models.ForeignKey(
        Building, on_delete=models.CASCADE, related_name="rooms", verbose_name="Bino"
    )
    name = models.CharField("Xona raqami/nomi", max_length=60)
    kind = models.CharField("Turi", max_length=20, choices=Kind.choices, default=Kind.LECTURE)
    capacity = models.PositiveIntegerField("Sig‘imi", default=30)
    floor = models.IntegerField("Qavat", default=1)
    is_active = models.BooleanField("Faol", default=True)

    class Meta:
        verbose_name = "Auditoriya"
        verbose_name_plural = "Auditoriyalar"
        ordering = ["building__name", "floor", "name"]
        constraints = [
            models.UniqueConstraint(fields=["building", "name"], name="uniq_room_per_building")
        ]

    def __str__(self):
        return f"{self.building.name} · {self.name}"


class TimeSlot(models.Model):
    """Juft (para) — tartib va vaqt oralig'i."""
    order = models.PositiveSmallIntegerField("Juft raqami", unique=True)
    start_time = models.TimeField("Boshlanishi")
    end_time = models.TimeField("Tugashi")
    is_active = models.BooleanField("Faol", default=True)

    class Meta:
        verbose_name = "Juft (vaqt)"
        verbose_name_plural = "Juftlar (vaqtlar)"
        ordering = ["order"]

    def __str__(self):
        return f"{self.order}-juft ({self.start_time:%H:%M}-{self.end_time:%H:%M})"


class Lesson(models.Model):
    class WeekDay(models.IntegerChoices):
        MON = 1, "Dushanba"
        TUE = 2, "Seshanba"
        WED = 3, "Chorshanba"
        THU = 4, "Payshanba"
        FRI = 5, "Juma"
        SAT = 6, "Shanba"

    class WeekType(models.TextChoices):
        ALL = "all", "Har hafta"
        ODD = "odd", "Toq hafta"
        EVEN = "even", "Juft hafta"

    class Kind(models.TextChoices):
        LECTURE = "lecture", "Ma‘ruza"
        PRACTICE = "practice", "Amaliy"
        LAB = "lab", "Laboratoriya"
        SEMINAR = "seminar", "Seminar"

    academic_year = models.ForeignKey(
        "academics.AcademicYear", on_delete=models.CASCADE, related_name="lessons",
        verbose_name="O‘quv yili")
    course = models.ForeignKey(
        "academics.Course", on_delete=models.CASCADE, related_name="lessons", verbose_name="Fan")
    teacher = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="lessons", verbose_name="O‘qituvchi")
    groups = models.ManyToManyField(
        "academics.AcademicGroup", related_name="lessons", verbose_name="Guruh(lar)")
    room = models.ForeignKey(
        Room, on_delete=models.SET_NULL, null=True, blank=True, related_name="lessons",
        verbose_name="Auditoriya")
    timeslot = models.ForeignKey(
        TimeSlot, on_delete=models.CASCADE, related_name="lessons", verbose_name="Juft")
    week_day = models.PositiveSmallIntegerField("Hafta kuni", choices=WeekDay.choices)
    week_type = models.CharField("Hafta turi", max_length=5, choices=WeekType.choices,
                                 default=WeekType.ALL)
    kind = models.CharField("Dars turi", max_length=12, choices=Kind.choices, default=Kind.LECTURE)
    is_active = models.BooleanField("Faol", default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Dars"
        verbose_name_plural = "Dars jadvali"
        ordering = ["week_day", "timeslot__order"]

    def __str__(self):
        return f"{self.course.code} · {self.get_week_day_display()} · {self.timeslot.order}-juft"


def _week_types_overlap(a, b):
    """Ikki hafta turi bir haftada to'qnashadimi."""
    if a == Lesson.WeekType.ALL or b == Lesson.WeekType.ALL:
        return True
    return a == b


def check_conflicts(academic_year, timeslot, week_day, week_type, teacher,
                    room, group_ids, exclude_id=None):
    """Bir vaqt oralig'ida o'qituvchi/xona/guruh bandligini tekshiradi.
    To'qnashuvlar ro'yxatini (matn) qaytaradi."""
    qs = Lesson.objects.filter(academic_year=academic_year, timeslot=timeslot,
                               week_day=week_day, is_active=True)
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    conflicts = []
    for other in qs.select_related("teacher", "room").prefetch_related("groups"):
        if not _week_types_overlap(week_type, other.week_type):
            continue
        if teacher and other.teacher_id == teacher.id:
            conflicts.append(f"O‘qituvchi ({teacher.full_name or teacher.username}) shu vaqtda band: "
                             f"{other.course.code}")
        if room and other.room_id == room.id:
            conflicts.append(f"Auditoriya ({room.name}) shu vaqtda band: {other.course.code}")
        common = set(other.groups.values_list("id", flat=True)) & set(group_ids)
        if common:
            conflicts.append(f"Guruh shu vaqtda band: {other.course.code}")
    return conflicts
