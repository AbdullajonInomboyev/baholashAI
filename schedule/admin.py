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
