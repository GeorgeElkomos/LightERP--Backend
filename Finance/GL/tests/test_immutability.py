"""
Test cases for segment combination and journal entry immutability.

Run these tests to verify the immutability implementation:
    python manage.py test Finance.GL.tests.test_immutability
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal

from Finance.GL.models import (
    XX_SegmentType,
    XX_Segment,
    XX_Segment_combination,
    segment_combination_detials,
    JournalEntry,
    JournalLine,
    GeneralLedger,
)
from Finance.core.models import Currency
from Finance.period.models import Period
from datetime import date


class SegmentCombinationImmutabilityTest(TestCase):
    """Test that segment combinations are immutable after creation."""
    
    def setUp(self):
        """Create test data."""
        # Create segment types
        self.entity_type = XX_SegmentType.objects.create(
            segment_name="Entity",
            is_active=True
        )
        self.account_type = XX_SegmentType.objects.create(
            segment_name="Account",
            is_active=True
        )
        
        # Create segments
        self.entity = XX_Segment.objects.create(
            segment_type=self.entity_type,
            code="100",
            alias="Entity 100",
            node_type="child"
        )
        self.account = XX_Segment.objects.create(
            segment_type=self.account_type,
            code="5000",
            alias="Account 5000",
            node_type="child"
        )
    
    def test_combination_creation_allowed(self):
        """Test that creating new combinations is allowed."""
        combo = XX_Segment_combination.create_combination([
            (self.entity_type.id, "100"),
            (self.account_type.id, "5000"),
        ], description="Test combination")
        
        self.assertIsNotNone(combo.id)
        self.assertEqual(combo.description, "Test combination")
        self.assertEqual(combo.details.count(), 2)
    
    def test_combination_modification_blocked(self):
        """Test that modifying existing combinations is blocked."""
        combo = XX_Segment_combination.create_combination([
            (self.entity_type.id, "100"),
            (self.account_type.id, "5000"),
        ])
        
        # Try to modify the description
        combo.description = "Modified description"
        
        with self.assertRaises(ValidationError) as context:
            combo.save()
        
        self.assertIn("Cannot modify Segment Combination", str(context.exception))
    
    def test_combination_deletion_blocked(self):
        """Test that deleting combinations is blocked."""
        combo = XX_Segment_combination.create_combination([
            (self.entity_type.id, "100"),
            (self.account_type.id, "5000"),
        ])
        
        with self.assertRaises(ValidationError) as context:
            combo.delete()
        
        self.assertIn("Cannot delete Segment Combination", str(context.exception))
    
    def test_detail_modification_blocked(self):
        """Test that modifying combination details is blocked."""
        combo = XX_Segment_combination.create_combination([
            (self.entity_type.id, "100"),
            (self.account_type.id, "5000"),
        ])
        
        detail = combo.details.first()
        
        # Try to modify the segment
        detail.segment = self.account
        
        with self.assertRaises(ValidationError) as context:
            detail.save()
        
        self.assertIn("Cannot modify Segment Combination Detail", str(context.exception))
    
    def test_detail_deletion_blocked(self):
        """Test that deleting combination details is blocked."""
        combo = XX_Segment_combination.create_combination([
            (self.entity_type.id, "100"),
            (self.account_type.id, "5000"),
        ])
        
        detail = combo.details.first()
        
        with self.assertRaises(ValidationError) as context:
            detail.delete()
        
        self.assertIn("Cannot delete Segment Combination Detail", str(context.exception))


class JournalEntryPostingTest(TestCase):
    """Test the journal entry posting functionality."""
    
    def setUp(self):
        """Create test data."""
        # Create currency
        self.currency = Currency.objects.create(
            code="USD",
            name="US Dollar",
            symbol="$"
        )
        
        # Create January 2026 period with GL open
        self.period = Period.objects.create(
            name='January 2026',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            fiscal_year=2026,
            period_number=1
        )
        self.period.gl_period.state = 'open'
        self.period.gl_period.save()
        
        # Create segment types
        self.entity_type = XX_SegmentType.objects.create(
            segment_name="Entity",
            is_active=True
        )
        self.account_type = XX_SegmentType.objects.create(
            segment_name="Account",
            is_active=True
        )
        
        # Create segments
        self.entity = XX_Segment.objects.create(
            segment_type=self.entity_type,
            code="100",
            alias="Entity 100",
            node_type="child"
        )
        self.account = XX_Segment.objects.create(
            segment_type=self.account_type,
            code="5000",
            alias="Account 5000",
            node_type="child"
        )
        
        # Create segment combination
        self.combo_id = XX_Segment_combination.get_combination_id([
            (self.entity_type.id, "100"),
            (self.account_type.id, "5000"),
        ])
    
    def test_post_balanced_entry(self):
        """Test posting a balanced journal entry."""
        # Create journal entry
        entry = JournalEntry.objects.create(
            date=date(2026, 1, 15),
            currency=self.currency,
            memo="Test entry"
        )
        
        # Add balanced lines
        JournalLine.objects.create(
            entry=entry,
            amount=Decimal("100.00"),
            type='DEBIT',
            segment_combination_id=self.combo_id
        )
        JournalLine.objects.create(
            entry=entry,
            amount=Decimal("100.00"),
            type='CREDIT',
            segment_combination_id=self.combo_id
        )
        
        # Post the entry
        gl_entry = entry.post()
        
        # Verify
        self.assertTrue(entry.posted)
        self.assertIsNotNone(gl_entry)
        self.assertEqual(gl_entry.JournalEntry, entry)
        # Check that submitted_date is today's date (posting date)
        self.assertEqual(gl_entry.submitted_date, timezone.now().date())
    
    def test_post_unbalanced_entry_blocked(self):
        """Test that posting an unbalanced entry is blocked."""
        # Create journal entry
        entry = JournalEntry.objects.create(
            date=date(2026, 1, 15),
            currency=self.currency,
            memo="Unbalanced entry"
        )
        
        # Add unbalanced lines
        JournalLine.objects.create(
            entry=entry,
            amount=Decimal("100.00"),
            type='DEBIT',
            segment_combination_id=self.combo_id
        )
        JournalLine.objects.create(
            entry=entry,
            amount=Decimal("50.00"),
            type='CREDIT',
            segment_combination_id=self.combo_id
        )
        
        # Try to post
        with self.assertRaises(ValidationError) as context:
            entry.post()
        
        self.assertIn("not balanced", str(context.exception))
    
    def test_post_already_posted_entry_blocked(self):
        """Test that posting an already-posted entry is blocked."""
        # Create and post journal entry
        entry = JournalEntry.objects.create(
            date=date(2026, 1, 15),
            currency=self.currency,
            memo="Test entry"
        )
        
        JournalLine.objects.create(
            entry=entry,
            amount=Decimal("100.00"),
            type='DEBIT',
            segment_combination_id=self.combo_id
        )
        JournalLine.objects.create(
            entry=entry,
            amount=Decimal("100.00"),
            type='CREDIT',
            segment_combination_id=self.combo_id
        )
        
        # First post - should succeed
        entry.post()
        
        # Try to post again
        with self.assertRaises(ValidationError) as context:
            entry.post()
        
        self.assertIn("already posted", str(context.exception))
    
    def test_posted_entry_immutable(self):
        """Test that posted entries cannot be modified."""
        # Create and post journal entry
        entry = JournalEntry.objects.create(
            date=date(2026, 1, 15),
            currency=self.currency,
            memo="Test entry"
        )
        
        JournalLine.objects.create(
            entry=entry,
            amount=Decimal("100.00"),
            type='DEBIT',
            segment_combination_id=self.combo_id
        )
        JournalLine.objects.create(
            entry=entry,
            amount=Decimal("100.00"),
            type='CREDIT',
            segment_combination_id=self.combo_id
        )
        
        entry.post()
        
        # Try to modify
        entry.memo = "Modified memo"
        
        with self.assertRaises(ValidationError) as context:
            entry.save()
        
        self.assertIn("already posted", str(context.exception))
    
    def test_posted_entry_cannot_be_deleted(self):
        """Test that posted entries cannot be deleted."""
        # Create and post journal entry
        entry = JournalEntry.objects.create(
            date=date(2026, 1, 15),
            currency=self.currency,
            memo="Test entry"
        )
        
        JournalLine.objects.create(
            entry=entry,
            amount=Decimal("100.00"),
            type='DEBIT',
            segment_combination_id=self.combo_id
        )
        JournalLine.objects.create(
            entry=entry,
            amount=Decimal("100.00"),
            type='CREDIT',
            segment_combination_id=self.combo_id
        )
        
        entry.post()
        
        # Try to delete
        with self.assertRaises(ValidationError) as context:
            entry.delete()
        
        self.assertIn("posted", str(context.exception))

