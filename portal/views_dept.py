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


# ==================== O'qituvchilar (kafedra mudiri) ====================

@role_required(Role.DEPT_HEAD)
def teachers(request):
    departments, active_dept, ctx = _base(request)
    if not active_dept:
        return render(request, "portal/dept_head/teachers.html", ctx)
    assignments = (TeacherAssignment.objects
                   .filter(department_course__department=active_dept,
                           status=TeacherAssignment.Status.ACTIVE)
                   .select_related("teacher", "department_course__course"))
    rows = {}
    for a in assignments:
        t = a.teacher
        r = rows.setdefault(t.id, {"teacher": t, "courses": 0, "hours": 0, "resources": 0})
        r["courses"] += 1
        r["hours"] += a.department_course.course.total_hours or 0
    # har bir o'qituvchining shu kafedradagi resurslari soni
    for tid, r in rows.items():
        r["resources"] = Resource.objects.filter(
            uploaded_by_id=tid,
            links__teacher_assignment__department_course__department=active_dept).distinct().count()
    teachers = sorted(rows.values(), key=lambda x: (x["teacher"].full_name or x["teacher"].username))
    ctx.update({"active": "teachers", "teachers": teachers})
    return render(request, "portal/dept_head/teachers.html", ctx)


@role_required(Role.DEPT_HEAD)
def teacher_profile(request, pk):
    from assessment.models import Assignment, TeacherReview
    departments, active_dept, ctx = _base(request)
    teacher = get_object_or_404(User, pk=pk)
    assignments = (TeacherAssignment.objects
                   .filter(teacher=teacher, department_course__department=active_dept,
                           status=TeacherAssignment.Status.ACTIVE)
                   .select_related("department_course__course"))
    total_hours = sum(a.department_course.course.total_hours or 0 for a in assignments)
    resources = (Resource.objects
                 .filter(uploaded_by=teacher,
                         links__teacher_assignment__department_course__department=active_dept)
                 .distinct().select_related("review"))
    # faollik: yaratgan topshiriqlar, baholagan ishlar, yuklagan resurslar
    n_assignments = Assignment.objects.filter(
        teacher_assignment__teacher=teacher,
        teacher_assignment__department_course__department=active_dept).count()
    n_graded = TeacherReview.objects.filter(teacher=teacher).count()
    activity = {"assignments": n_assignments, "graded": n_graded, "resources": resources.count()}
    ctx.update({"active": "teachers", "teacher_obj": teacher, "assignments": assignments,
                "total_hours": total_hours, "resources": resources, "activity": activity})
    return render(request, "portal/dept_head/teacher_profile.html", ctx)


# ==================== O'quv rejalari (mudir tree) ====================

@role_required(Role.DEPT_HEAD)
def curricula(request):
    from academics.models import AcademicYear, Curriculum, Direction, StudyForm
    departments, dept, ctx = _base(request)
    tree = []
    if dept:
        directions = Direction.objects.filter(department=dept)
        study_form = request.GET.get("form", StudyForm.FULL_TIME)
        for y in AcademicYear.objects.filter(faculty=dept.faculty):
            dir_nodes = []
            for d in directions:
                cur = Curriculum.objects.filter(direction=d, academic_year=y,
                                                study_form=study_form).first()
                if not cur:
                    continue
                base = Course.objects.filter(curriculum=cur)
                sems = []
                for n in range(1, 9):
                    courses = list(base.filter(placements__semester__number=n).distinct())
                    if courses:
                        sems.append({"n": n, "courses": courses})
                dir_nodes.append({"dir": d, "total": base.count(), "sems": sems,
                                  "approved": cur.is_approved})
            if dir_nodes:
                tree.append({"year": y, "dirs": dir_nodes})
        ctx["study_form"] = study_form
        ctx["study_forms"] = StudyForm.choices
    ctx.update({"active": "curricula", "tree": tree})
    return render(request, "portal/dept_head/curricula.html", ctx)


@role_required(Role.DEPT_HEAD)
def course_program(request, pk):
    from assessment.models import Quiz
    departments, dept, ctx = _base(request)
    course = get_object_or_404(
        Course.objects.select_related("curriculum__direction", "curriculum__academic_year"),
        pk=pk, curriculum__direction__department=dept)
    dept_link = DepartmentCourse.objects.filter(department=dept, course=course).first()
    teachers = []
    if dept_link:
        teachers = [ta.teacher for ta in dept_link.teacher_assignments.filter(
            status=TeacherAssignment.Status.ACTIVE).select_related("teacher")]
    quizzes = Quiz.objects.filter(
        teacher_assignment__department_course__course=course).distinct()
    resource_links = (Resource.objects.none())
    from teaching.models import ResourceLink
    resource_links = (ResourceLink.objects
                      .filter(teacher_assignment__department_course__course=course)
                      .select_related("resource", "topic").distinct())
    ctx.update({"active": "curricula", "course": course, "dept_link": dept_link,
                "teachers": teachers, "topics": course.topics.all(),
                "literature": course.literature.all(),
                "control_types": course.control_types.all(),
                "control_total": sum(c.weight for c in course.control_types.all()),
                "quizzes": quizzes, "resource_links": resource_links,
                "placements": course.placements.select_related("semester")})
    return render(request, "portal/dept_head/course_program.html", ctx)


