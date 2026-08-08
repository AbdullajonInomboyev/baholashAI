from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from academics.models import StudentEnrollment
from accounts.models import Role
from assessment.models import Assignment, Submission
from assessment.services import ai

from .access import role_required
from .forms import SubmissionForm


def _base(request):
    return {"panel_title": "Talaba paneli",
            "panel_scope": request.user.full_name or request.user.username}


def _my_enrollments(user):
    return StudentEnrollment.objects.filter(student=user).select_related("direction", "academic_year")


def _visible_assignments(user):
    """Talaba o‘qiydigan yo‘nalish va ta‘lim shakliga mos, e‘lon qilingan topshiriqlar."""
    enrollments = _my_enrollments(user)
    filters = Q()
    for e in enrollments:
        filters |= Q(
            teacher_assignment__department_course__course__curriculum__direction=e.direction,
            teacher_assignment__department_course__course__curriculum__study_form=e.study_form)
    if not filters:
        return Assignment.objects.none()
    return (Assignment.objects
            .filter(filters)
            .exclude(status=Assignment.Status.DRAFT)
            .select_related("assignment_type", "teacher_assignment__department_course__course")
            .distinct())


@role_required(Role.STUDENT)
def dashboard(request):
    ctx = _base(request)
    visible = _visible_assignments(request.user)
    submitted_ids = set(Submission.objects.filter(student=request.user).values_list("assignment_id", flat=True))
    ctx.update({
        "active": "assignments",
        "n_assignments": visible.count(),
        "n_submitted": len(submitted_ids),
        "n_todo": visible.exclude(pk__in=submitted_ids).count(),
        "enrollments": _my_enrollments(request.user),
    })
    return render(request, "portal/student/dashboard.html", ctx)


@role_required(Role.STUDENT)
def assignments(request):
    ctx = _base(request)
    visible = _visible_assignments(request.user).order_by("-created_at")
    subs = {s.assignment_id: s for s in Submission.objects.filter(student=request.user)}
    rows = [(a, subs.get(a.pk)) for a in visible]
    ctx.update({"active": "assignments", "rows": rows})
    return render(request, "portal/student/assignments.html", ctx)


@role_required(Role.STUDENT)
def assignment_detail(request, pk):
    ctx = _base(request)
    assignment = get_object_or_404(_visible_assignments(request.user), pk=pk)
    submission = Submission.objects.filter(assignment=assignment, student=request.user).first()
    ctx.update({"active": "assignments", "assignment": assignment,
                "submission": submission, "form": SubmissionForm()})
    return render(request, "portal/student/assignment_detail.html", ctx)


@role_required(Role.STUDENT)
def submit(request, pk):
    assignment = get_object_or_404(_visible_assignments(request.user), pk=pk)
    if assignment.status == Assignment.Status.CLOSED:
        messages.error(request, "Topshiriq yopilgan.")
        return redirect("portal:student_assignment_detail", pk=pk)
    form = SubmissionForm(request.POST, request.FILES)
    if form.is_valid():
        submission, _ = Submission.objects.update_or_create(
            assignment=assignment, student=request.user,
            defaults={"file": form.cleaned_data.get("file"),
                      "text_answer": form.cleaned_data.get("text_answer", ""),
                      "status": Submission.Status.SUBMITTED})
        # topshirilishi bilan AI baholaydi
        ai.evaluate_submission(submission)
        messages.success(request, "Ish topshirildi va AI baholadi.")
    else:
        messages.error(request, form.errors.get("__all__", ["Ma‘lumot kiritilmadi."])[0])
    return redirect("portal:student_assignment_detail", pk=pk)


@role_required(Role.STUDENT)
def grades(request):
    ctx = _base(request)
    subs = (Submission.objects.filter(student=request.user)
            .select_related("assignment__assignment_type", "ai_evaluation", "teacher_review")
            .prefetch_related("criterion_scores__criterion")
            .order_by("-created_at"))
    ctx.update({"active": "grades", "submissions": subs})
    return render(request, "portal/student/grades.html", ctx)


