from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from accounts.models import Role


@login_required
def dashboard(request):
    codes = request.user.role_codes()
    active = request.session.get("active_role")
    active = active if active in codes else (codes[0] if codes else None)
    if active == Role.VICE_DEAN:
        return redirect("portal:dashboard")
    if active == Role.DEPT_HEAD:
        return redirect("portal:dept_dashboard")
    if active == Role.TEACHER:
        return redirect("portal:teacher_dashboard")
    if active == Role.STUDENT:
        return redirect("portal:student_dashboard")
    return render(request, "core/dashboard.html")
