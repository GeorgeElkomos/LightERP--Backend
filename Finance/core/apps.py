from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Finance.core'
    label = 'finance_core'  # Unique label for this app