@role_required(Role.STUDENT)
def materials(request):
    from teaching.models import ResourceLink
    enrollments = _my_enrollments(request.user)
    filt = Q()
    for e in enrollments:
        filt |= Q(teacher_assignment__department_course__course__curriculum__direction=e.direction,
                  teacher_assignment__department_course__course__curriculum__study_form=e.study_form)
    groups = {}
    if filt:
        links = (ResourceLink.objects.filter(filt)
                 .select_related("resource", "topic",
                                 "teacher_assignment__department_course__course")
                 .order_by("teacher_assignment__department_course__course__code"))
        for l in links:
            course = l.teacher_assignment.department_course.course
            groups.setdefault(course, []).append(l)
    ctx = _base(request)
    ctx.update({"active": "materials", "groups": list(groups.items())})
    return render(request, "portal/student/materials.html", ctx)


# ==================== Mening fanlarim (talaba: tree + fan ichi) ====================

def _my_courses_qs(user):
    from academics.models import Course
    filters = Q()
    for e in _my_enrollments(user):
        filters |= Q(curriculum__direction=e.direction,
                     curriculum__academic_year=e.academic_year,
                     curriculum__study_form=e.study_form)
    if not filters:
        return Course.objects.none()
    return (Course.objects.filter(filters)
            .select_related("curriculum__direction", "curriculum__academic_year").distinct())


def _get_my_course(user, pk):
    from academics.models import Course
    return get_object_or_404(_my_courses_qs(user), pk=pk)


@role_required(Role.STUDENT)
def my_courses(request):
    ctx = _base(request)
    courses = list(_my_courses_qs(request.user))
    years = {}
    for c in courses:
        y = c.curriculum.academic_year
        yn = years.setdefault(y.id, {"year": y, "sems": {}})
        placed = False
        for pl in c.placements.select_related("semester"):
            yn["sems"].setdefault(pl.semester.number, []).append(c)
            placed = True
        if not placed:
            yn["sems"].setdefault(0, []).append(c)
    tree = []
    for yn in sorted(years.values(), key=lambda x: x["year"].title, reverse=True):
        sems = [{"n": n, "courses": cs} for n, cs in sorted(yn["sems"].items())]
        tree.append({"year": yn["year"], "sems": sems})
    ctx.update({"active": "mycourses", "tree": tree, "n_courses": len(courses)})
    return render(request, "portal/student/my_courses.html", ctx)


@role_required(Role.STUDENT)
def course_view(request, pk):
    from teaching.models import Resource, ResourceLink, TeacherAssignment
    from assessment.models import Quiz, CriterionScore, TeacherReview
    course = _get_my_course(request.user, pk)
    # o'qituvchi(lar)
    teachers = [ta.teacher for ta in TeacherAssignment.objects.filter(
        department_course__course=course, status=TeacherAssignment.Status.ACTIVE).select_related("teacher")]
    # materiallar (faqat tasdiqlangan resurslar), tur bo'yicha guruhlangan
    links = (ResourceLink.objects
             .filter(teacher_assignment__department_course__course=course,
                     resource__approval_status="approved")
             .select_related("resource", "topic").distinct())
    materials = {}
    for l in links:
        materials.setdefault(l.resource.get_kind_display(), []).append(l)
    # topshiriqlar (shu fan)
    my_assignments = _visible_assignments(request.user).filter(
        teacher_assignment__department_course__course=course)
    # testlar
    quizzes = Quiz.objects.filter(
        teacher_assignment__department_course__course=course, is_open=True).distinct()
    # baholar (shu fan topshiriqlari bo'yicha)
    my_subs = Submission.objects.filter(
        student=request.user, assignment__teacher_assignment__department_course__course=course
    ).select_related("assignment", "ai_evaluation", "teacher_review")
    try:
        syllabus = course.syllabus
    except Exception:
        syllabus = None
    ctx = _base(request)
    ctx.update({"active": "mycourses", "course": course, "teachers": teachers,
                "materials": materials, "topics": course.topics.all(),
                "literature": course.literature.all(), "syllabus": syllabus,
                "assignments": my_assignments, "quizzes": quizzes, "subs": my_subs,
                "placements": course.placements.select_related("semester"),
                "control_types": course.control_types.all()})
    return render(request, "portal/student/course_view.html", ctx)
