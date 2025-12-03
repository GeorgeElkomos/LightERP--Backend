"""
Usage Examples for Immutable Segment Combinations and Journal Entry Posting

This file demonstrates how to properly use the immutability features.
"""

from django.utils import timezone
from decimal import Decimal

from Finance.GL.models import (
    XX_SegmentType,
    XX_Segment,
    XX_Segment_combination,
    JournalEntry,
    JournalLine,
)
from Finance.core.models import Currency


# ============================================================================
# EXAMPLE 1: Creating Segment Combinations (The Right Way)
# ============================================================================

def create_segment_combination_example():
    """
    Always use create_combination() or get_combination_id() to create combinations.
    These methods ensure proper validation and atomic creation.
    """
    
    # Method 1: Create a new combination explicitly
    combo = XX_Segment_combination.create_combination([
        (1, "100"),    # Entity type ID=1, code="100"
        (2, "5000"),   # Account type ID=2, code="5000"
        (3, "PROJ1"),  # Project type ID=3, code="PROJ1"
    ], description="Entity 100 - Account 5000 - Project PROJ1")
    
    print(f"Created combination: {combo}")
    print(f"Combination ID: {combo.id}")
    
    # Method 2: Get existing or create new (recommended for most use cases)
    combo_id = XX_Segment_combination.get_combination_id([
        (1, "100"),
        (2, "5000"),
        (3, "PROJ1"),
    ])
    
    print(f"Combination ID: {combo_id}")
    
    return combo_id


# ============================================================================
# EXAMPLE 2: What NOT to Do (These Will Fail)
# ============================================================================

def immutability_violations_example():
    """
    These operations will raise ValidationError due to immutability constraints.
    """
    
    # Create a combination
    combo = XX_Segment_combination.create_combination([
        (1, "100"),
        (2, "5000"),
    ])
    
    # ❌ WRONG: Trying to modify the combination
    try:
        combo.description = "Modified description"
        combo.save()  # This will raise ValidationError
    except Exception as e:
        print(f"Error (expected): {e}")
    
    # ❌ WRONG: Trying to delete the combination
    try:
        combo.delete()  # This will raise ValidationError
    except Exception as e:
        print(f"Error (expected): {e}")
    
    # ❌ WRONG: Trying to modify combination details
    try:
        detail = combo.details.first()
        detail.segment_id = 999
        detail.save()  # This will raise ValidationError
    except Exception as e:
        print(f"Error (expected): {e}")
    
    # ✅ RIGHT: Mark as inactive instead of deleting
    combo.is_active = False
    # Note: This will also fail due to immutability!
    # You can only set is_active during creation or use update() carefully


# ============================================================================
# EXAMPLE 3: Creating and Posting Journal Entries
# ============================================================================

def create_and_post_journal_entry_example():
    """
    Demonstrates the complete workflow for creating and posting journal entries.
    """
    
    # Get currency
    currency = Currency.objects.get(code="USD")
    
    # Get or create segment combination
    combo_id = XX_Segment_combination.get_combination_id([
        (1, "100"),    # Entity
        (2, "5000"),   # Account
        (3, "PROJ1"),  # Project
    ])
    
    # Step 1: Create the journal entry
    entry = JournalEntry.objects.create(
        date=timezone.now().date(),
        currency=currency,
        memo="Payment for services"
    )
    
    print(f"Created Journal Entry #{entry.id}")
    
    # Step 2: Add journal lines (must be balanced!)
    debit_line = JournalLine.objects.create(
        entry=entry,
        amount=Decimal("1500.00"),
        type='DEBIT',
        segment_combination_id=combo_id
    )
    
    credit_line = JournalLine.objects.create(
        entry=entry,
        amount=Decimal("1500.00"),
        type='CREDIT',
        segment_combination_id=combo_id
    )
    
    print(f"Added {entry.lines.count()} lines")
    
    # Step 3: Verify the entry is balanced
    if entry.is_balanced():
        print(f"Entry is balanced: Debits={entry.get_total_debit()}, Credits={entry.get_total_credit()}")
    else:
        print(f"Entry is NOT balanced! Difference: {entry.get_balance_difference()}")
        return None
    
    # Step 4: Post the entry to the General Ledger
    try:
        gl_entry = entry.post()
        print(f"✅ Posted to General Ledger #{gl_entry.id} on {gl_entry.submitted_date}")
        print(f"Journal Entry #{entry.id} is now posted and immutable")
        return gl_entry
    except Exception as e:
        print(f"❌ Failed to post: {e}")
        return None


# ============================================================================
# EXAMPLE 4: Handling Unbalanced Entries
# ============================================================================

def unbalanced_entry_example():
    """
    Shows what happens when you try to post an unbalanced entry.
    """
    
    currency = Currency.objects.get(code="USD")
    combo_id = XX_Segment_combination.get_combination_id([
        (1, "100"),
        (2, "5000"),
    ])
    
    # Create entry with unbalanced lines
    entry = JournalEntry.objects.create(
        date=timezone.now().date(),
        currency=currency,
        memo="Unbalanced entry"
    )
    
    JournalLine.objects.create(
        entry=entry,
        amount=Decimal("100.00"),
        type='DEBIT',
        segment_combination_id=combo_id
    )
    
    JournalLine.objects.create(
        entry=entry,
        amount=Decimal("75.00"),  # Not balanced!
        type='CREDIT',
        segment_combination_id=combo_id
    )
    
    # Check balance
    print(f"Debits: {entry.get_total_debit()}")
    print(f"Credits: {entry.get_total_credit()}")
    print(f"Difference: {entry.get_balance_difference()}")
    
    # Try to post (will fail)
    try:
        entry.post()
    except Exception as e:
        print(f"❌ Cannot post unbalanced entry: {e}")


