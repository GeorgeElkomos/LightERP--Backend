from django.apps import AppConfig


class ApprovalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core.approval'
    verbose_name = 'Approval Workflows'
    
    def ready(self):
        """Import signals or perform startup tasks."""
        # Import signals here if you add any
        # from . import signals
        pass
