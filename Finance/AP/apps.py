from django.apps import AppConfig


class ApConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Finance.AP'
    label = 'finance_ap'  # Unique label for this app
