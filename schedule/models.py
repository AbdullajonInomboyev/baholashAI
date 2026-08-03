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