# ==================== Elektron resurslar workflow (mudir) ====================

@role_required(Role.DEPT_HEAD)
def resources_workflow(request):
    departments, dept, ctx = _base(request)
    qs = (Resource.objects.none())
    counts = {}
    if dept:
        qs = (Resource.objects
              .filter(links__teacher_assignment__department_course__department=dept)
              .distinct().select_related("uploaded_by", "review")
              .prefetch_related("links__teacher_assignment__department_course__course"))
        status = request.GET.get("status", "new")
        counts = {s: qs.filter(dept_status=s).count() for s, _ in Resource.DeptStatus.choices}
        if status in dict(Resource.DeptStatus.choices):
            qs = qs.filter(dept_status=status)
        ctx["f_status"] = status
    ctx.update({"active": "eresources", "resources": qs,
                "statuses": Resource.DeptStatus.choices, "counts": counts})
    return render(request, "portal/dept_head/resources_workflow.html", ctx)


def _dept_res_action(request, pk, status, note_field="dept_note"):
    from core.notifications import notify
    from django.urls import reverse
    departments, dept, _ = _base(request)
    r = get_object_or_404(
        Resource.objects.filter(
            links__teacher_assignment__department_course__department=dept).distinct(), pk=pk)
    r.dept_status = status
    note = request.POST.get("note", "").strip()
    if note:
        r.dept_note = note
    r.save(update_fields=["dept_status", "dept_note"])
    return r, note


@role_required(Role.DEPT_HEAD)
def resource_dept_approve(request, pk):
    _dept_res_action(request, pk, Resource.DeptStatus.APPROVED)
    messages.success(request, "Resurs kafedra tomonidan tasdiqlandi.")
    return redirect(request.META.get("HTTP_REFERER", "portal:dept_eresources"))


@role_required(Role.DEPT_HEAD)
def resource_dept_return(request, pk):
    from core.notifications import notify
    from django.urls import reverse
    r, note = _dept_res_action(request, pk, Resource.DeptStatus.RETURNED)
    notify(r.uploaded_by, f"«{r.title}» resursi tuzatishga qaytarildi"
           + (f": {note}" if note else ""), reverse("portal:teacher_resources"))
    messages.success(request, "Resurs o‘qituvchiga tuzatishga qaytarildi.")
    return redirect(request.META.get("HTTP_REFERER", "portal:dept_eresources"))


@role_required(Role.DEPT_HEAD)
def resource_dept_forward(request, pk):
    r, _ = _dept_res_action(request, pk, Resource.DeptStatus.FORWARDED)
    # Zam dekan navbatiga tushishi uchun tasdiq holatini 'kutilmoqda' qilamiz
    r.approval_status = Resource.ApprovalStatus.PENDING
    r.save(update_fields=["approval_status"])
    messages.success(request, "Resurs Zam dekanga yuborildi.")
    return redirect(request.META.get("HTTP_REFERER", "portal:dept_eresources"))


@role_required(Role.DEPT_HEAD)
def resource_dept_archive(request, pk):
    _dept_res_action(request, pk, Resource.DeptStatus.ARCHIVED)
    messages.success(request, "Resurs arxivlandi.")
    return redirect(request.META.get("HTTP_REFERER", "portal:dept_eresources"))


# ==================== Dars jadvali (mudir ko'rinishi, faqat o'qish) ====================

@role_required(Role.DEPT_HEAD)
def schedule_view(request):
    from academics.models import AcademicGroup, AcademicYear
    from schedule.models import Lesson, TimeSlot, Room
    departments, dept, ctx = _base(request)
    rows, groups, teachers, rooms, years = [], [], [], [], []
    year_id = obj_id = None
    view_by = request.GET.get("by", "group")
    if dept:
        years = list(AcademicYear.objects.filter(faculty=dept.faculty))
        year_id = request.GET.get("year") or (years[0].pk if years else None)
        groups = AcademicGroup.objects.filter(direction__department=dept)
        teacher_ids = (TeacherAssignment.objects
                       .filter(department_course__department=dept,
                               status=TeacherAssignment.Status.ACTIVE)
                       .values_list("teacher_id", flat=True).distinct())
        teachers = User.objects.filter(id__in=teacher_ids)
        rooms = Room.objects.all()
        obj_id = request.GET.get("id")

        lessons = (Lesson.objects.filter(academic_year_id=year_id, is_active=True)
                   .select_related("course", "teacher", "room", "timeslot")
                   .prefetch_related("groups"))
        if view_by == "group" and obj_id:
            lessons = lessons.filter(groups__id=obj_id)
        elif view_by == "teacher" and obj_id:
            lessons = lessons.filter(teacher_id=obj_id)
        elif view_by == "room" and obj_id:
            lessons = lessons.filter(room_id=obj_id)
        else:
            # standart: kafedra guruhlari bo'yicha
            lessons = lessons.filter(groups__in=groups)

        slots = list(TimeSlot.objects.filter(is_active=True))
        grid = {}
        for les in lessons.distinct():
            grid.setdefault((les.timeslot_id, les.week_day), []).append(les)
        for slot in slots:
            cells = [{"day": dv, "lessons": grid.get((slot.id, dv), [])}
                     for dv, dl in Lesson.WeekDay.choices]
            rows.append({"slot": slot, "cells": cells})
    ctx.update({"active": "schedule", "years": years,
                "year_id": int(year_id) if year_id else None,
                "view_by": view_by, "obj_id": int(obj_id) if obj_id else None,
                "groups": groups, "teachers": teachers, "rooms": rooms,
                "days": Lesson.WeekDay.choices,
                "rows": rows})
    return render(request, "portal/dept_head/schedule.html", ctx)


