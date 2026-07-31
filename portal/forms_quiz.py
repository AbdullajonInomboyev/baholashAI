from django import forms

from assessment.models import Choice, Question, Quiz
from teaching.models import TeacherAssignment


class QuizForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ["teacher_assignment", "title", "description", "time_limit_minutes"]
        labels = {"teacher_assignment": "Fan"}
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, teacher=None, **kwargs):
        super().__init__(*args, **kwargs)
        if teacher is not None:
            self.fields["teacher_assignment"].queryset = (
                TeacherAssignment.objects
                .filter(teacher=teacher, status=TeacherAssignment.Status.ACTIVE)
                .select_related("department_course__course")
            )


class QuestionForm(forms.Form):
    text = forms.CharField(label="Savol matni", widget=forms.Textarea(attrs={"rows": 2}))
    kind = forms.ChoiceField(label="Turi", choices=Question.Kind.choices)
    points = forms.IntegerField(label="Ball", min_value=1, initial=1)
    correct_text = forms.CharField(label="To‘g‘ri javob (qisqa matn turi uchun)", required=False)
    tf_correct = forms.ChoiceField(
        label="To‘g‘ri/Noto‘g‘ri uchun to‘g‘ri javob", required=False,
        choices=[("true", "To‘g‘ri"), ("false", "Noto‘g‘ri")],
    )
    choice_1 = forms.CharField(label="Variant 1", required=False)
    choice_2 = forms.CharField(label="Variant 2", required=False)
    choice_3 = forms.CharField(label="Variant 3", required=False)
    choice_4 = forms.CharField(label="Variant 4", required=False)
    correct_1 = forms.BooleanField(label="1 to‘g‘ri", required=False)
    correct_2 = forms.BooleanField(label="2 to‘g‘ri", required=False)
    correct_3 = forms.BooleanField(label="3 to‘g‘ri", required=False)
    correct_4 = forms.BooleanField(label="4 to‘g‘ri", required=False)

    def clean(self):
        c = super().clean()
        kind = c.get("kind")
        if kind == Question.Kind.SHORT and not c.get("correct_text"):
            raise forms.ValidationError("Qisqa matnli savol uchun to‘g‘ri javobni kiriting.")
        if kind in ("single", "multiple"):
            filled = [c.get(f"choice_{i}") for i in range(1, 5) if c.get(f"choice_{i}")]
            correct = [i for i in range(1, 5) if c.get(f"correct_{i}") and c.get(f"choice_{i}")]
            if len(filled) < 2:
                raise forms.ValidationError("Kamida 2 ta variant kiriting.")
            if not correct:
                raise forms.ValidationError("Kamida bitta to‘g‘ri variantni belgilang.")
            if kind == "single" and len(correct) != 1:
                raise forms.ValidationError("«Bitta to‘g‘ri javob» uchun aynan bitta to‘g‘ri variant bo‘lsin.")
        if kind == Question.Kind.TRUE_FALSE and not c.get("tf_correct"):
            raise forms.ValidationError("To‘g‘ri/Noto‘g‘ri javobni tanlang.")
        return c

    def save(self, quiz):
        c = self.cleaned_data
        kind = c["kind"]
        order = quiz.questions.count() + 1
        q = Question.objects.create(
            quiz=quiz, text=c["text"], kind=kind, points=c["points"],
            correct_text=c.get("correct_text", ""), order=order,
        )
        if kind == Question.Kind.TRUE_FALSE:
            Choice.objects.create(question=q, text="To‘g‘ri", is_correct=(c["tf_correct"] == "true"), order=1)
            Choice.objects.create(question=q, text="Noto‘g‘ri", is_correct=(c["tf_correct"] == "false"), order=2)
        elif kind in ("single", "multiple"):
            for i in range(1, 5):
                txt = c.get(f"choice_{i}")
                if txt:
                    Choice.objects.create(question=q, text=txt, is_correct=bool(c.get(f"correct_{i}")), order=i)
        return q
