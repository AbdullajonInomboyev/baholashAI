"""E'lon joylash — o'qituvchi, kafedra mudiri, zam dekan."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Role
from academics.models import Direction, AcademicGroup, Faculty
from core.models import Announcement
from .access import role_required, vice_dean_faculty, dept_head_departments


def _tgt(qs, pk):
    if not pk:
        return None
    try:
        return qs.filter(pk=int(pk)).first()
    except (ValueError, TypeError):
        return None


def _create_announcement(request, scope, title, body, faculty=None, direction=None, group=None):
    if not title or not body:
        messages.error(request, "Sarlavha va matnni kiriting.")
        return False
    Announcement.objects.create(
        author=request.user, title=title.strip(), body=body.strip(),
        scope=scope, faculty=faculty, direction=direction, group=group)
    messages.success(request, "E'lon joylandi.")
    return True


# ==================== O'qituvchi ====================

def _teacher_targets(user):
    from teaching.models import TeacherAssignment
    from schedule.models import Lesson
    dir_ids = (TeacherAssignment.objects.filter(teacher=user, status=TeacherAssignment.Status.ACTIVE)
               .values_list("department_course__course__curriculum__direction_id", flat=True))
    directions = Direction.objects.filter(id__in=list(dir_ids)).distinct()
    gids = set(AcademicGroup.objects.filter(curator=user).values_list("id", flat=True))
    gids |= set(Lesson.objects.filter(teacher=user).values_list("groups__id", flat=True))
    gids |= set(AcademicGroup.objects.filter(direction__in=directions).values_list("id", flat=True))
    gids.discard(None)
    groups = AcademicGroup.objects.filter(id__in=gids).distinct()
    return directions, groups


@role_required(Role.TEACHER)
def teacher_announce(request):
    directions, groups = _teacher_targets(request.user)
    if request.method == "POST":
        scope = request.POST.get("scope")
        title = request.POST.get("title", "")
        body = request.POST.get("body", "")
        direction = group = None
        if scope == "group":
            group = _tgt(groups, request.POST.get("target"))
        elif scope == "direction":
            direction = _tgt(directions, request.POST.get("target"))
        if _create_announcement(request, scope, title, body, direction=direction, group=group):
            return redirect("portal:teacher_announce")
    ctx = {"panel_title": "O‘qituvchi paneli",
           "panel_scope": request.user.full_name or request.user.username,
           "active": "announce", "directions": directions, "groups": groups,
           "mine": Announcement.objects.filter(author=request.user),
           "nav": "teacher"}
    return render(request, "portal/announce/create.html", ctx)


# ==================== Kafedra mudiri ====================

@role_required(Role.DEPT_HEAD)
def dept_announce(request):
    departments = list(dept_head_departments(request.user))
    dept = None
    if departments:
        pk = request.session.get("active_department")
        dept = next((d for d in departments if d.pk == pk), departments[0])
    directions = Direction.objects.filter(department=dept) if dept else Direction.objects.none()
    groups = AcademicGroup.objects.filter(direction__in=directions)
    if request.method == "POST":
        scope = request.POST.get("scope")
        direction = group = None
        if scope == "group":
            group = _tgt(groups, request.POST.get("target"))
        elif scope == "direction":
            direction = _tgt(directions, request.POST.get("target"))
        if _create_announcement(request, scope, request.POST.get("title", ""),
                                request.POST.get("body", ""), direction=direction, group=group):
            return redirect("portal:dept_announce")
    ctx = {"panel_title": "Kafedra mudiri paneli",
           "panel_scope": dept.name if dept else "—",
           "active": "announce", "directions": directions, "groups": groups,
           "mine": Announcement.objects.filter(author=request.user), "nav": "dept"}
    return render(request, "portal/announce/create.html", ctx)


# ==================== Zam dekan ====================

@role_required(Role.VICE_DEAN)
def vice_announce(request):
    faculty = vice_dean_faculty(request.user)
    directions = Direction.objects.filter(
        department__faculty=faculty) if faculty else Direction.objects.none()
    groups = AcademicGroup.objects.filter(direction__in=directions)
    if request.method == "POST":
        scope = request.POST.get("scope")
        fac = direction = group = None
        if scope == "faculty":
            fac = faculty
        elif scope == "direction":
            direction = _tgt(directions, request.POST.get("target"))
        elif scope == "group":
            group = _tgt(groups, request.POST.get("target"))
        if _create_announcement(request, scope, request.POST.get("title", ""),
                                request.POST.get("body", ""), faculty=fac,
                                direction=direction, group=group):
            return redirect("portal:vice_announce")
    ctx = {"panel_title": "Zam dekan paneli", "panel_scope": faculty.name if faculty else "—",
           "active": "announce", "directions": directions, "groups": groups,
           "allow_faculty": True, "allow_global": True,
           "mine": Announcement.objects.filter(author=request.user), "nav": "vice"}
    return render(request, "portal/announce/create.html", ctx)


@role_required(Role.TEACHER)
def announce_delete_teacher(request, pk):
    get_object_or_404(Announcement, pk=pk, author=request.user).delete()
    messages.success(request, "E'lon o‘chirildi.")
    return redirect("portal:teacher_announce")


@role_required(Role.DEPT_HEAD)
def announce_delete_dept(request, pk):
    get_object_or_404(Announcement, pk=pk, author=request.user).delete()
    messages.success(request, "E'lon o‘chirildi.")
    return redirect("portal:dept_announce")


@role_required(Role.VICE_DEAN)
def announce_delete_vice(request, pk):
    get_object_or_404(Announcement, pk=pk, author=request.user).delete()
    messages.success(request, "E'lon o‘chirildi.")
    return redirect("portal:vice_announce")
