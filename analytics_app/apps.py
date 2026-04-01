from django.apps import AppConfig


class AnalyticsAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "analytics_app"

    def ready(self) -> None:
        from . import signals  # noqa: F401
