from django.contrib import admin

from .models import Building, Room


class RoomInline(admin.TabularInline):
    model = Room
    extra = 0


@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ("name", "address", "room_count", "is_active")
    inlines = [RoomInline]


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("name", "building", "kind", "capacity", "floor", "is_active")
    list_filter = ("kind", "building", "is_active")


from .models import Lesson, TimeSlot  # noqa: E402


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ("order", "start_time", "end_time", "is_active")


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("course", "teacher", "week_day", "timeslot", "week_type", "kind", "room")
    list_filter = ("week_day", "week_type", "kind")
    filter_horizontal = ("groups",)
