from __future__ import annotations

from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def ensure_groups_and_permissions(sender, **kwargs):
    if not apps.is_installed("django.contrib.auth"):
        return

    Group.objects.get_or_create(name="HR")
    hr_admin_group, _ = Group.objects.get_or_create(name="HR_ADMIN")

    # Права для админки (HR_ADMIN). Группа HR (приложение) в админку не пускается.
    wanted = [
        ("analytics_app", "hrdataset", ["view", "add", "change", "delete"]),
        ("analytics_app", "usersessionupload", ["view", "add", "change", "delete"]),
        ("analytics_app", "csvreport", ["view", "add", "change", "delete"]),
        ("auth", "user", ["view", "add", "change"]),
        ("auth", "group", ["view", "add", "change"]),
    ]

    perms: list[Permission] = []
    for app_label, model, actions in wanted:
        try:
            ct = ContentType.objects.get(app_label=app_label, model=model)
        except ContentType.DoesNotExist:
            continue

        codenames = [f"{action}_{model}" for action in actions]
        perms.extend(list(Permission.objects.filter(content_type=ct, codename__in=codenames)))

    if perms:
        hr_admin_group.permissions.add(*perms)
