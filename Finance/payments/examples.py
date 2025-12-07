"""
Payment Allocation System - Usage Examples

This script demonstrates how to use the payment allocation system.
Run this in Django shell: python manage.py shell < examples.py
"""

from decimal import Decimal
from datetime import date
from django.db import transaction

from Finance.payments.models import Payment, PaymentAllocation
from Finance.Invoice.models import AP_Invoice, AR_Invoice
from Finance.BusinessPartner.models import BusinessPartner, Supplier, Customer
from Finance.core.models import Currency, Country
from Finance.GL.models import JournalEntry, Account, AccountType


def setup_test_data():
    """Create test data for examples"""
    print("=" * 60)
    print("Setting up test data...")
    print("=" * 60)
    
    # Create currency
    currency, _ = Currency.objects.get_or_create(
        code="USD",
        defaults={
            "name": "US Dollar",
            "symbol": "$",
            "is_base_currency": True
        }
    )
    
    # Create country
    country, _ = Country.objects.get_or_create(
        code="US",
        defaults={
            "name": "United States",
            "currency": currency
        }
    )
    
    # Create supplier
    bp, _ = BusinessPartner.objects.get_or_create(
        name="ACME Corp",
        defaults={"country": country}
    )
    supplier, _ = Supplier.objects.get_or_create(
        business_partner=bp,
        defaults={"payment_terms": "Net 30"}
    )
    
    # Create GL accounts and journal entry
    account_type, _ = AccountType.objects.get_or_create(
        code="ASSET",
        defaults={"name": "Asset"}
    )
    
    account, _ = Account.objects.get_or_create(
        account_number="1000",
        defaults={
            "name": "Cash",
            "account_type": account_type,
            "currency": currency
        }
    )
    
    journal_entry, _ = JournalEntry.objects.get_or_create(
        date=date.today(),
        defaults={
            "description": "Test Entry",
            "is_posted": False
        }
    )
    
    print(f"✓ Created currency: {currency}")
    print(f"✓ Created supplier: {supplier}")
    print(f"✓ Created journal entry: {journal_entry}")
    
    return currency, supplier, journal_entry


def example_1_basic_allocation():
    """Example 1: Basic payment allocation"""
    print("\n" + "=" * 60)
    print("EXAMPLE 1: Basic Payment Allocation")
    print("=" * 60)
    
    currency, supplier, journal_entry = setup_test_data()
    
    # Create invoice
    invoice = AP_Invoice.objects.create(
        supplier=supplier,
        date=date.today(),
        currency=currency,
        subtotal=Decimal('1000.00'),
        total=Decimal('1000.00'),
        gl_distributions=journal_entry
    )
    print(f"\n✓ Created invoice with total: ${invoice.invoice.total}")
    print(f"  Initial paid_amount: ${invoice.invoice.paid_amount}")
    print(f"  Payment status: {invoice.invoice.payment_status}")
    
    # Create payment
    payment = Payment.objects.create(
        date=date.today(),
        business_partner=supplier.business_partner,
        currency=currency,
        exchange_rate=Decimal('1.0000')
    )
    print(f"\n✓ Created payment for {payment.business_partner}")
    
    # Allocate payment to invoice
    print(f"\n→ Allocating $500.00 to invoice...")
    allocation = payment.allocate_to_invoice(invoice.invoice, Decimal('500.00'))
    
    # Check result
    invoice.invoice.refresh_from_db()
    print(f"✓ Allocation created!")
    print(f"  Paid amount: ${invoice.invoice.paid_amount}")
    print(f"  Payment status: {invoice.invoice.payment_status}")
    print(f"  Remaining: ${invoice.invoice.remaining_amount()}")


