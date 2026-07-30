from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from academics.models import Course, StudyForm
from accounts.models import Role
from core.audit import log_action
from core.models import ReviewRemark
from teaching.models import (
    DepartmentCourse, Resource, ResourceReview, TeacherAssignment,
)

from .access import dept_head_departments, role_required

User = get_user_model()
LOW_QUALITY = 80  # shu foizdan past ballar "ishkal" deb belgilanadi


def _base(request):
    departments = list(dept_head_departments(request.user))
    active_dept = None
    if departments:
        pk = request.session.get("active_department")
        active_dept = next((d for d in departments if d.pk == pk), departments[0])
    ctx = {"panel_title": "Kafedra mudiri paneli",
           "panel_scope": active_dept.name if active_dept else "Kafedra biriktirilmagan",
           "departments": departments, "active_dept": active_dept}
    return departments, active_dept, ctx


@role_required(Role.DEPT_HEAD)
def switch_department(request, pk):
    if dept_head_departments(request.user).filter(pk=pk).exists():
        request.session["active_department"] = pk
    return redirect(request.META.get("HTTP_REFERER", "portal:dept_dashboard"))


@role_required(Role.DEPT_HEAD)
def dashboard(request):
    departments, dept, ctx = _base(request)
    if not dept:
        return render(request, "portal/dept_head/no_department.html", ctx)
    links = DepartmentCourse.objects.filter(department=dept)
    reviews = ResourceReview.objects.filter(
        resource__links__teacher_assignment__department_course__department=dept)
    ctx.update({
        "active": "dashboard",
        "n_courses": links.count(),
        "n_teachers": TeacherAssignment.objects.filter(
            department_course__department=dept, status=TeacherAssignment.Status.ACTIVE
        ).values("teacher").distinct().count(),
        "n_resources": reviews.count(),
        "n_low": reviews.filter(status=ResourceReview.Status.COMPLETED,
                                match_score__lt=LOW_QUALITY).count(),
        "open_remarks": ReviewRemark.objects.filter(
            target=request.user, department=dept, status=ReviewRemark.Status.OPEN).count(),
    })
    return render(request, "portal/dept_head/dashboard.html", ctx)


# ---- Kafedra fanlari ----
@role_required(Role.DEPT_HEAD)
def courses(request):
    departments, dept, ctx = _base(request)
    links = (DepartmentCourse.objects.filter(department=dept)
             .select_related("course", "course__curriculum__direction")
             .annotate(n_teachers=Count(
                 "teacher_assignments",
                 filter=Q(teacher_assignments__status=TeacherAssignment.Status.ACTIVE))))
    ctx.update({"active": "courses", "links": links})
    return render(request, "portal/dept_head/courses.html", ctx)


@role_required(Role.DEPT_HEAD)
def course_browser(request):
    """Barcha fanlarni qidirib, o‘z kafedrasiga biriktirish (boshqa fakultet ham)."""
    departments, dept, ctx = _base(request)
    q = request.GET.get("q", "").strip()
    qs = Course.objects.select_related("curriculum__direction").order_by("code")
    if q:
        qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q))
    else:
        qs = qs.none()
    linked_ids = set(DepartmentCourse.objects.filter(department=dept).values_list("course_id", flat=True))
    ctx.update({"active": "courses", "results": qs[:100], "q": q, "linked_ids": linked_ids})
    return render(request, "portal/dept_head/course_browser.html", ctx)


@role_required(Role.DEPT_HEAD)
def course_pull(request, course_pk):
    departments, dept, _ = _base(request)
    course = get_object_or_404(Course, pk=course_pk)
    DepartmentCourse.objects.get_or_create(
        department=dept, course=course, defaults={"assigned_by": request.user})
    messages.success(request, f"{course.code} kafedraga biriktirildi.")
    return redirect("portal:dept_course_teachers", pk=DepartmentCourse.objects.get(
        department=dept, course=course).pk)


@role_required(Role.DEPT_HEAD)
def course_teachers(request, pk):
    departments, dept, ctx = _base(request)
    link = get_object_or_404(
        DepartmentCourse.objects.select_related("course"), pk=pk, department=dept)
    assignments = link.teacher_assignments.select_related("teacher").order_by("-status")
    assigned_ids = set(a.teacher_id for a in assignments if a.status == TeacherAssignment.Status.ACTIVE)
    teachers = (User.objects.filter(roles__role=Role.TEACHER).distinct()
                .order_by("full_name"))
    ctx.update({"active": "courses", "link": link, "assignments": assignments,
                "teachers": teachers, "assigned_ids": assigned_ids})
    return render(request, "portal/dept_head/course_teachers.html", ctx)


