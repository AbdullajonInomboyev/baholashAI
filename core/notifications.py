"""Bildirishnoma yaratish yordamchilari."""
from core.models import Notification


def notify(user, message, url=""):
    if user is not None:
        Notification.objects.create(user=user, message=message, url=url)


def notify_many(users, message, url=""):
    items = [Notification(user=u, message=message, url=url) for u in users if u is not None]
    if items:
        Notification.objects.bulk_create(items)