def example_2_multiple_allocations():
    """Example 2: Multiple payments to one invoice"""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Multiple Payments to One Invoice")
    print("=" * 60)
    
    currency, supplier, journal_entry = setup_test_data()
    
    # Create invoice
    invoice = AP_Invoice.objects.create(
        supplier=supplier,
        date=date.today(),
        currency=currency,
        subtotal=Decimal('1000.00'),
        total=Decimal('1000.00'),
        gl_distributions=journal_entry
    )
    print(f"\n✓ Created invoice with total: ${invoice.invoice.total}")
    
    # Create first payment
    payment1 = Payment.objects.create(
        date=date.today(),
        business_partner=supplier.business_partner,
        currency=currency,
        exchange_rate=Decimal('1.0000')
    )
    
    # Create second payment
    payment2 = Payment.objects.create(
        date=date.today(),
        business_partner=supplier.business_partner,
        currency=currency,
        exchange_rate=Decimal('1.0000')
    )
    
    print(f"✓ Created 2 payments")
    
    # Allocate first payment
    print(f"\n→ Payment 1: Allocating $400.00...")
    payment1.allocate_to_invoice(invoice.invoice, Decimal('400.00'))
    invoice.invoice.refresh_from_db()
    print(f"  Paid amount: ${invoice.invoice.paid_amount}")
    print(f"  Status: {invoice.invoice.payment_status}")
    
    # Allocate second payment
    print(f"\n→ Payment 2: Allocating $600.00...")
    payment2.allocate_to_invoice(invoice.invoice, Decimal('600.00'))
    invoice.invoice.refresh_from_db()
    print(f"  Paid amount: ${invoice.invoice.paid_amount}")
    print(f"  Status: {invoice.invoice.payment_status}")
    print(f"  Is fully paid? {invoice.invoice.is_paid()}")


def example_3_update_allocation():
    """Example 3: Updating an allocation"""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Updating an Allocation")
    print("=" * 60)
    
    currency, supplier, journal_entry = setup_test_data()
    
    # Create invoice and payment
    invoice = AP_Invoice.objects.create(
        supplier=supplier,
        date=date.today(),
        currency=currency,
        subtotal=Decimal('1000.00'),
        total=Decimal('1000.00'),
        gl_distributions=journal_entry
    )
    
    payment = Payment.objects.create(
        date=date.today(),
        business_partner=supplier.business_partner,
        currency=currency,
        exchange_rate=Decimal('1.0000')
    )
    
    # Create initial allocation
    print(f"\n→ Initial allocation: $300.00")
    allocation = payment.allocate_to_invoice(invoice.invoice, Decimal('300.00'))
    invoice.invoice.refresh_from_db()
    print(f"  Paid amount: ${invoice.invoice.paid_amount}")
    
    # Update allocation
    print(f"\n→ Updating allocation to $700.00...")
    allocation.amount_allocated = Decimal('700.00')
    allocation.save()
    
    invoice.invoice.refresh_from_db()
    print(f"✓ Allocation updated!")
    print(f"  Paid amount: ${invoice.invoice.paid_amount}")
    print(f"  Status: {invoice.invoice.payment_status}")


def example_4_delete_allocation():
    """Example 4: Deleting an allocation"""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Deleting an Allocation")
    print("=" * 60)
    
    currency, supplier, journal_entry = setup_test_data()
    
    # Create invoice and payment
    invoice = AP_Invoice.objects.create(
        supplier=supplier,
        date=date.today(),
        currency=currency,
        subtotal=Decimal('1000.00'),
        total=Decimal('1000.00'),
        gl_distributions=journal_entry
    )
    
    payment = Payment.objects.create(
        date=date.today(),
        business_partner=supplier.business_partner,
        currency=currency,
        exchange_rate=Decimal('1.0000')
    )
    
    # Create allocation
    print(f"\n→ Creating allocation: $500.00")
    allocation = payment.allocate_to_invoice(invoice.invoice, Decimal('500.00'))
    invoice.invoice.refresh_from_db()
    print(f"  Paid amount: ${invoice.invoice.paid_amount}")
    
    # Delete allocation
    print(f"\n→ Deleting allocation...")
    allocation.delete()
    
    invoice.invoice.refresh_from_db()
    print(f"✓ Allocation deleted!")
    print(f"  Paid amount: ${invoice.invoice.paid_amount}")
    print(f"  Status: {invoice.invoice.payment_status}")


