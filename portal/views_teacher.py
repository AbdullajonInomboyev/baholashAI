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
    ctx = _base(request)
    mine = _my_assignments(request.user)
    ctx.update({
        "active": "courses",
        "n_courses": mine.count(),
        "n_assignments": Assignment.objects.filter(teacher_assignment__in=mine).count(),
        "n_pending": Submission.objects.filter(
            assignment__teacher_assignment__in=mine, status=Submission.Status.AI_EVALUATED).count(),
        "n_resources": Resource.objects.filter(uploaded_by=request.user).count(),
    })
    return render(request, "portal/teacher/dashboard.html", ctx)


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
