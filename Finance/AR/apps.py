from django.apps import AppConfig


class ArConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Finance.AR'
    label = 'finance_ar'  # Unique label for this app
