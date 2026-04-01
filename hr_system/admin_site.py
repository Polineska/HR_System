from __future__ import annotations

from django.contrib.admin import AdminSite


class HRAdminSite(AdminSite):
    site_header = "HR Data-Driven System — Admin"
    site_title = "HR Admin"
    index_title = "Управление системой"

    def has_permission(self, request):
        user = request.user
        if not user.is_active:
            return False
        if not user.is_staff:
            return False
        if user.is_superuser:
            return True
        return user.groups.filter(name="HR_ADMIN").exists()


hr_admin_site = HRAdminSite(name="hr_admin")
