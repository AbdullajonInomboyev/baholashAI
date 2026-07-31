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
            .order_by("-created_at"))
    ctx.update({"active": "grades", "submissions": subs})
    return render(request, "portal/student/grades.html", ctx)
