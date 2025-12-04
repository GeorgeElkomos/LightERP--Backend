# Generated manually to clean up old Invoice models
# This migration removes the old Supplier and APInvoice models that are now obsolete

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('finance_invoice', '0002_remove_apinvoice_base_currency_total_and_more'),
    ]

    operations = [
        # Delete the old APInvoice model
        migrations.DeleteModel(
            name='APInvoice',
        ),
        # Delete the old Supplier model (will be replaced by BusinessPartner.Supplier)
        migrations.DeleteModel(
            name='Supplier',
        ),
    ]
