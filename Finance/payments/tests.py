from django.test import TestCase
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import date

# from .models import (
#     PaymentMethod, BankAccount, Payment,
#     PaymentAllocation, SupplierPayment, CustomerPayment
# )
# from Finance.core.models import Currency
# from Finance.BusinessPartner.models import Supplier, Customer


class PaymentMethodTestCase(TestCase):
    """Tests for PaymentMethod model."""
    
    def setUp(self):
        pass
    
    # def test_create_payment_method(self):
    #     """Test creating a payment method."""
    #     method = PaymentMethod.objects.create(
    #         code='CASH',
    #         name='Cash',
    #         is_active=True
    #     )
    #     self.assertEqual(method.code, 'CASH')


class PaymentTestCase(TestCase):
    """Tests for Payment model."""
    
    def setUp(self):
        pass
    
    # def test_payment_workflow(self):
    #     """Test payment approval workflow."""
    #     # Create payment
    #     # Submit for approval
    #     # Approve
    #     # Post
    #     pass
    
    # def test_payment_allocation(self):
    #     """Test payment allocation to invoices."""
    #     pass
    
    # def test_cannot_overpay_invoice(self):
    #     """Test that allocation cannot exceed invoice balance."""
    #     pass
