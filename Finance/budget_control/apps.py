"""
Budget Control App Configuration
"""
from django.apps import AppConfig


class BudgetControlConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Finance.budget_control'
    verbose_name = 'Budget Control'
    
    def ready(self):
        """Import signals when app is ready"""
        try:
            import Finance.budget_control.signals
        except ImportError:
            pass
