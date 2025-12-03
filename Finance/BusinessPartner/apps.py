from django.apps import AppConfig


class BusinessPartnerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Finance.BusinessPartner'
    label = 'finance_businesspartner'  # Unique label for this app
