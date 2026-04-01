from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Создает пользователя для админки (is_staff) и добавляет в группу HR_ADMIN."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("password")
        parser.add_argument(
            "--superuser",
            action="store_true",
            help="Сделать суперпользователя (полный доступ).",
        )
        parser.add_argument(
            "--also-hr",
            action="store_true",
            help="Также добавить в группу HR (доступ в само приложение).",
        )

    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]
        make_super = bool(options["superuser"])
        also_hr = bool(options["also_hr"])

        User = get_user_model()
        if User.objects.filter(username=username).exists():
            raise CommandError(f"Пользователь '{username}' уже существует")

        if make_super:
            user = User.objects.create_superuser(username=username, password=password)
        else:
            user = User.objects.create_user(username=username)
            user.set_password(password)
            user.is_staff = True
            user.save()

        hr_admin_group, _ = Group.objects.get_or_create(name="HR_ADMIN")
        user.groups.add(hr_admin_group)

        if also_hr:
            hr_group, _ = Group.objects.get_or_create(name="HR")
            user.groups.add(hr_group)

        self.stdout.write(self.style.SUCCESS(f"Admin пользователь создан: {username}"))
