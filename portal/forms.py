from django import forms

from academics.models import (
    AcademicGroup, AcademicYear, Course, Curriculum, Department, Direction, StudyForm,
)
from accounts.models import Role
from django.contrib.auth import get_user_model
from teaching.models import DepartmentCourse


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name", "head"]

    def __init__(self, *args, faculty=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["head"].required = False
        self.fields["head"].label = "Kafedra mudiri"
        self.fields["name"].label = "Kafedra nomi"


class DirectionForm(forms.ModelForm):
    class Meta:
        model = Direction
        fields = ["department", "code", "name"]
        labels = {"department": "Mas‘ul kafedra", "code": "Yo‘nalish kodi", "name": "Nomi"}

    def __init__(self, *args, faculty=None, **kwargs):
        super().__init__(*args, **kwargs)
        if faculty is not None:
            self.fields["department"].queryset = Department.objects.filter(faculty=faculty)


class AcademicYearForm(forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = ["title", "is_active"]
        labels = {"title": "O‘quv yili", "is_active": "Faol"}
        widgets = {"title": forms.TextInput(attrs={"placeholder": "2025-2026"})}


class ImportForm(forms.Form):
    file = forms.FileField(label="O‘quv reja fayli (.xlsx)")
    direction = forms.ModelChoiceField(
        label="Yo‘nalish", queryset=Direction.objects.none(), required=False,
        empty_label="Excel’dagi kodni ishlatish (avtomatik)",
    )
    forms_to_import = forms.MultipleChoiceField(
        label="Ta‘lim shakllari",
        choices=StudyForm.choices,
        widget=forms.CheckboxSelectMultiple,
        initial=[c for c, _ in StudyForm.choices],
    )

    def __init__(self, *args, faculty=None, **kwargs):
        super().__init__(*args, **kwargs)
        if faculty is not None:
            self.fields["direction"].queryset = Direction.objects.filter(faculty=faculty)


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = [
            "curriculum", "code", "name", "is_elective",
            "total_hours", "lecture_hours", "practice_hours", "lab_hours",
            "seminar_hours", "course_project_hours", "independent_hours",
        ]
        labels = {"curriculum": "O‘quv reja (yo‘nalish · yil · shakl)"}

    def __init__(self, *args, faculty=None, **kwargs):
        super().__init__(*args, **kwargs)
        if faculty is not None:
            self.fields["curriculum"].queryset = Curriculum.objects.filter(
                direction__faculty=faculty
            ).select_related("direction", "academic_year")


class AssignCourseForm(forms.Form):
    department = forms.ModelChoiceField(queryset=Department.objects.none(), label="Kafedra")

    def __init__(self, *args, faculty=None, **kwargs):
        super().__init__(*args, **kwargs)
        if faculty is not None:
            self.fields["department"].queryset = Department.objects.filter(faculty=faculty)


class StudentImportForm(forms.Form):
    file = forms.FileField(label="Talabalar fayli (.xlsx)")


class ReportRemarkForm(forms.Form):
    department = forms.ModelChoiceField(queryset=Department.objects.none(), label="Kafedra")
    message = forms.CharField(label="Izoh", widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, faculty=None, **kwargs):
        super().__init__(*args, **kwargs)
        if faculty is not None:
            self.fields["department"].queryset = Department.objects.filter(faculty=faculty)


class CoursePlacementForm(forms.Form):
    semester_number = forms.IntegerField(label="Semestr", min_value=1, max_value=8)
    credits = forms.DecimalField(label="Kredit", max_digits=5, decimal_places=2, required=False)
    weekly_hours = forms.IntegerField(label="Haftalik soat", min_value=0, required=False)


class SyllabusTopicForm(forms.Form):
    order = forms.IntegerField(label="Tartib", min_value=1)
    title = forms.CharField(label="Mavzu", max_length=500)


class StudentProfileForm(forms.Form):
    full_name = forms.CharField(label="F.I.Sh.", max_length=255)
    email = forms.EmailField(label="Email", required=False)
    phone = forms.CharField(label="Telefon", max_length=30, required=False)
    group_name = forms.CharField(label="Guruh", max_length=50, required=False)
    status = forms.ChoiceField(label="Holat")
    direction = forms.ModelChoiceField(label="Yo‘nalish", queryset=None)
    study_form = forms.ChoiceField(label="Ta‘lim shakli")

    def __init__(self, *args, faculty=None, **kwargs):
        from academics.models import Direction, StudentEnrollment, StudyForm
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = StudentEnrollment.Status.choices
        self.fields["study_form"].choices = StudyForm.choices
        self.fields["direction"].queryset = Direction.objects.filter(faculty=faculty) if faculty else Direction.objects.none()


class AssignmentForm(forms.ModelForm):
    from assessment.models import Assignment as _A

    class Meta:
        from assessment.models import Assignment
        model = Assignment
        fields = ["assignment_type", "title", "description", "due_date", "status"]
        labels = {"assignment_type": "Topshiriq turi", "title": "Sarlavha",
                  "description": "Tavsif", "due_date": "Muddat", "status": "Holat"}
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"}),
                   "description": forms.Textarea(attrs={"rows": 3})}


class ResourceUploadForm(forms.Form):
    title = forms.CharField(label="Sarlavha", max_length=255)
    kind = forms.ChoiceField(label="Turkum")
    resource_format = forms.ChoiceField(label="Ko‘rinishi")
    file = forms.FileField(label="Fayl (fayl turi uchun)", required=False)
    url = forms.URLField(label="Havola (URL/Video uchun)", required=False)
    content = forms.CharField(label="Matn (sahifa turi uchun)", required=False,
                              widget=forms.Textarea(attrs={"rows": 5}))
    assignments = forms.MultipleChoiceField(
        label="Qaysi fanlarga biriktirilsin", widget=forms.CheckboxSelectMultiple, required=True)
    topic = forms.ChoiceField(label="Mavzu (ixtiyoriy)", required=False)

    def __init__(self, *args, teacher_assignments=None, **kwargs):
        from teaching.models import Resource
        super().__init__(*args, **kwargs)
        tas = list(teacher_assignments or [])
        self.fields["kind"].choices = Resource.Kind.choices
        self.fields["resource_format"].choices = Resource.Format.choices
        self.fields["assignments"].choices = [
            (ta.pk, f"{ta.department_course.course.code} — {ta.department_course.course.name}")
            for ta in tas]
        topic_choices = [("", "— (mavzuga bog‘lamaslik) —")]
        for ta in tas:
            for t in ta.department_course.course.topics.all():
                topic_choices.append((t.pk, f"{ta.department_course.course.code}: {t.title}"))
        self.fields["topic"].choices = topic_choices

    def clean(self):
        c = super().clean()
        fmt = c.get("resource_format")
        if fmt == "file" and not c.get("file"):
            raise forms.ValidationError("Fayl turi uchun fayl yuklang.")
        if fmt in ("url", "video") and not c.get("url"):
            raise forms.ValidationError("Havola/Video turi uchun URL kiriting.")
        if fmt == "page" and not c.get("content"):
            raise forms.ValidationError("Sahifa turi uchun matn kiriting.")
        return c


class GradeForm(forms.Form):
    final_score = forms.DecimalField(label="Yakuniy baho", max_digits=5, decimal_places=2,
                                     min_value=0, max_value=100)


class SubmissionForm(forms.Form):
    text_answer = forms.CharField(
        label="Javob (onlayn matn)", required=False,
        widget=forms.Textarea(attrs={"rows": 8, "placeholder": "Javobingizni shu yerga yozing…"}),
    )
    file = forms.FileField(label="Yoki ish faylini yuklang", required=False)

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("text_answer") and not cleaned.get("file"):
            raise forms.ValidationError("Matn javob yozing yoki fayl yuklang.")
        return cleaned


class AcademicGroupForm(forms.ModelForm):
    class Meta:
        model = AcademicGroup
        fields = ["direction", "academic_year", "name", "study_form", "course", "curator", "is_active"]
        labels = {"direction": "Yo‘nalish", "academic_year": "Qabul yili", "name": "Guruh nomi",
                  "study_form": "Ta‘lim shakli", "course": "Kurs", "curator": "Kurator",
                  "is_active": "Faol"}
        widgets = {"name": forms.TextInput(attrs={"placeholder": "Masalan: AT-24"})}

    def __init__(self, *args, faculty=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["academic_year"].required = False
        self.fields["curator"].required = False
        if faculty is not None:
            self.fields["direction"].queryset = Direction.objects.filter(faculty=faculty)
            self.fields["academic_year"].queryset = AcademicYear.objects.filter(faculty=faculty)
            self.fields["curator"].queryset = (
                get_user_model().objects.filter(roles__role=Role.TEACHER).distinct()
            )


from schedule.models import Building, Room  # noqa: E402


class BuildingForm(forms.ModelForm):
    class Meta:
        model = Building
        fields = ["name", "address", "is_active"]
        labels = {"name": "Bino nomi", "address": "Manzil", "is_active": "Faol"}


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ["building", "name", "kind", "capacity", "floor", "is_active"]
        labels = {"building": "Bino", "name": "Xona raqami", "kind": "Turi",
                  "capacity": "Sig‘imi", "floor": "Qavat", "is_active": "Faol"}
