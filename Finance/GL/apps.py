from django.apps import AppConfig


class GlConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Finance.GL'
    label = 'finance_gl'  # Unique label for this app
