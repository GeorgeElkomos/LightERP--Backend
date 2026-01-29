"""
Person App Configuration
"""

from django.apps import AppConfig


class PersonConfig(AppConfig):
    """Configuration for the Person app"""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'HR.person'
    label = 'person'
    verbose_name = 'Person Management'

    def ready(self):
        """Initialize app when Django starts"""
        # Import signal handlers if any
        pass