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
