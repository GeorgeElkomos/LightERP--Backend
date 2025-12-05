import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_project.settings')
django.setup()

from Finance.BusinessPartner.models import BusinessPartner
from Finance.Invoice.models import Invoice

print("=" * 60)
print("BusinessPartner.get_field_names():")
print("=" * 60)
bp_fields = BusinessPartner.get_field_names()
for i, field in enumerate(bp_fields, 1):
    print(f"{i}. {field}")
print(f"\nTotal: {len(bp_fields)} fields")

print("\n" + "=" * 60)
print("Invoice.get_field_names():")
print("=" * 60)
invoice_fields = Invoice.get_field_names()
for i, field in enumerate(invoice_fields, 1):
    print(f"{i}. {field}")
print(f"\nTotal: {len(invoice_fields)} fields")

print("\n" + "=" * 60)
print("Invoice._meta.get_fields() (ALL fields):")
print("=" * 60)
for field in Invoice._meta.get_fields():
    print(f"  - {field.name} (type: {field.__class__.__name__}, many_to_many: {field.many_to_many}, one_to_many: {field.one_to_many})")
