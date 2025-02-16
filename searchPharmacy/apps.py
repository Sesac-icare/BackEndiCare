from django.apps import AppConfig


class SearchpharmacyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "searchPharmacy"

    def ready(self):
        try:
            from . import scheduler
            scheduler.start()
        except Exception as e:
            print(f"스케줄러 시작 실패: {e}")
