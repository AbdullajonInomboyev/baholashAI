from django.contrib import messages
from django.core.files.base import ContentFile
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Role
from assessment.models import (
    Assignment, AssignmentCriterion, AssignmentType, CriterionScore, Submission, TeacherReview,
)
from assessment.services import ai
from core.audit import log_action
from core.notifications import notify, notify_many
from django.urls import reverse
from teaching.models import (
    Resource, ResourceLink, ResourceReview, TeacherAssignment,
)

from .access import role_required
from .forms import AssignmentForm, GradeForm, ResourceUploadForm

STATUS = TeacherAssignment.Status


def _my_assignments(user):
    return (TeacherAssignment.objects
            .filter(teacher=user, status=STATUS.ACTIVE)
            .select_related("department_course__course", "department_course__department"))


def _base(request):
    return {"panel_title": "O‘qituvchi paneli",
            "panel_scope": request.user.full_name or request.user.username}


@role_required(Role.TEACHER)
def dashboard(request):
    from academics.models import StudentEnrollment
    ctx = _base(request)
    mine = _my_assignments(request.user)
    my_courses = _my_courses_qs(request.user)
    total_hours = sum(c.total_hours or 0 for c in my_courses)
    group_ids = list(_my_groups_qs(request.user).values_list("id", flat=True))
    n_students = StudentEnrollment.objects.filter(group_id__in=group_ids).count()
    ctx.update({
        "active": "dashboard",
        "n_courses": my_courses.count(),
        "n_groups": len(group_ids),
        "n_students": n_students,
        "total_hours": total_hours,
        "n_assignments": Assignment.objects.filter(teacher_assignment__in=mine).count(),
        "n_pending": Submission.objects.filter(
            assignment__teacher_assignment__in=mine, status=Submission.Status.AI_EVALUATED).count(),
        "n_resources": Resource.objects.filter(uploaded_by=request.user).count(),
        "n_in_review": Resource.objects.filter(
            uploaded_by=request.user, dept_status=Resource.DeptStatus.NEW).count(),
        "recent_resources": Resource.objects.filter(uploaded_by=request.user).order_by("-created_at")[:5],
        "recent_notifications": request.user.notifications.all()[:5],
    })
    return render(request, "portal/teacher/dashboard.html", ctx)


# ==================== Hisobotlar (o'qituvchi) ====================

@role_required(Role.TEACHER)
def reports(request):
    from academics.models import StudentEnrollment
    ctx = _base(request)
    my_courses = _my_courses_qs(request.user)
    group_ids = list(_my_groups_qs(request.user).values_list("id", flat=True))
    ctx.update({"active": "reports", "stats": {
        "courses": my_courses.count(),
        "resources": Resource.objects.filter(uploaded_by=request.user).count(),
        "approved": Resource.objects.filter(uploaded_by=request.user, approval_status="approved").count(),
        "groups": len(group_ids),
        "students": StudentEnrollment.objects.filter(group_id__in=group_ids).count(),
        "hours": sum(c.total_hours or 0 for c in my_courses),
    }})
    return render(request, "portal/teacher/reports.html", ctx)


@role_required(Role.TEACHER)
def report_pdf(request):
    from django.http import HttpResponse
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from io import BytesIO
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=14 * mm)
    styles = getSampleStyleSheet()
    who = request.user.full_name or request.user.username
    elems = [Paragraph(f"O‘qituvchi hisoboti — {who}", styles["Title"]), Spacer(1, 8)]
    rows = [["Fan kodi", "Fan nomi", "Soat", "Resurslar"]]
    for c in _my_courses_qs(request.user):
        n_res = Resource.objects.filter(
            uploaded_by=request.user,
            links__teacher_assignment__department_course__course=c).distinct().count()
        rows.append([c.code, c.name, str(c.total_hours or 0), str(n_res)])
    if len(rows) == 1:
        rows.append(["—", "Fan biriktirilmagan", "0", "0"])
    t = Table(rows, repeatRows=1, hAlign="LEFT", colWidths=[60, 220, 50, 70])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3d5ee1")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9cede")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6fa")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elems.append(t)
    doc.build(elems)
    resp = HttpResponse(buf.getvalue(), content_type="application/pdf")
    resp["Content-Disposition"] = 'attachment; filename="oqituvchi_hisoboti.pdf"'
    return resp


