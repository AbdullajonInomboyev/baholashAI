from django import forms

from academics.models import (
    AcademicYear, Course, Curriculum, Department, Direction, StudyForm,
)
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
        fields = ["code", "name"]
        labels = {"code": "Yo‘nalish kodi", "name": "Nomi"}


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
    kind = forms.ChoiceField(label="Turi")
    file = forms.FileField(label="Fayl")
    assignments = forms.MultipleChoiceField(
        label="Qaysi fanlarga biriktirilsin", widget=forms.CheckboxSelectMultiple, required=True)

    def __init__(self, *args, teacher_assignments=None, **kwargs):
        from teaching.models import Resource
        super().__init__(*args, **kwargs)
        self.fields["kind"].choices = Resource.Kind.choices
        choices = [(ta.pk, f"{ta.department_course.course.code} — {ta.department_course.course.name}")
                   for ta in (teacher_assignments or [])]
        self.fields["assignments"].choices = choices


class GradeForm(forms.Form):
    final_score = forms.DecimalField(label="Yakuniy baho", max_digits=5, decimal_places=2,
                                     min_value=0, max_value=100)


class SubmissionForm(forms.Form):
    file = forms.FileField(label="Ish fayli")
