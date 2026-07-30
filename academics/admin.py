from django.contrib import admin

from .models import (
    AcademicYear, Course, CourseSemester, Curriculum, Department, Direction,
    ExcelImport, Faculty, Semester, StudentEnrollment, SyllabusTopic,
)


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ("name", "dean")
    search_fields = ("name",)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "faculty", "head")
    list_filter = ("faculty",)
    search_fields = ("name",)


@admin.register(Direction)
class DirectionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "faculty")
    search_fields = ("code", "name")


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ("title", "faculty", "is_active")
    list_filter = ("is_active", "faculty")


class CourseSemesterInline(admin.TabularInline):
    model = CourseSemester
    extra = 0


@admin.register(Curriculum)
class CurriculumAdmin(admin.ModelAdmin):
    list_display = ("direction", "academic_year", "study_form")
    list_filter = ("academic_year", "study_form", "direction")
    search_fields = ("direction__code", "direction__name")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "curriculum", "is_elective", "total_hours", "credit")
    list_filter = ("curriculum__study_form", "curriculum__academic_year", "is_elective")
    search_fields = ("code", "name")
    autocomplete_fields = ["curriculum"]
    inlines = [CourseSemesterInline]


@admin.register(ExcelImport)
class ExcelImportAdmin(admin.ModelAdmin):
    list_display = ("academic_year", "study_form", "status", "uploaded_by", "created_at")
    list_filter = ("status", "study_form")


admin.site.register(Semester)
admin.site.register(SyllabusTopic)
admin.site.register(StudentEnrollment)