# ==================== Hisobotlar (mudir) ====================

@role_required(Role.DEPT_HEAD)
def reports(request):
    departments, dept, ctx = _base(request)
    stats = {}
    if dept:
        from academics.models import Direction
        n_courses = DepartmentCourse.objects.filter(department=dept).count()
        teacher_ids = (TeacherAssignment.objects
                       .filter(department_course__department=dept,
                               status=TeacherAssignment.Status.ACTIVE)
                       .values_list("teacher_id", flat=True).distinct())
        n_resources = Resource.objects.filter(
            links__teacher_assignment__department_course__department=dept).distinct().count()
        total_hours = sum(
            (dc.course.total_hours or 0)
            for dc in DepartmentCourse.objects.filter(department=dept).select_related("course"))
        stats = {"courses": n_courses, "teachers": len(teacher_ids),
                 "resources": n_resources, "directions": Direction.objects.filter(department=dept).count(),
                 "hours": total_hours}
    ctx.update({"active": "reports", "stats": stats})
    return render(request, "portal/dept_head/reports.html", ctx)


@role_required(Role.DEPT_HEAD)
def report_excel(request):
    from django.http import HttpResponse
    from portal.services.reports import department_report
    departments, dept, _ = _base(request)
    data = department_report(dept)
    resp = HttpResponse(data, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = 'attachment; filename="kafedra_hisoboti.xlsx"'
    return resp


@role_required(Role.DEPT_HEAD)
def report_pdf(request):
    from django.http import HttpResponse
    from portal.services.reports import department_report_pdf
    departments, dept, _ = _base(request)
    data = department_report_pdf(dept)
    resp = HttpResponse(data, content_type="application/pdf")
    resp["Content-Disposition"] = 'attachment; filename="kafedra_hisoboti.pdf"'
    return resp


# ==================== Xabarlar (mudir) ====================

@role_required(Role.DEPT_HEAD)
def messages_center(request):
    from core.models import Message
    departments, dept, ctx = _base(request)
    tab = request.GET.get("tab", "incoming")
    incoming = ReviewRemark.objects.none()
    sent = Message.objects.none()
    dept_teachers = []
    if dept:
        incoming = (ReviewRemark.objects.filter(department=dept)
                    .select_related("author").order_by("-created_at"))
        sent = (Message.objects.filter(sender=request.user)
                .select_related("recipient").order_by("-created_at"))
        teacher_ids = (TeacherAssignment.objects
                       .filter(department_course__department=dept,
                               status=TeacherAssignment.Status.ACTIVE)
                       .values_list("teacher_id", flat=True).distinct())
        dept_teachers = User.objects.filter(id__in=teacher_ids)
    ctx.update({"active": "messages", "tab": tab, "incoming": incoming,
                "sent": sent, "dept_teachers": dept_teachers})
    return render(request, "portal/dept_head/messages.html", ctx)


@role_required(Role.DEPT_HEAD)
def message_send(request):
    from core.models import Message
    from core.notifications import notify
    from django.urls import reverse
    departments, dept, _ = _base(request)
    recipient = get_object_or_404(User, pk=request.POST.get("recipient"))
    body = (request.POST.get("body") or "").strip()
    if body:
        Message.objects.create(sender=request.user, recipient=recipient, body=body)
        notify(recipient, f"Kafedra mudiridan xabar: {body[:60]}",
               reverse("portal:dashboard"))
        messages.success(request, "Xabar yuborildi.")
    return redirect("/zamdekan/kafedra/xabarlar/?tab=sent")


# ==================== Profil (mudir) ====================

@role_required(Role.DEPT_HEAD)
def profile(request):
    departments, dept, ctx = _base(request)
    user = request.user
    pw_error = pw_ok = None
    if request.method == "POST" and request.POST.get("form") == "info":
        user.full_name = request.POST.get("full_name", "").strip()
        user.phone = request.POST.get("phone", "").strip()
        user.email = request.POST.get("email", "").strip()
        user.save(update_fields=["full_name", "phone", "email"])
        messages.success(request, "Ma‘lumotlar saqlandi.")
        return redirect("portal:dept_profile")
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
            user.set_password(new)
            user.save()
            messages.success(request, "Parol yangilandi. Qayta kiring.")
            return redirect("accounts:logout")
    ctx.update({"active": "profile", "user_obj": user})
    return render(request, "portal/dept_head/profile.html", ctx)
