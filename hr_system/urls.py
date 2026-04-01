from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.urls import path

from hr_system.admin_site import hr_admin_site

from analytics_app import views


urlpatterns = [
    path("admin/", hr_admin_site.urls),

    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/register/", views.register, name="register"),

    path("", views.dashboard, name="dashboard"),
    path("datasets/", views.datasets, name="datasets"),
    path("datasets/<uuid:dataset_id>/active/", views.dataset_set_active, name="dataset_set_active"),
    path("datasets/<uuid:dataset_id>/delete/", views.dataset_delete, name="dataset_delete"),

    path("individual/", views.individual_analysis, name="individual"),
    path("monitoring/", views.mass_monitoring, name="monitoring"),
    path("download/report/", views.download_report, name="download_report"),
    path("download/csv/<uuid:report_id>/", views.download_csv_report, name="download_csv_report"),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
