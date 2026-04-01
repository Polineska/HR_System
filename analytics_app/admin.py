from __future__ import annotations

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group
from django.db.models import Count
from django.utils.html import format_html

from hr_system.admin_site import hr_admin_site

from .models import CsvReport, HRDataset, UserSessionUpload


def _file_link(fieldfile, label: str = "Скачать") -> str:
    if not fieldfile:
        return "—"
    try:
        return format_html('<a href="{}" target="_blank">{}</a>', fieldfile.url, label)
    except Exception:
        return "—"


@admin.register(HRDataset, site=hr_admin_site)
class HRDatasetAdmin(admin.ModelAdmin):
    list_display = ("kind", "name", "user", "is_active", "created_at", "download")
    list_filter = ("kind", "is_active", "created_at", "user")
    search_fields = ("name", "user__username")
    ordering = ("-created_at",)
    readonly_fields = ("id", "user", "kind", "created_at", "download")
    fields = ("id", "user", "kind", "name", "file", "is_active", "created_at", "download")

    @admin.display(description="Файл")
    def download(self, obj: HRDataset):
        return _file_link(obj.file)


@admin.register(UserSessionUpload, site=hr_admin_site)
class UserSessionUploadAdmin(admin.ModelAdmin):
    list_display = ("original_name", "user", "session_key", "created_at", "download")
    list_filter = ("created_at", "user")
    search_fields = ("original_name", "user__username", "session_key")
    ordering = ("-created_at",)
    readonly_fields = ("id", "user", "session_key", "original_name", "created_at", "download")
    fields = ("id", "user", "session_key", "original_name", "file", "created_at", "download")

    @admin.display(description="Файл")
    def download(self, obj: UserSessionUpload):
        return _file_link(obj.file)


@admin.register(CsvReport, site=hr_admin_site)
class CsvReportAdmin(admin.ModelAdmin):
    list_display = ("kind", "user", "dataset", "created_at", "download")
    list_filter = ("kind", "created_at", "user")
    search_fields = ("user__username", "dataset__name")
    ordering = ("-created_at",)
    readonly_fields = ("id", "user", "dataset", "kind", "created_at", "download")
    fields = ("id", "user", "dataset", "kind", "file", "created_at", "download")

    @admin.display(description="Файл")
    def download(self, obj: CsvReport):
        return _file_link(obj.file)


def make_hr(modeladmin, request, queryset):
    hr_group, _ = Group.objects.get_or_create(name="HR")
    for user in queryset:
        user.groups.add(hr_group)


def make_hr_admin_staff(modeladmin, request, queryset):
    hr_admin_group, _ = Group.objects.get_or_create(name="HR_ADMIN")
    for user in queryset:
        user.groups.add(hr_admin_group)
        user.is_staff = True
        user.save(update_fields=["is_staff"])


def remove_hr(modeladmin, request, queryset):
    hr_group, _ = Group.objects.get_or_create(name="HR")
    for user in queryset:
        user.groups.remove(hr_group)


def remove_hr_admin(modeladmin, request, queryset):
    hr_admin_group, _ = Group.objects.get_or_create(name="HR_ADMIN")
    for user in queryset:
        user.groups.remove(hr_admin_group)


make_hr.short_description = "Добавить в группу HR (доступ в приложение)"
make_hr_admin_staff.short_description = "Сделать HR_ADMIN + дать доступ в админку (is_staff)"
remove_hr.short_description = "Убрать из группы HR"
remove_hr_admin.short_description = "Убрать из группы HR_ADMIN"


User = get_user_model()


@admin.register(User, site=hr_admin_site)
class UserAdmin(DjangoUserAdmin):
    actions = (make_hr, make_hr_admin_staff, remove_hr, remove_hr_admin)
    list_display = (
        "username",
        "is_staff",
        "is_superuser",
        "is_active",
        "last_login",
        "date_joined",
        "datasets_count",
        "reports_count",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            _datasets_count=Count("hrdataset", distinct=True),
            _reports_count=Count("csvreport", distinct=True),
        )

    @admin.display(description="Датасеты")
    def datasets_count(self, obj):
        return getattr(obj, "_datasets_count", 0)

    @admin.display(description="Отчеты")
    def reports_count(self, obj):
        return getattr(obj, "_reports_count", 0)


@admin.register(Group, site=hr_admin_site)
class GroupAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    ordering = ("name",)
