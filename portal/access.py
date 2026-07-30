from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from accounts.models import Role


def _active_role(request):
    codes = request.user.role_codes()
    current = request.session.get("active_role")
    return current if current in codes else (codes[0] if codes else None)


def role_required(role):
    """Faol roli mos kelmasa — kirishni rad etadi."""

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not request.user.has_role(role):
                raise PermissionDenied
            request.active_role = role
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def vice_dean_faculty(user):
    """Zam dekanning fakulteti (birinchi mos scope)."""
    link = user.roles.filter(role=Role.VICE_DEAN, faculty__isnull=False).select_related("faculty").first()
    return link.faculty if link else None


def dept_head_departments(user):
    """Foydalanuvchi mudir bo‘lgan kafedralar."""
    from academics.models import Department
    ids = (user.roles.filter(role=Role.DEPT_HEAD, department__isnull=False)
           .values_list("department_id", flat=True))
    return Department.objects.filter(id__in=ids).select_related("faculty")
