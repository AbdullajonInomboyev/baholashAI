"""O'qituvchi: Savollar banki (Word'dan import)."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Role
from qbank.models import QuestionBank, TestBank, Question, TestQuestion
from qbank.services.docx_parser import (
    TestQuestionDocxParser, WrittenQuestionDocxParser, DocxParseError,
)
from teaching.models import TeacherAssignment
from .access import role_required


def _panel(request):
    return {"panel_title": "O‘qituvchi paneli",
            "panel_scope": request.user.full_name or request.user.username}


def _my_courses(user):
    from academics.models import Course
    ids = (TeacherAssignment.objects.filter(teacher=user, status=TeacherAssignment.Status.ACTIVE)
           .values_list("department_course__course_id", flat=True))
    return Course.objects.filter(id__in=list(ids)).select_related("curriculum__direction")


@role_required(Role.TEACHER)
def banks(request):
    ctx = _panel(request)
    ctx.update({
        "active": "qbank",
        "test_banks": TestBank.objects.filter(created_by=request.user),
        "written_banks": QuestionBank.objects.filter(created_by=request.user),
        "courses": _my_courses(request.user),
    })
    return render(request, "portal/qbank/banks.html", ctx)


@role_required(Role.TEACHER)
def bank_create(request):
    if request.method != "POST":
        return redirect("portal:qbank_banks")
    kind = request.POST.get("kind")
    title = (request.POST.get("title") or "").strip()
    course_id = request.POST.get("course") or None
    if not title:
        messages.error(request, "Bank nomini kiriting.")
        return redirect("portal:qbank_banks")
    course = None
    if course_id:
        course = _my_courses(request.user).filter(pk=course_id).first()
    if kind == "test":
        b = TestBank.objects.create(title=title, course=course, created_by=request.user)
        messages.success(request, "Test banki yaratildi. Endi Word fayl yuklang.")
        return redirect("portal:qbank_test_detail", pk=b.pk)
    else:
        b = QuestionBank.objects.create(title=title, course=course, created_by=request.user)
        messages.success(request, "Yozma savollar banki yaratildi. Endi Word fayl yuklang.")
        return redirect("portal:qbank_written_detail", pk=b.pk)


# ---------- Test banki ----------

@role_required(Role.TEACHER)
def test_detail(request, pk):
    bank = get_object_or_404(TestBank, pk=pk, created_by=request.user)
    assignments = (TeacherAssignment.objects
                   .filter(teacher=request.user, status=TeacherAssignment.Status.ACTIVE)
                   .select_related("department_course__course"))
    ctx = _panel(request)
    ctx.update({"active": "qbank", "bank": bank, "questions": bank.questions.all(),
                "assignments": assignments})
    return render(request, "portal/qbank/test_detail.html", ctx)


@role_required(Role.TEACHER)
def test_import(request, pk):
    bank = get_object_or_404(TestBank, pk=pk, created_by=request.user)
    f = request.FILES.get("file")
    if not f:
        return redirect("portal:qbank_test_detail", pk=pk)
    try:
        created = TestQuestionDocxParser(f).parse_into_bank(bank)
        messages.success(request, f"{len(created)} ta test savoli import qilindi.")
    except DocxParseError as e:
        messages.error(request, f"Xatolik: {e}")
    except Exception:
        messages.error(request, "Faylni o‘qib bo‘lmadi. Word (.docx) va to‘g‘ri format ekanini tekshiring.")
    return redirect("portal:qbank_test_detail", pk=pk)


@role_required(Role.TEACHER)
def test_delete(request, pk):
    get_object_or_404(TestBank, pk=pk, created_by=request.user).delete()
    messages.success(request, "Test banki o‘chirildi.")
    return redirect("portal:qbank_banks")


# ---------- Yozma savollar banki ----------

@role_required(Role.TEACHER)
def written_detail(request, pk):
    bank = get_object_or_404(QuestionBank, pk=pk, created_by=request.user)
    assignments = (TeacherAssignment.objects
                   .filter(teacher=request.user, status=TeacherAssignment.Status.ACTIVE)
                   .select_related("department_course__course"))
    ctx = _panel(request)
    ctx.update({"active": "qbank", "bank": bank,
                "groups": bank.groups.prefetch_related("questions"),
                "assignments": assignments, "exams": bank.exams.all()})
    return render(request, "portal/qbank/written_detail.html", ctx)


@role_required(Role.TEACHER)
def written_import(request, pk):
    bank = get_object_or_404(QuestionBank, pk=pk, created_by=request.user)
    f = request.FILES.get("file")
    if not f:
        return redirect("portal:qbank_written_detail", pk=pk)
    try:
        groups = WrittenQuestionDocxParser(f).parse_into_bank(bank)
        n = Question.objects.filter(group__bank=bank).count()
        messages.success(request, f"{len(groups)} guruh, {n} savol import qilindi.")
    except DocxParseError as e:
        messages.error(request, f"Xatolik: {e}")
    except Exception:
        messages.error(request, "Faylni o‘qib bo‘lmadi. Word (.docx) va to‘g‘ri format ekanini tekshiring.")
    return redirect("portal:qbank_written_detail", pk=pk)


@role_required(Role.TEACHER)
def written_delete(request, pk):
    get_object_or_404(QuestionBank, pk=pk, created_by=request.user).delete()
    messages.success(request, "Yozma savollar banki o‘chirildi.")
    return redirect("portal:qbank_banks")


# ---------- Bankdan talaba testini yaratish ----------

@role_required(Role.TEACHER)
def test_to_quiz(request, pk):
    import random
    from django.urls import reverse
    from django.contrib.auth import get_user_model
    from core.notifications import notify_many
    from assessment.models import Quiz, Question as QQuestion, Choice
    bank = get_object_or_404(TestBank, pk=pk, created_by=request.user)
    if request.method != "POST":
        return redirect("portal:qbank_test_detail", pk=pk)
    ta = TeacherAssignment.objects.filter(
        pk=request.POST.get("assignment"), teacher=request.user,
        status=TeacherAssignment.Status.ACTIVE).first()
    if not ta:
        messages.error(request, "Fan (biriktiruv) tanlanmadi.")
        return redirect("portal:qbank_test_detail", pk=pk)
    title = (request.POST.get("title") or bank.title).strip()
    tqs = list(bank.questions.all())
    if not tqs:
        messages.error(request, "Bankда savol yo‘q.")
        return redirect("portal:qbank_test_detail", pk=pk)
    quiz = Quiz.objects.create(teacher_assignment=ta, title=title,
                               description="Savollar bankidan yaratilgan", is_open=True)
    order = 0
    for tq in tqs:
        text = tq.raw_text or (tq.question_html and "[formula/rasm]") or "Savol"
        order += 1
        q = QQuestion.objects.create(quiz=quiz, text=text, kind=QQuestion.Kind.SINGLE,
                                     points=1, order=order,
                                     formula_mathml=tq.formula_mathml or "")
        variants = [(tq.correct_answer, True)]
        for opt in (tq.option1, tq.option2, tq.option3):
            if opt:
                variants.append((opt, False))
        random.shuffle(variants)
        for oi, (t, ok) in enumerate(variants, start=1):
            Choice.objects.create(question=q, text=(t or "")[:255], is_correct=ok, order=oi)
    cur = ta.department_course.course.curriculum
    students = get_user_model().objects.filter(
        enrollments__direction=cur.direction, enrollments__study_form=cur.study_form).distinct()
    notify_many(students, f"Yangi test: {quiz.title}", reverse("portal:student_quizzes"))
    messages.success(request, f"«{title}» testi yaratildi ({len(tqs)} savol). Endi ko‘rib chiqing.")
    return redirect("portal:quiz_manage", pk=quiz.pk)


# ==================== Yozma imtihon ====================

@role_required(Role.TEACHER)
def written_to_exam(request, pk):
    from qbank.models import WrittenExam
    bank = get_object_or_404(QuestionBank, pk=pk, created_by=request.user)
    if request.method != "POST":
        return redirect("portal:qbank_written_detail", pk=pk)
    ta = TeacherAssignment.objects.filter(
        pk=request.POST.get("assignment"), teacher=request.user,
        status=TeacherAssignment.Status.ACTIVE).first()
    if not ta:
        messages.error(request, "Fan (biriktiruv) tanlanmadi.")
        return redirect("portal:qbank_written_detail", pk=pk)
    if not Question.objects.filter(group__bank=bank).exists():
        messages.error(request, "Bankда savol yo‘q.")
        return redirect("portal:qbank_written_detail", pk=pk)
    exam = WrittenExam.objects.create(
        bank=bank, teacher_assignment=ta,
        title=(request.POST.get("title") or bank.title).strip(), created_by=request.user)
    from django.contrib.auth import get_user_model
    from core.notifications import notify_many
    from django.urls import reverse
    cur = ta.department_course.course.curriculum
    students = get_user_model().objects.filter(
        enrollments__direction=cur.direction, enrollments__study_form=cur.study_form).distinct()
    notify_many(students, f"Yangi yozma imtihon: {exam.title}", reverse("portal:student_exams"))
    messages.success(request, "Yozma imtihon yaratildi va talabalarga e'lon qilindi.")
    return redirect("portal:qbank_exam_submissions", pk=exam.pk)


@role_required(Role.TEACHER)
def exam_submissions(request, pk):
    from qbank.models import WrittenExam
    exam = get_object_or_404(WrittenExam, pk=pk, created_by=request.user)
    subs = exam.submissions.select_related("student")
    ctx = _panel(request)
    ctx.update({"active": "qbank", "exam": exam, "subs": subs})
    return render(request, "portal/qbank/exam_submissions.html", ctx)


@role_required(Role.TEACHER)
def exam_review(request, pk):
    from qbank.models import WrittenExamSubmission
    sub = get_object_or_404(
        WrittenExamSubmission.objects.select_related("exam", "student"),
        pk=pk, exam__created_by=request.user)
    answers = sub.answers.select_related("question")
    if request.method == "POST":
        total = 0
        for a in answers:
            raw = request.POST.get(f"score_{a.pk}", "").strip()
            a.feedback = request.POST.get(f"fb_{a.pk}", "").strip()
            try:
                a.score = float(raw) if raw else None
            except ValueError:
                a.score = None
            a.save(update_fields=["score", "feedback"])
            total += float(a.score) if a.score else 0
        sub.total_score = total
        sub.reviewed = True
        sub.save(update_fields=["total_score", "reviewed"])
        from core.notifications import notify
        from django.urls import reverse
        notify(sub.student, f"«{sub.exam.title}» imtihoningiz baholandi: {total} ball",
               reverse("portal:student_exams"))
        messages.success(request, "Baholandi.")
        return redirect("portal:qbank_exam_submissions", pk=sub.exam.pk)
    ctx = _panel(request)
    ctx.update({"active": "qbank", "sub": sub, "answers": answers})
    return render(request, "portal/qbank/exam_review.html", ctx)
