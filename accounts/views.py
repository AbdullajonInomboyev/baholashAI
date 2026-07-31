from django.contrib.auth import logout
from django.contrib.auth.views import LoginView as BaseLoginView
from django.shortcuts import redirect


class LoginView(BaseLoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


def logout_view(request):
    logout(request)
    return redirect("accounts:login")


def switch_role(request, code):
    if request.user.is_authenticated and code in request.user.role_codes():
        request.session["active_role"] = code
    return redirect(request.META.get("HTTP_REFERER", "core:dashboard"))


from django.contrib import messages  # noqa: E402
from django.contrib.auth import update_session_auth_hash  # noqa: E402
from django.contrib.auth.decorators import login_required  # noqa: E402
from django.shortcuts import redirect, render  # noqa: E402

from .models import PasswordStatus  # noqa: E402


@login_required
def force_password_change(request):
    user = request.user
    if request.method == "POST":
        p1 = request.POST.get("password1") or ""
        p2 = request.POST.get("password2") or ""
        if len(p1) < 6:
            messages.error(request, "Parol kamida 6 belgidan iborat bo‘lsin.")
        elif p1 != p2:
            messages.error(request, "Parollar mos kelmadi.")
        else:
            user.set_password(p1)
            user.password_status = PasswordStatus.ACTIVE
            user.save(update_fields=["password", "password_status"])
            update_session_auth_hash(request, user)
            messages.success(request, "Parol o‘rnatildi.")
            return redirect("core:dashboard")
    return render(request, "accounts/force_password_change.html", {})