def example_5_validation_errors():
    """Example 5: Validation errors"""
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Validation Errors")
    print("=" * 60)
    
    currency, supplier, journal_entry = setup_test_data()
    
    # Create invoice and payment
    invoice = AP_Invoice.objects.create(
        supplier=supplier,
        date=date.today(),
        currency=currency,
        subtotal=Decimal('1000.00'),
        total=Decimal('1000.00'),
        gl_distributions=journal_entry
    )
    
    payment = Payment.objects.create(
        date=date.today(),
        business_partner=supplier.business_partner,
        currency=currency,
        exchange_rate=Decimal('1.0000')
    )
    
    # Try to allocate more than total
    print(f"\n→ Attempting to allocate $1500.00 (more than invoice total)...")
    try:
        payment.allocate_to_invoice(invoice.invoice, Decimal('1500.00'))
        print("  ✗ Should have raised error!")
    except Exception as e:
        print(f"  ✓ Validation error caught: {e}")
    
    # Try negative amount
    print(f"\n→ Attempting to allocate -$100.00 (negative amount)...")
    try:
        allocation = PaymentAllocation(
            payment=payment,
            invoice=invoice.invoice,
            amount_allocated=Decimal('-100.00')
        )
        allocation.full_clean()
        print("  ✗ Should have raised error!")
    except Exception as e:
        print(f"  ✓ Validation error caught: {type(e).__name__}")


def example_6_payment_summary():
    """Example 6: Getting payment summary"""
    print("\n" + "=" * 60)
    print("EXAMPLE 6: Payment Allocation Summary")
    print("=" * 60)
    
    currency, supplier, journal_entry = setup_test_data()
    
    # Create invoice
    invoice = AP_Invoice.objects.create(
        supplier=supplier,
        date=date.today(),
        currency=currency,
        subtotal=Decimal('1000.00'),
        total=Decimal('1000.00'),
        gl_distributions=journal_entry
    )
    
    # Create multiple payments
    payment1 = Payment.objects.create(
        date=date.today(),
        business_partner=supplier.business_partner,
        currency=currency,
        exchange_rate=Decimal('1.0000')
    )
    
    payment2 = Payment.objects.create(
        date=date.today(),
        business_partner=supplier.business_partner,
        currency=currency,
        exchange_rate=Decimal('1.0000')
    )
    
    # Allocate payments
    payment1.allocate_to_invoice(invoice.invoice, Decimal('300.00'))
    payment2.allocate_to_invoice(invoice.invoice, Decimal('400.00'))
    
    # Get summary
    summary = invoice.invoice.get_payment_allocations_summary()
    
    print(f"\n✓ Invoice Payment Summary:")
    print(f"  Total allocated: ${summary['total_allocated']}")
    print(f"  Number of allocations: {summary['allocation_count']}")
    print(f"\n  Allocations:")
    for alloc in summary['allocations']:
        print(f"    - Payment {alloc['payment_id']}: ${alloc['amount']} on {alloc['payment_date']}")


def run_all_examples():
    """Run all examples"""
    print("\n" + "█" * 60)
    print("PAYMENT ALLOCATION SYSTEM - USAGE EXAMPLES")
    print("█" * 60)
    
    with transaction.atomic():
        example_1_basic_allocation()
        example_2_multiple_allocations()
        example_3_update_allocation()
        example_4_delete_allocation()
        example_5_validation_errors()
        example_6_payment_summary()
        
        print("\n" + "█" * 60)
        print("ALL EXAMPLES COMPLETED!")
        print("█" * 60)
        print("\nNote: Running in transaction - changes will be rolled back")
        
        # Rollback to clean up
        raise Exception("Rolling back test data")


if __name__ == "__main__":
    try:
        run_all_examples()
    except Exception as e:
        if "Rolling back" in str(e):
            print("\n✓ Test data cleaned up")
        else:
            raise
