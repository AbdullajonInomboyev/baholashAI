from core.models import AuditLog


def log_action(user, action, entity, entity_id, *, old=None, new=None):
    AuditLog.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        action=action, entity=entity, entity_id=str(entity_id),
        old_value=old, new_value=new,
    )
