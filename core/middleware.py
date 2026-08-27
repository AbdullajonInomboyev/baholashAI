import threading

_state = threading.local()


def get_current_user():
    return getattr(_state, "user", None)


class CurrentUserMiddleware:
    """Audit yozuvlari uchun joriy foydalanuvchini oqim (thread) darajasida saqlaydi."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _state.user = getattr(request, "user", None)
        try:
            return self.get_response(request)
        finally:
            _state.user = None


class GuestRestrictMiddleware:
    """Mehmon (bir martalik test) foydalanuvchisini FAQAT o'z testiga cheklaydi."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and getattr(user, "is_guest", False):
            path = request.path
            allowed_prefixes = ("/zamdekan/talaba/testlar/", "/zamdekan/a11y/",
                                "/hisob/chiqish/", "/static/", "/media/")
            if path != "/" and not path.startswith(allowed_prefixes):
                from django.shortcuts import redirect
                return redirect("core:dashboard")
        return self.get_response(request)


class ForcePasswordChangeMiddleware:
    """Vaqtinchalik parolli foydalanuvchini majburan parol o'zgartirishga yo'naltiradi."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        must_change = getattr(user, "must_change_password", False)
        if callable(must_change):
            must_change = must_change()
        if user is not None and user.is_authenticated and must_change:
            path = request.path
            allowed = ("/hisob/parol-almashtirish/", "/hisob/chiqish/")
            if not path.startswith("/admin/") and not path.startswith(allowed) and not path.startswith("/static/"):
                from django.shortcuts import redirect
                return redirect("accounts:force_password_change")
        return self.get_response(request)