# ============================================================================
# EXAMPLE 5: Posted Entry Immutability
# ============================================================================

def posted_entry_immutability_example():
    """
    Demonstrates that posted entries cannot be modified or deleted.
    """
    
    currency = Currency.objects.get(code="USD")
    combo_id = XX_Segment_combination.get_combination_id([
        (1, "100"),
        (2, "5000"),
    ])
    
    # Create and post an entry
    entry = JournalEntry.objects.create(
        date=timezone.now().date(),
        currency=currency,
        memo="Original memo"
    )
    
    JournalLine.objects.create(
        entry=entry,
        amount=Decimal("100.00"),
        type='DEBIT',
        segment_combination_id=combo_id
    )
    
    JournalLine.objects.create(
        entry=entry,
        amount=Decimal("100.00"),
        type='CREDIT',
        segment_combination_id=combo_id
    )
    
    # Post it
    gl_entry = entry.post()
    print(f"Posted entry #{entry.id}")
    
    # ❌ WRONG: Try to modify posted entry
    try:
        entry.memo = "Modified memo"
        entry.save()  # This will raise ValidationError
    except Exception as e:
        print(f"Error (expected): {e}")
    
    # ❌ WRONG: Try to delete posted entry
    try:
        entry.delete()  # This will raise ValidationError
    except Exception as e:
        print(f"Error (expected): {e}")
    
    # ❌ WRONG: Try to post again
    try:
        entry.post()  # This will raise ValidationError
    except Exception as e:
        print(f"Error (expected): {e}")
    
    # ✅ RIGHT: Create a reversing entry instead
    print("To correct a posted entry, create a reversing entry:")
    reversing_entry = JournalEntry.objects.create(
        date=timezone.now().date(),
        currency=currency,
        memo=f"Reversal of JE#{entry.id}"
    )
    
    # Reverse the lines (swap debit/credit)
    for line in entry.lines.all():
        reversed_type = 'CREDIT' if line.type == 'DEBIT' else 'DEBIT'
        JournalLine.objects.create(
            entry=reversing_entry,
            amount=line.amount,
            type=reversed_type,
            segment_combination_id=line.segment_combination_id
        )
    
    # Post the reversing entry
    reversing_gl = reversing_entry.post()
    print(f"✅ Created reversing entry #{reversing_entry.id}, posted to GL#{reversing_gl.id}")


# ============================================================================
# EXAMPLE 6: Complete Workflow
# ============================================================================

def complete_workflow_example():
    """
    Complete workflow from segment setup to posting journal entries.
    """
    
    print("=" * 80)
    print("COMPLETE WORKFLOW EXAMPLE")
    print("=" * 80)
    
    # 1. Ensure segment types exist
    entity_type = XX_SegmentType.objects.get(segment_name="Entity")
    account_type = XX_SegmentType.objects.get(segment_name="Account")
    
    # 2. Ensure segments exist
    entity = XX_Segment.objects.get(segment_type=entity_type, code="100")
    account = XX_Segment.objects.get(segment_type=account_type, code="5000")
    
    # 3. Get or create combination
    combo_id = XX_Segment_combination.get_combination_id([
        (entity_type.id, entity.code),
        (account_type.id, account.code),
    ])
    print(f"✅ Segment combination ID: {combo_id}")
    
    # 4. Create journal entry
    currency = Currency.objects.get(code="USD")
    entry = JournalEntry.objects.create(
        date=timezone.now().date(),
        currency=currency,
        memo="Monthly expense allocation"
    )
    print(f"✅ Created Journal Entry #{entry.id}")
    
    # 5. Add balanced lines
    JournalLine.objects.create(
        entry=entry,
        amount=Decimal("2500.00"),
        type='DEBIT',
        segment_combination_id=combo_id
    )
    JournalLine.objects.create(
        entry=entry,
        amount=Decimal("2500.00"),
        type='CREDIT',
        segment_combination_id=combo_id
    )
    print(f"✅ Added {entry.lines.count()} balanced lines")
    
    # 6. Validate balance
    if entry.is_balanced():
        print(f"✅ Entry is balanced (Debits={entry.get_total_debit()}, Credits={entry.get_total_credit()})")
    else:
        print(f"❌ Entry is unbalanced! Difference: {entry.get_balance_difference()}")
        return
    
    # 7. Post to General Ledger
    gl_entry = entry.post()
    print(f"✅ Posted to General Ledger #{gl_entry.id} on {gl_entry.submitted_date}")
    
    # 8. Verify immutability
    print(f"✅ Entry is now immutable (posted={entry.posted})")
    
    print("=" * 80)
    print("WORKFLOW COMPLETE")
    print("=" * 80)


# ============================================================================
# Run Examples
# ============================================================================

if __name__ == "__main__":
    print("Run these examples in Django shell:")
    print("  python manage.py shell")
    print("  >>> from Finance.GL.usage_examples import *")
    print("  >>> complete_workflow_example()")
