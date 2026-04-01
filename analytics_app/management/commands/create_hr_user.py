from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Создает учетную запись HR (доступ в приложение) и добавляет в группу HR."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("password")

    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]

        User = get_user_model()
        if User.objects.filter(username=username).exists():
            raise CommandError(f"Пользователь '{username}' уже существует")

        user = User.objects.create_user(username=username)
        user.set_password(password)
        user.save()

        hr_group, _ = Group.objects.get_or_create(name="HR")
        user.groups.add(hr_group)

        self.stdout.write(self.style.SUCCESS(f"HR пользователь создан: {username}"))
