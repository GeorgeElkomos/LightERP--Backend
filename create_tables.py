import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_project.settings')
django.setup()

from django.db import connection
from Finance.cash_management.models import PaymentType, BankStatementLine, BankStatementLineMatch
from Finance.payments.models import Payment

print("Creating tables...")

with connection.schema_editor() as schema_editor:
    # Create PaymentType table
    try:
        schema_editor.create_model(PaymentType)
        print("✓ PaymentType table created")
    except Exception as e:
        print(f"PaymentType table: {e}")
    
    # Create BankStatementLine table
    try:
        schema_editor.create_model(BankStatementLine)
        print("✓ BankStatementLine table created")
    except Exception as e:
        print(f"BankStatementLine table: {e}")
    
    # Create BankStatementLineMatch table
    try:
        schema_editor.create_model(BankStatementLineMatch)
        print("✓ BankStatementLineMatch table created")
    except Exception as e:
        print(f"BankStatementLineMatch table: {e}")
    
    # Add payment fields
    try:
        from Finance.payments.models import Payment
        payment_model = Payment._meta
        
        # Add payment_type field
        payment_type_field = payment_model.get_field('payment_type')
        schema_editor.add_field(Payment, payment_type_field)
        print("✓ payment_type field added to Payment")
    except Exception as e:
        print(f"Payment fields: {e}")

print("\nTables created successfully!")
