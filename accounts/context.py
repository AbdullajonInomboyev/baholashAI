from accounts.models import Role


def active_role(request):
    """Shablonlarda joriy faol rolni ko‘rsatish uchun.
    Multi-rolli foydalanuvchi sessiyada rolini almashtiradi."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"active_role": None, "available_roles": []}

    codes = user.role_codes()
    current = request.session.get("active_role")
    if current not in codes:
        current = codes[0] if codes else None

    labels = dict(Role.choices)
    return {
        "active_role": current,
        "active_role_label": labels.get(current, ""),
        "available_roles": [(code, labels.get(code, code)) for code in codes],
    }
