from django.contrib import messages
from django.core.files.base import ContentFile
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Role
from assessment.models import (
    Assignment, AssignmentType, Submission, TeacherReview,
)
from assessment.services import ai
from core.audit import log_action
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
        assignment.teacher_assignment = ta
        assignment.save()
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
        log_action(request.user, "review_override", "Submission", submission.pk,
                   old={"ai_score": str(old)}, new={"final": str(form.cleaned_data["final_score"])})
        messages.success(request, "Yakuniy baho o‘zgartirildi.")
    else:
        messages.error(request, "Baho noto‘g‘ri.")
    return redirect("portal:teacher_submissions", assignment_pk=submission.assignment_id)


@role_required(Role.TEACHER)
def resources(request):
    ctx = _base(request)
    ctx.update({"active": "resources",
                "resources": Resource.objects.filter(uploaded_by=request.user)
                .select_related("review").prefetch_related("links__teacher_assignment__department_course__course"),
                "form": ResourceUploadForm(teacher_assignments=_my_assignments(request.user))})
    return render(request, "portal/teacher/resources.html", ctx)


@role_required(Role.TEACHER)
def resource_upload(request):
    mine = _my_assignments(request.user)
    form = ResourceUploadForm(request.POST, request.FILES, teacher_assignments=mine)
    if form.is_valid():
        resource = Resource.objects.create(
            uploaded_by=request.user, title=form.cleaned_data["title"],
            kind=form.cleaned_data["kind"], file=form.cleaned_data["file"])
        for ta_id in form.cleaned_data["assignments"]:
            ResourceLink.objects.get_or_create(resource=resource, teacher_assignment_id=int(ta_id))
        # yuklanishi bilan AI tahlili avtomatik shakllanadi
        ai.review_resource(resource)
        messages.success(request, "Resurs yuklandi va AI tahliliga yuborildi.")
    else:
        messages.error(request, "Ma‘lumot to‘liq emas (fayl va kamida bitta fan tanlang).")
    return redirect("portal:teacher_resources")


def _get_submission(request, submission_pk):
    mine = _my_assignments(request.user)
    return get_object_or_404(
        Submission.objects.select_related("assignment", "ai_evaluation"),
        pk=submission_pk, assignment__teacher_assignment__in=mine)