@role_required(Role.TEACHER)
def report_excel(request):
    from django.http import HttpResponse
    from openpyxl import Workbook
    from io import BytesIO
    wb = Workbook()
    ws = wb.active
    ws.title = "Fanlar"
    ws.append(["Fan kodi", "Fan nomi", "Soat", "Resurslar"])
    for c in _my_courses_qs(request.user):
        n_res = Resource.objects.filter(
            uploaded_by=request.user,
            links__teacher_assignment__department_course__course=c).distinct().count()
        ws.append([c.code, c.name, c.total_hours or 0, n_res])
    buf = BytesIO()
    wb.save(buf)
    resp = HttpResponse(buf.getvalue(),
                        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = 'attachment; filename="oqituvchi_hisoboti.xlsx"'
    return resp


@role_required(Role.TEACHER)
def courses(request):
    ctx = _base(request)
    mine = _my_assignments(request.user).annotate(n=Count("assignments"))
    ctx.update({"active": "courses", "assignments": mine})
    return render(request, "portal/teacher/courses.html", ctx)


@role_required(Role.TEACHER)
def course_assignments(request, pk):
    ctx = _base(request)
    ta = get_object_or_404(_my_assignments(request.user), pk=pk)
    ctx.update({"active": "courses", "ta": ta,
                "assignments": ta.assignments.select_related("assignment_type").all()})
    return render(request, "portal/teacher/course_assignments.html", ctx)


@role_required(Role.TEACHER)
def assignment_form(request, pk, assignment_pk=None):
    ctx = _base(request)
    ta = get_object_or_404(_my_assignments(request.user), pk=pk)
    instance = get_object_or_404(Assignment, pk=assignment_pk, teacher_assignment=ta) if assignment_pk else None
    form = AssignmentForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        assignment = form.save(commit=False)
        is_new = assignment.pk is None
        assignment.teacher_assignment = ta
        assignment.save()
        if is_new and assignment.status != Assignment.Status.DRAFT:
            notify_many(_course_students(ta), f"Yangi topshiriq: {assignment.title}",
                        reverse("portal:student_assignment_detail", args=[assignment.pk]))
        # tanlangan turga qaysi AI ishlashini ko‘rsatib beramiz
        model = ai.model_for_assignment_type(assignment.assignment_type)
        messages.success(request, f"Topshiriq saqlandi. Baholovchi AI: {model or '—'}.")
        return redirect("portal:teacher_course_assignments", pk=ta.pk)
    ctx.update({"active": "courses", "ta": ta, "form": form, "instance": instance})
    return render(request, "portal/teacher/assignment_form.html", ctx)


@role_required(Role.TEACHER)
def assignment_delete(request, pk, assignment_pk):
    ta = get_object_or_404(_my_assignments(request.user), pk=pk)
    if request.method == "POST":
        Assignment.objects.filter(pk=assignment_pk, teacher_assignment=ta).delete()
        messages.success(request, "Topshiriq o‘chirildi.")
    return redirect("portal:teacher_course_assignments", pk=pk)


@role_required(Role.TEACHER)
def submissions(request, assignment_pk):
    ctx = _base(request)
    mine = _my_assignments(request.user)
    assignment = get_object_or_404(Assignment, pk=assignment_pk, teacher_assignment__in=mine)
    subs = (assignment.submissions
            .select_related("student", "ai_evaluation", "teacher_review").order_by("student__full_name"))
    ctx.update({"active": "courses", "assignment": assignment, "submissions": subs,
                "grade_form": GradeForm()})
    return render(request, "portal/teacher/submissions.html", ctx)


@role_required(Role.TEACHER)
def review_confirm(request, submission_pk):
    """AI bahosini tasdiqlash (o‘zgarishsiz)."""
    submission = _get_submission(request, submission_pk)
    ai_score = getattr(getattr(submission, "ai_evaluation", None), "score", None)
    TeacherReview.objects.update_or_create(
        submission=submission,
        defaults={"teacher": request.user, "final_score": ai_score,
                  "status": TeacherReview.Status.CONFIRMED})
    submission.status = Submission.Status.TEACHER_REVIEWED
    submission.save(update_fields=["status"])
    notify(submission.student, f"«{submission.assignment.title}» ishingizga baho qo‘yildi: {ai_score}",
           reverse("portal:student_grades"))
    log_action(request.user, "review_confirm", "Submission", submission.pk, new={"score": str(ai_score)})
    messages.success(request, "AI bahosi tasdiqlandi.")
    return redirect("portal:teacher_submissions", assignment_pk=submission.assignment_id)


@role_required(Role.TEACHER)
def review_override(request, submission_pk):
    """AI bahosini o‘zgartirish (yakuniy bahoni qo‘lda qo‘yish)."""
    submission = _get_submission(request, submission_pk)
    form = GradeForm(request.POST)
    if form.is_valid():
        old = getattr(getattr(submission, "ai_evaluation", None), "score", None)
        TeacherReview.objects.update_or_create(
            submission=submission,
            defaults={"teacher": request.user, "final_score": form.cleaned_data["final_score"],
                      "status": TeacherReview.Status.MODIFIED})
        submission.status = Submission.Status.TEACHER_REVIEWED
        submission.save(update_fields=["status"])
        notify(submission.student, f"«{submission.assignment.title}» yakuniy bahosi: {form.cleaned_data['final_score']}",
               reverse("portal:student_grades"))
        log_action(request.user, "review_override", "Submission", submission.pk,
                   old={"ai_score": str(old)}, new={"final": str(form.cleaned_data["final_score"])})
        messages.success(request, "Yakuniy baho o‘zgartirildi.")
    else:
        messages.error(request, "Baho noto‘g‘ri.")
    return redirect("portal:teacher_submissions", assignment_pk=submission.assignment_id)


@role_required(Role.TEACHER)
def resources(request):
    ctx = _base(request)
    qs = (Resource.objects.filter(uploaded_by=request.user)
          .select_related("review")
          .prefetch_related("links__teacher_assignment__department_course__course"))
    kind = request.GET.get("kind")
    counts = {k: qs.filter(kind=k).count() for k, _ in Resource.Kind.choices}
    if kind and kind in dict(Resource.Kind.choices):
        qs = qs.filter(kind=kind)
    ctx.update({"active": "resources", "resources": qs, "f_kind": kind,
                "kinds": Resource.Kind.choices, "counts": counts, "total": Resource.objects.filter(uploaded_by=request.user).count(),
                "form": ResourceUploadForm(teacher_assignments=_my_assignments(request.user))})
    return render(request, "portal/teacher/resources.html", ctx)


@role_required(Role.TEACHER)
def resource_upload(request):
    mine = _my_assignments(request.user)
    form = ResourceUploadForm(request.POST, request.FILES, teacher_assignments=mine)
    if form.is_valid():
        cd = form.cleaned_data
        resource = Resource.objects.create(
            uploaded_by=request.user, title=cd["title"], kind=cd["kind"],
            resource_format=cd["resource_format"],
            file=cd.get("file") if cd["resource_format"] == "file" else None,
            url=cd.get("url", ""), content=cd.get("content", ""))
        topic_id = cd.get("topic") or None
        for ta_id in cd["assignments"]:
            link_topic_id = None
            if topic_id:
                # mavzu shu fanning mavzusi bo‘lsagina bog‘laymiz
                from academics.models import SyllabusTopic
                t = SyllabusTopic.objects.filter(pk=topic_id).first()
                ta = next((x for x in mine if x.pk == int(ta_id)), None)
                if t and ta and t.course_id == ta.department_course.course_id:
                    link_topic_id = t.pk
            ResourceLink.objects.get_or_create(
                resource=resource, teacher_assignment_id=int(ta_id),
                defaults={"topic_id": link_topic_id})
        # yuklanishi bilan AI tahlili avtomatik shakllanadi
        ai.review_resource(resource)
        messages.success(request, "Resurs qo‘shildi va AI tahliliga yuborildi.")
    else:
        err = form.errors.get("__all__")
        messages.error(request, err[0] if err else "Ma‘lumot to‘liq emas (fan tanlang).")
    return redirect("portal:teacher_resources")


def _get_submission(request, submission_pk):
    mine = _my_assignments(request.user)
    return get_object_or_404(
        Submission.objects.select_related("assignment", "ai_evaluation"),
        pk=submission_pk, assignment__teacher_assignment__in=mine)


# ---------------- Rubrika (mezonlar) ----------------

from decimal import Decimal  # noqa: E402


@role_required(Role.TEACHER)
def assignment_criteria(request, assignment_pk):
    mine = _my_assignments(request.user)
    assignment = get_object_or_404(Assignment, pk=assignment_pk, teacher_assignment__in=mine)
    ctx = _base(request)
    ctx.update({"active": "courses", "assignment": assignment,
                "criteria": assignment.criteria.all()})
    return render(request, "portal/teacher/assignment_criteria.html", ctx)


@role_required(Role.TEACHER)
def criterion_add(request, assignment_pk):
    mine = _my_assignments(request.user)
    assignment = get_object_or_404(Assignment, pk=assignment_pk, teacher_assignment__in=mine)
    title = (request.POST.get("title") or "").strip()
    try:
        max_points = int(request.POST.get("max_points") or 10)
    except ValueError:
        max_points = 10
    if title and max_points > 0:
        AssignmentCriterion.objects.create(
            assignment=assignment, title=title, max_points=max_points,
            order=assignment.criteria.count() + 1)
        messages.success(request, "Mezon qo‘shildi.")
    else:
        messages.error(request, "Mezon nomi va ballini kiriting.")
    return redirect("portal:teacher_assignment_criteria", assignment_pk=assignment_pk)


@role_required(Role.TEACHER)
def criterion_delete(request, pk):
    criterion = get_object_or_404(
        AssignmentCriterion, pk=pk,
        assignment__teacher_assignment__in=_my_assignments(request.user))
    a_pk = criterion.assignment_id
    criterion.delete()
    messages.success(request, "Mezon o‘chirildi.")
    return redirect("portal:teacher_assignment_criteria", assignment_pk=a_pk)


@role_required(Role.TEACHER)
def rubric_grade(request, submission_pk):
    submission = _get_submission(request, submission_pk)
    criteria = list(submission.assignment.criteria.all())
    scores = {cs.criterion_id: cs for cs in submission.criterion_scores.all()}

    if request.method == "POST":
        total_max = sum(c.max_points for c in criteria) or 1
        earned = 0
        modified = False
        for c in criteria:
            raw = request.POST.get(f"score_{c.id}")
            try:
                val = max(0, min(c.max_points, float(raw)))
            except (TypeError, ValueError):
                val = 0
            cs, _ = CriterionScore.objects.update_or_create(
                submission=submission, criterion=c,
                defaults={})
            cs.teacher_score = Decimal(str(val))
            cs.save(update_fields=["teacher_score"])
            if cs.ai_score is not None and float(cs.ai_score) != val:
                modified = True
            earned += val
        final = round(earned / total_max * 100, 2)
        TeacherReview.objects.update_or_create(
            submission=submission,
            defaults={"teacher": request.user, "final_score": Decimal(str(final)),
                      "status": TeacherReview.Status.MODIFIED if modified else TeacherReview.Status.CONFIRMED})
        submission.status = Submission.Status.TEACHER_REVIEWED
        submission.save(update_fields=["status"])
        notify(submission.student, f"«{submission.assignment.title}» rubrika bahosi: {final}%",
               reverse("portal:student_grades"))
        log_action(request.user, "rubric_grade", "Submission", submission.pk, new={"final": str(final)})
        messages.success(request, f"Rubrika bo‘yicha yakuniy baho: {final}%.")
        return redirect("portal:teacher_submissions", assignment_pk=submission.assignment_id)

    rows = [{"c": c, "cs": scores.get(c.id)} for c in criteria]
    ctx = _base(request)
    ctx.update({"active": "courses", "submission": submission, "rows": rows})
    return render(request, "portal/teacher/rubric_grade.html", ctx)


# ---------------- Baholar jurnali (gradebook) ----------------

from django.contrib.auth import get_user_model  # noqa: E402


@role_required(Role.TEACHER)
def gradebook(request):
    from assessment.models import Quiz, QuizAttempt
    User = get_user_model()
    mine = _my_assignments(request.user)
    ta_pk = request.GET.get("course")
    selected = (mine.filter(pk=ta_pk).first() if ta_pk else mine.first())

    ctx = _base(request)
    ctx.update({"active": "gradebook", "courses": mine, "selected": selected})

    if selected:
        course = selected.department_course.course
        cur = course.curriculum
        students = list(User.objects.filter(
            enrollments__direction=cur.direction,
            enrollments__study_form=cur.study_form).distinct().order_by("full_name", "username"))

        assignments = list(Assignment.objects.filter(teacher_assignment=selected)
                           .exclude(status=Assignment.Status.DRAFT).order_by("created_at"))
        quizzes = list(Quiz.objects.filter(teacher_assignment=selected).order_by("created_at"))

        # baho xaritalari
        sub_map = {}
        for s in (Submission.objects.filter(assignment__in=assignments)
                  .select_related("teacher_review", "ai_evaluation")):
            score = None
            if getattr(s, "teacher_review", None) and s.teacher_review.final_score is not None:
                score = s.teacher_review.final_score
            elif getattr(s, "ai_evaluation", None) and s.ai_evaluation.score is not None:
                score = s.ai_evaluation.score
            sub_map[(s.assignment_id, s.student_id)] = score
        quiz_map = {(a.quiz_id, a.student_id): a.score
                    for a in QuizAttempt.objects.filter(quiz__in=quizzes, submitted_at__isnull=False)}

        columns = ([{"kind": "a", "id": a.id, "title": a.title} for a in assignments]
                   + [{"kind": "q", "id": q.id, "title": q.title} for q in quizzes])

        rows = []
        for st in students:
            cells = []
            vals = []
            for a in assignments:
                v = sub_map.get((a.id, st.id))
                cells.append(v)
                if v is not None:
                    vals.append(float(v))
            for q in quizzes:
                v = quiz_map.get((q.id, st.id))
                cells.append(v)
                if v is not None:
                    vals.append(float(v))
            avg = round(sum(vals) / len(vals), 1) if vals else None
            rows.append({"student": st, "cells": cells, "avg": avg})

        ctx.update({"columns": columns, "rows": rows, "course": course})

    return render(request, "portal/teacher/gradebook.html", ctx)


def _course_students(ta):
    User = get_user_model()
    cur = ta.department_course.course.curriculum
    return User.objects.filter(enrollments__direction=cur.direction,
                               enrollments__study_form=cur.study_form).distinct()


# ==================== Mening fanlarim (tree) + Fan dasturlari ====================

def _my_courses_qs(user):
    from academics.models import Course
    ta_ids = _my_assignments(user).values_list("department_course__course_id", flat=True)
    return Course.objects.filter(id__in=ta_ids).select_related(
        "curriculum__direction", "curriculum__academic_year")


def _get_my_course(user, pk):
    from academics.models import Course
    return get_object_or_404(_my_courses_qs(user), pk=pk)


@role_required(Role.TEACHER)
def my_courses(request):
    from academics.models import AcademicYear
    ctx = _base(request)
    courses = list(_my_courses_qs(request.user))
    # yil -> semestr -> fan
    years = {}
    for c in courses:
        y = c.curriculum.academic_year
        ynode = years.setdefault(y.id, {"year": y, "sems": {}})
        for pl in c.placements.select_related("semester"):
            n = pl.semester.number
            ynode["sems"].setdefault(n, []).append(c)
        if not c.placements.exists():
            ynode["sems"].setdefault(0, []).append(c)
    tree = []
    for ynode in sorted(years.values(), key=lambda x: x["year"].title, reverse=True):
        sems = [{"n": n, "courses": cs} for n, cs in sorted(ynode["sems"].items())]
        tree.append({"year": ynode["year"], "sems": sems})
    ctx.update({"active": "mycourses", "tree": tree, "n_courses": len(courses)})
    return render(request, "portal/teacher/my_courses.html", ctx)


@role_required(Role.TEACHER)
def course_program(request, pk):
    from academics.models import AcademicGroup, CourseSyllabus
    course = _get_my_course(request.user, pk)
    syllabus, _ = CourseSyllabus.objects.get_or_create(course=course)
    groups = AcademicGroup.objects.filter(direction=course.curriculum.direction)
    resource_links = (ResourceLink.objects
                      .filter(teacher_assignment__teacher=request.user,
                              teacher_assignment__department_course__course=course)
                      .select_related("resource", "topic").distinct())
    ctx = _base(request)
    ctx.update({"active": "mycourses", "course": course, "syllabus": syllabus,
                "groups": groups, "topics": course.topics.all(),
                "literature": course.literature.all(),
                "control_types": course.control_types.all(),
                "control_total": sum(c.weight for c in course.control_types.all()),
                "resource_links": resource_links,
                "placements": course.placements.select_related("semester")})
    return render(request, "portal/teacher/course_program.html", ctx)


@role_required(Role.TEACHER)
def syllabus_save(request, pk):
    from academics.models import CourseSyllabus
    course = _get_my_course(request.user, pk)
    syl, _ = CourseSyllabus.objects.get_or_create(course=course)
    for f in ["about", "objective", "tasks", "outcomes", "grading"]:
        setattr(syl, f, request.POST.get(f, "").strip())
    syl.save()
    messages.success(request, "Sillabus saqlandi.")
    return redirect("portal:teacher_course_program", pk=pk)


@role_required(Role.TEACHER)
def topic_add(request, pk):
    from academics.models import SyllabusTopic
    course = _get_my_course(request.user, pk)
    title = (request.POST.get("title") or "").strip()
    if title:
        from django.db.models import Max
        want = request.POST.get("order")
        taken = set(course.topics.values_list("order", flat=True))
        try:
            order = int(want)
        except (TypeError, ValueError):
            order = None
        if not order or order in taken:
            mx = course.topics.aggregate(m=Max("order"))["m"] or 0
            order = mx + 1
        SyllabusTopic.objects.create(course=course, title=title, order=order)
        messages.success(request, "Mavzu qo‘shildi.")
    return redirect("portal:teacher_course_program", pk=pk)


@role_required(Role.TEACHER)
def topic_delete(request, pk, topic_pk):
    from academics.models import SyllabusTopic
    course = _get_my_course(request.user, pk)
    get_object_or_404(SyllabusTopic, pk=topic_pk, course=course).delete()
    messages.success(request, "Mavzu o‘chirildi.")
    return redirect("portal:teacher_course_program", pk=pk)


@role_required(Role.TEACHER)
def literature_add(request, pk):
    from academics.models import CourseLiterature
    course = _get_my_course(request.user, pk)
    title = (request.POST.get("title") or "").strip()
    if title:
        CourseLiterature.objects.create(
            course=course, title=title, author=request.POST.get("author", "").strip(),
            year=request.POST.get("year", "").strip(),
            kind=request.POST.get("kind", CourseLiterature.Kind.MAIN),
            order=course.literature.count() + 1)
        messages.success(request, "Adabiyot qo‘shildi.")
    return redirect("portal:teacher_course_program", pk=pk)


@role_required(Role.TEACHER)
def literature_delete(request, pk, lit_pk):
    from academics.models import CourseLiterature
    course = _get_my_course(request.user, pk)
    get_object_or_404(CourseLiterature, pk=lit_pk, course=course).delete()
    messages.success(request, "Adabiyot o‘chirildi.")
    return redirect("portal:teacher_course_program", pk=pk)


# ==================== Resurs yuborish workflow (o'qituvchi) ====================

@role_required(Role.TEACHER)
def submissions_center(request):
    ctx = _base(request)
    qs = (Resource.objects.filter(uploaded_by=request.user)
          .select_related("review")
          .prefetch_related("links__teacher_assignment__department_course__course"))
    status = request.GET.get("status", "draft")
    if status in dict(Resource.DeptStatus.choices):
        qs = qs.filter(dept_status=status)
    ctx.update({"active": "submit", "resources": qs, "f_status": status,
                "statuses": Resource.DeptStatus.choices})
    return render(request, "portal/teacher/submit.html", ctx)


def _my_resource(request, pk):
    return get_object_or_404(Resource, pk=pk, uploaded_by=request.user)


@role_required(Role.TEACHER)
def resource_submit(request, pk):
    """Qoralama yoki qaytarilganni kafedra tekshiruviga yuborish."""
    r = _my_resource(request, pk)
    if r.dept_status in (Resource.DeptStatus.DRAFT, Resource.DeptStatus.RETURNED):
        r.dept_status = Resource.DeptStatus.NEW
        r.save(update_fields=["dept_status"])
        # kafedra mudir(lar)iga xabar
        from academics.models import Department
        depts = set()
        for link in r.links.select_related("teacher_assignment__department_course__department"):
            d = link.teacher_assignment.department_course.department
            if d:
                depts.add(d)
        for d in depts:
            for head in d.heads.all() if hasattr(d, "heads") else []:
                notify(head, f"Yangi resurs tekshiruvga keldi: {r.title}",
                       reverse("portal:dept_eresources"))
        messages.success(request, "Resurs kafedra tekshiruviga yuborildi.")
    return redirect(request.META.get("HTTP_REFERER", "portal:teacher_submit"))


@role_required(Role.TEACHER)
def resource_to_draft(request, pk):
    r = _my_resource(request, pk)
    if r.dept_status == Resource.DeptStatus.RETURNED:
        r.dept_status = Resource.DeptStatus.DRAFT
        r.save(update_fields=["dept_status"])
        messages.success(request, "Resurs qoralamaga qaytarildi (tahrirlashingiz mumkin).")
    return redirect(request.META.get("HTTP_REFERER", "portal:teacher_submit"))


# ==================== Mening guruhlarim (o'qituvchi) ====================

def _my_groups_qs(user):
    from academics.models import AcademicGroup
    from schedule.models import Lesson
    ids = set(AcademicGroup.objects.filter(curator=user).values_list("id", flat=True))
    ids |= set(Lesson.objects.filter(teacher=user).values_list("groups__id", flat=True))
    # o'qitadigan fanlar yo'nalishlaridagi guruhlar
    dir_ids = _my_courses_qs(user).values_list("curriculum__direction_id", flat=True)
    ids |= set(AcademicGroup.objects.filter(direction_id__in=list(dir_ids)).values_list("id", flat=True))
    ids.discard(None)
    return (AcademicGroup.objects.filter(id__in=ids)
            .select_related("direction", "curator").order_by("course", "name"))


@role_required(Role.TEACHER)
def my_groups(request):
    ctx = _base(request)
    groups = list(_my_groups_qs(request.user))
    course = request.GET.get("course")
    if course:
        groups = [g for g in groups if str(g.course) == course]
    ctx.update({"active": "groups", "groups": groups,
                "courses": sorted({g.course for g in _my_groups_qs(request.user)}),
                "f_course": course})
    return render(request, "portal/teacher/groups.html", ctx)


@role_required(Role.TEACHER)
def group_detail(request, pk):
    from academics.models import AcademicGroup, StudentEnrollment
    from schedule.models import Lesson
    group = get_object_or_404(_my_groups_qs(request.user), pk=pk)
    students = (StudentEnrollment.objects.filter(group=group)
                .select_related("student").order_by("student__full_name"))
    # shu guruhga o'qituvchi o'qitadigan fanlar
    my_courses = _my_courses_qs(request.user).filter(
        curriculum__direction=group.direction)
    # shu guruh + shu o'qituvchi darslari
    lessons = (Lesson.objects.filter(teacher=request.user, groups=group)
               .select_related("course", "room", "timeslot").order_by("week_day", "timeslot__order"))
    ctx = _base(request)
    ctx.update({"active": "groups", "group": group, "students": students,
                "my_courses": my_courses, "lessons": lessons})
    return render(request, "portal/teacher/group_detail.html", ctx)


@role_required(Role.TEACHER)
def student_profile(request, pk):
    from academics.models import StudentEnrollment
    # o'qituvchi faqat o'z guruhlaridagi talabalarni ko'radi
    my_group_ids = list(_my_groups_qs(request.user).values_list("id", flat=True))
    enr = get_object_or_404(
        StudentEnrollment.objects.select_related("student", "direction", "academic_year", "group"),
        pk=pk, group_id__in=my_group_ids)
    ctx = _base(request)
    ctx.update({"active": "groups", "enr": enr, "student": enr.student})
    return render(request, "portal/teacher/student_profile.html", ctx)


# ==================== Dars jadvali (o'qituvchi, shaxsiy) ====================

@role_required(Role.TEACHER)
def my_schedule(request):
    from datetime import date
    from academics.models import AcademicYear
    from schedule.models import Lesson, TimeSlot
    ctx = _base(request)
    years = list(AcademicYear.objects.all())
    year_id = request.GET.get("year") or (years[0].pk if years else None)
    lessons = (Lesson.objects.filter(teacher=request.user, academic_year_id=year_id, is_active=True)
               .select_related("course", "room", "timeslot").prefetch_related("groups"))
    slots = list(TimeSlot.objects.filter(is_active=True))
    grid = {}
    for les in lessons:
        grid.setdefault((les.timeslot_id, les.week_day), []).append(les)
    rows = []
    for slot in slots:
        cells = [{"day": dv, "lessons": grid.get((slot.id, dv), [])}
                 for dv, dl in Lesson.WeekDay.choices]
        rows.append({"slot": slot, "cells": cells})
    # bugungi darslar (Dushanba=1 .. Shanba=6)
    today_wd = date.today().isoweekday()
    today_lessons = []
    if today_wd <= 6:
        today_lessons = sorted(
            [l for l in lessons if l.week_day == today_wd],
            key=lambda l: l.timeslot.order)
    ctx.update({"active": "schedule", "years": years,
                "year_id": int(year_id) if year_id else None,
                "days": Lesson.WeekDay.choices, "rows": rows,
                "today_lessons": today_lessons, "has_slots": bool(slots)})
    return render(request, "portal/teacher/schedule.html", ctx)


# ==================== Nazorat (o'qituvchi) ====================

@role_required(Role.TEACHER)
def assessment_center(request):
    from assessment.models import Quiz
    from teaching.models import Resource
    courses = list(_my_courses_qs(request.user))
    rows = []
    for c in courses:
        cts = list(c.control_types.all())
        quizzes = Quiz.objects.filter(
            teacher_assignment__teacher=request.user,
            teacher_assignment__department_course__course=c).distinct()
        cq = Resource.objects.filter(
            uploaded_by=request.user, kind=Resource.Kind.CONTROL_Q,
            links__teacher_assignment__department_course__course=c).distinct().count()
        rows.append({"course": c, "control_types": cts,
                     "total": sum(x.weight for x in cts),
                     "quizzes": quizzes, "control_q": cq})
    ctx = _base(request)
    ctx.update({"active": "control", "rows": rows})
    return render(request, "portal/teacher/control.html", ctx)


@role_required(Role.TEACHER)
def control_add(request, pk):
    from academics.models import ControlType
    course = _get_my_course(request.user, pk)
    name = (request.POST.get("name") or "").strip()
    try:
        weight = int(request.POST.get("weight") or 0)
    except ValueError:
        weight = 0
    if name:
        ControlType.objects.create(course=course, name=name, weight=weight,
                                   order=course.control_types.count() + 1)
        messages.success(request, "Nazorat turi qo‘shildi.")
    return redirect("portal:teacher_control")


@role_required(Role.TEACHER)
def control_delete(request, pk):
    from academics.models import ControlType
    ct = get_object_or_404(ControlType, pk=pk)
    # faqat o'z fanining nazorat turini o'chirish
    _get_my_course(request.user, ct.course_id)
    ct.delete()
    messages.success(request, "Nazorat turi o‘chirildi.")
    return redirect("portal:teacher_control")


# ==================== Xabarlar (o'qituvchi) ====================

@role_required(Role.TEACHER)
def messages_center(request):
    from core.models import Message
    from django.contrib.auth import get_user_model
    ctx = _base(request)
    tab = request.GET.get("tab", "incoming")
    incoming = (Message.objects.filter(recipient=request.user)
                .select_related("sender").order_by("-created_at"))
    if tab == "incoming":
        incoming.filter(is_read=False).update(is_read=True)
    sent = (Message.objects.filter(sender=request.user)
            .select_related("recipient").order_by("-created_at"))
    heads = get_user_model().objects.filter(roles__role=Role.DEPT_HEAD).distinct()
    ctx.update({"active": "messages", "tab": tab, "incoming": incoming,
                "sent": sent, "heads": heads})
    return render(request, "portal/teacher/messages.html", ctx)


@role_required(Role.TEACHER)
def message_send(request):
    from core.models import Message
    from django.contrib.auth import get_user_model
    recipient = get_object_or_404(get_user_model(), pk=request.POST.get("recipient"))
    body = (request.POST.get("body") or "").strip()
    if body:
        Message.objects.create(sender=request.user, recipient=recipient, body=body)
        notify(recipient, f"O‘qituvchidan xabar: {body[:60]}", reverse("portal:dashboard"))
        messages.success(request, "Xabar yuborildi.")
    return redirect("/zamdekan/oqituvchi/xabarlar/?tab=sent")


# ==================== Profil (o'qituvchi) ====================

@role_required(Role.TEACHER)
def profile(request):
    ctx = _base(request)
    user = request.user
    if request.method == "POST" and request.POST.get("form") == "info":
        for f in ["full_name", "phone", "email", "position", "academic_degree", "academic_title"]:
            setattr(user, f, request.POST.get(f, "").strip())
        user.save()
        messages.success(request, "Ma‘lumotlar saqlandi.")
        return redirect("portal:teacher_profile")
    if request.method == "POST" and request.POST.get("form") == "password":
        old = request.POST.get("old_password", "")
        new = request.POST.get("new_password", "")
        new2 = request.POST.get("new_password2", "")
        if not user.check_password(old):
            messages.error(request, "Joriy parol noto‘g‘ri.")
        elif len(new) < 6:
            messages.error(request, "Yangi parol kamida 6 belgidan iborat bo‘lsin.")
        elif new != new2:
            messages.error(request, "Yangi parollar mos kelmadi.")
        else:
            user.set_password(new); user.save()
            messages.success(request, "Parol yangilandi. Qayta kiring.")
            return redirect("accounts:logout")
    ctx.update({"active": "profile", "user_obj": user})
    return render(request, "portal/teacher/profile.html", ctx)
