from django.apps import AppConfig


class InvoiceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Finance.Invoice'
    label = 'finance_invoice'  # Unique label for this app
