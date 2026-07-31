"""Barcha rollar uchun umumiy sahifalar: bildirishnomalar va kalendar."""
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone

from academics.models import StudentEnrollment
from assessment.models import Assignment, Quiz


def _base(request):
    return {"panel_title": "Menyu",
            "panel_scope": request.user.full_name or request.user.username}


@login_required
def notifications(request):
    items = list(request.user.notifications.all()[:100])
    # ochilganda o'qilgan deb belgilaymiz
    request.user.notifications.filter(is_read=False).update(is_read=True)
    ctx = _base(request)
    ctx.update({"active": "notifications", "items": items})
    return render(request, "portal/common/notifications.html", ctx)


@login_required
def notification_open(request, pk):
    n = request.user.notifications.filter(pk=pk).first()
    if n:
        n.is_read = True
        n.save(update_fields=["is_read"])
        if n.url:
            return redirect(n.url)
    return redirect("portal:notifications")


@login_required
def calendar(request):
    user = request.user
    items = []

    # o'qituvchi sifatida
    for a in Assignment.objects.filter(teacher_assignment__teacher=user, due_date__isnull=False):
        items.append({"date": a.due_date, "title": a.title, "kind": "Topshiriq (o‘qituvchi)"})
    for q in Quiz.objects.filter(teacher_assignment__teacher=user, deadline__isnull=False):
        items.append({"date": q.deadline, "title": q.title, "kind": "Test (o‘qituvchi)"})

    # talaba sifatida
    enrollments = StudentEnrollment.objects.filter(student=user)
    filt = Q()
    for e in enrollments:
        filt |= Q(teacher_assignment__department_course__course__curriculum__direction=e.direction,
                  teacher_assignment__department_course__course__curriculum__study_form=e.study_form)
    if filt:
        for a in (Assignment.objects.filter(filt, due_date__isnull=False)
                  .exclude(status=Assignment.Status.DRAFT).distinct()):
            items.append({"date": a.due_date, "title": a.title, "kind": "Topshiriq"})
        for q in Quiz.objects.filter(filt, deadline__isnull=False, is_open=True).distinct():
            items.append({"date": q.deadline, "title": q.title, "kind": "Test"})

    today = timezone.localdate()
    seen = set()
    uniq = []
    for it in sorted(items, key=lambda x: x["date"]):
        k = (it["title"], it["date"], it["kind"])
        if k not in seen:
            seen.add(k)
            it["past"] = it["date"] < today
            uniq.append(it)
    upcoming = [i for i in uniq if not i["past"]]
    past = [i for i in uniq if i["past"]]

    ctx = _base(request)
    ctx.update({"active": "calendar", "upcoming": upcoming, "past": past, "today": today})
    return render(request, "portal/common/calendar.html", ctx)
