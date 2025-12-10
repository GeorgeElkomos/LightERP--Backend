"""
Payment GL Integration Tests

Tests cover:
1. Payment creation with GL entries
2. GL entry with journal lines and segment combinations
"""

from django.test import TestCase
from decimal import Decimal
from datetime import date

from Finance.payments.models import Payment
from Finance.BusinessPartner.models import Supplier
from Finance.core.models import Currency, Country
from Finance.GL.models import (
    JournalEntry, JournalLine, 
    XX_SegmentType, XX_Segment, XX_Segment_combination
)


class PaymentGLModelTestCase(TestCase):
    """Tests for Payment model with GL entries."""
    
    def setUp(self):
        """Set up test data"""
        # Create currency
        self.currency = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$'
        )
        
        # Create country
        self.country = Country.objects.create(
            code='US',
            name='United States'
        )
        
        # Create supplier
        self.supplier = Supplier.objects.create(
            name='Test Supplier',
            country=self.country
        )
        
        # Get business partner
        self.business_partner = self.supplier.business_partner
    
    def test_create_payment_without_gl_entry(self):
        """Test creating a basic payment without GL entry"""
        payment = Payment.objects.create(
            date=date.today(),
            business_partner=self.business_partner,
            currency=self.currency,
            exchange_rate=Decimal('1.0')
        )
        
        self.assertIsNotNone(payment.id)
        self.assertEqual(payment.approval_status, 'DRAFT')
        self.assertIsNone(payment.gl_entry)
        self.assertEqual(payment.get_total_allocated(), Decimal('0'))
    
    def test_create_payment_with_gl_entry(self):
        """Test creating a payment with GL entry"""
        # Create segment types
        entity_type = XX_SegmentType.objects.create(
            segment_name='Entity',
            is_required=True,
            length=50,
            display_order=1
        )
        
        account_type = XX_SegmentType.objects.create(
            segment_name='Account',
            is_required=True,
            length=50,
            display_order=2
        )
        
        # Create segments
        XX_Segment.objects.create(
            segment_type=entity_type,
            code='100',
            alias='Main Entity',
            node_type='child'
        )
        
        XX_Segment.objects.create(
            segment_type=account_type,
            code='1010',
            alias='Cash',
            node_type='child'
        )
        
        XX_Segment.objects.create(
            segment_type=account_type,
            code='2010',
            alias='Accounts Payable',
            node_type='child'
        )
        
        # Create journal entry
        journal_entry = JournalEntry.objects.create(
            date=date.today(),
            currency=self.currency,
            memo='Test Payment GL Entry'
        )
        
        # Create segment combinations
        debit_combo_id = XX_Segment_combination.get_combination_id([
            (entity_type.id, '100'),
            (account_type.id, '2010')
        ])
        
        credit_combo_id = XX_Segment_combination.get_combination_id([
            (entity_type.id, '100'),
            (account_type.id, '1010')
        ])
        
        # Create journal lines
        JournalLine.objects.create(
            entry=journal_entry,
            amount=Decimal('1000.00'),
            type='DEBIT',
            segment_combination_id=debit_combo_id
        )
        
        JournalLine.objects.create(
            entry=journal_entry,
            amount=Decimal('1000.00'),
            type='CREDIT',
            segment_combination_id=credit_combo_id
        )
        
        # Create payment with GL entry
        payment = Payment.objects.create(
            date=date.today(),
            business_partner=self.business_partner,
            currency=self.currency,
            exchange_rate=Decimal('1.0'),
            gl_entry=journal_entry
        )
        
        self.assertIsNotNone(payment.gl_entry)
        self.assertEqual(payment.gl_entry.lines.count(), 2)
        self.assertFalse(payment.gl_entry.posted)
        
        # Verify journal lines have segment combinations
        for line in payment.gl_entry.lines.all():
            self.assertIsNotNone(line.segment_combination)
            self.assertEqual(line.segment_combination.details.count(), 2)