@role_required(Role.DEPT_HEAD)
def teacher_assign(request, pk):
    departments, dept, _ = _base(request)
    link = get_object_or_404(DepartmentCourse, pk=pk, department=dept)
    teacher = get_object_or_404(User, pk=request.POST.get("teacher"))
    ta, created = TeacherAssignment.objects.get_or_create(
        department_course=link, teacher=teacher,
        defaults={"assigned_by": request.user})
    if not created and ta.status != TeacherAssignment.Status.ACTIVE:
        ta.status = TeacherAssignment.Status.ACTIVE
        ta.save(update_fields=["status"])
    log_action(request.user, "assign_teacher", "TeacherAssignment", ta.pk)
    messages.success(request, f"{teacher} biriktirildi.")
    return redirect("portal:dept_course_teachers", pk=pk)


@role_required(Role.DEPT_HEAD)
def teacher_remove(request, pk, ta_pk):
    departments, dept, _ = _base(request)
    get_object_or_404(DepartmentCourse, pk=pk, department=dept)
    ta = get_object_or_404(TeacherAssignment, pk=ta_pk, department_course_id=pk)
    ta.status = TeacherAssignment.Status.REMOVED
    ta.save(update_fields=["status"])
    messages.success(request, "O‘qituvchi olib tashlandi.")
    return redirect("portal:dept_course_teachers", pk=pk)


# ---- Resurs sifati (AI) ----
@role_required(Role.DEPT_HEAD)
def resources(request):
    departments, dept, ctx = _base(request)
    reviews = (ResourceReview.objects
               .filter(resource__links__teacher_assignment__department_course__department=dept)
               .select_related("resource", "resource__uploaded_by", "ai_model")
               .distinct())
    teacher_id = request.GET.get("teacher")
    course_id = request.GET.get("course")
    only_low = request.GET.get("low") == "1"
    if teacher_id:
        reviews = reviews.filter(resource__uploaded_by_id=teacher_id)
    if course_id:
        reviews = reviews.filter(
            resource__links__teacher_assignment__department_course__course_id=course_id)
    if only_low:
        reviews = reviews.filter(status=ResourceReview.Status.COMPLETED, match_score__lt=LOW_QUALITY)

    teachers = (User.objects
                .filter(resources__links__teacher_assignment__department_course__department=dept)
                .distinct().order_by("full_name"))
    dept_courses = (Course.objects
                    .filter(department_links__department=dept).distinct().order_by("code"))
    ctx.update({"active": "resources", "reviews": reviews.order_by("match_score"),
                "teachers": teachers, "dept_courses": dept_courses,
                "f_teacher": teacher_id, "f_course": course_id, "only_low": only_low,
                "low_threshold": LOW_QUALITY})
    return render(request, "portal/dept_head/resources.html", ctx)


@role_required(Role.DEPT_HEAD)
def resource_detail(request, pk):
    departments, dept, ctx = _base(request)
    review = get_object_or_404(
        ResourceReview.objects.select_related("resource", "resource__uploaded_by", "ai_model"),
        pk=pk,
        resource__links__teacher_assignment__department_course__department=dept)
    linked_courses = (Course.objects
                      .filter(department_links__teacher_assignments__resource_links__resource=review.resource)
                      .distinct())
    ctx.update({"active": "resources", "review": review, "linked_courses": linked_courses})
    return render(request, "portal/dept_head/resource_detail.html", ctx)


# ---- Izohlar (zam dekandan) ----
@role_required(Role.DEPT_HEAD)
def remarks(request):
    departments, dept, ctx = _base(request)
    items = (ReviewRemark.objects.filter(target=request.user)
             .select_related("author", "department", "course", "resource").order_by("status", "-created_at"))
    ctx.update({"active": "remarks", "remarks": items})
    return render(request, "portal/dept_head/remarks.html", ctx)


@role_required(Role.DEPT_HEAD)
def remark_resolve(request, pk):
    remark = get_object_or_404(ReviewRemark, pk=pk, target=request.user)
    if request.method == "POST":
        remark.status = ReviewRemark.Status.RESOLVED
        remark.resolved_at = timezone.now()
        remark.save(update_fields=["status", "resolved_at"])
        messages.success(request, "Izoh hal qilingan deb belgilandi.")
    return redirect("portal:dept_remarks")
