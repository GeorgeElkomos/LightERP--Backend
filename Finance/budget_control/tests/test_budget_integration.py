"""
Budget Integration Tests
Tests for:
- PR → PO → GRN budget flow (3-stage consumption)
- Budget commitment on PR approval
- Budget encumbrance on PO approval
- Budget actual on GRN creation
- Budget release on cancellation/rejection

NOTE: These tests are skipped until procurement models are finalized.
"""

import unittest
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from decimal import Decimal
from datetime import date, timedelta

from Finance.budget_control.models import BudgetHeader, BudgetSegmentValue, BudgetAmount
from Finance.GL.models import XX_Segment, XX_SegmentType
from Finance.core.models import Currency
from Finance.GL.models import XX_Segment_combination
from procurement.PR.models import NonCatalog_PR, PRItem
from procurement.po.models import POHeader, POLineItem
from procurement.receiving.models import GoodsReceipt, GoodsReceiptLine
from Finance.BusinessPartner.models import Supplier
from procurement.catalog.models import UnitOfMeasure
from Finance.budget_control.tests.test_utils import create_test_user, create_test_currency

class BudgetPRIntegrationTestCase(APITestCase):
    """Test budget integration with Purchase Requisitions"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.user = create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create currency
        self.currency = create_test_currency()
        
        # Create segment types
        self.account_type = XX_SegmentType.objects.create(
            segment_name='Account',
            is_required=True,
            length=4,
            display_order=1
        )
        
        self.dept_type = XX_SegmentType.objects.create(
            segment_name='Department',
            is_required=True,
            length=2,
            display_order=2
        )
        
        # Create segments
        self.segment_5000 = XX_Segment.objects.create(segment_type=self.account_type, code='5000', alias='Travel Expense', node_type='child', is_active=True)
        
        self.segment_dept01 = XX_Segment.objects.create(segment_type=self.dept_type, code='01', alias='IT Department', node_type='child', is_active=True)
        
        # Create segment combination
        self.segment_combo = XX_Segment_combination.create_combination(
            combination_list=[
                (self.account_type.id, '5000'),
                (self.dept_type.id, '01')
            ]
        )
        
        # Create budget with ABSOLUTE control
        self.budget = BudgetHeader.objects.create(
            budget_code='PRINT2026',
            budget_name='PR Integration Test',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            currency=self.currency,
            status='ACTIVE',
            is_active=True
        )
        
        # Create segment values
        seg_val_5000 = BudgetSegmentValue.objects.create(
            budget_header=self.budget,
            segment_value=self.segment_5000,
            control_level='ABSOLUTE'
        )
        
        seg_val_dept01 = BudgetSegmentValue.objects.create(
            budget_header=self.budget,
            segment_value=self.segment_dept01,
            control_level='ABSOLUTE'
        )
        
        # Create budget amounts with sufficient budget
        BudgetAmount.objects.create(
            budget_segment_value=seg_val_5000,
            budget_header=self.budget,
            original_budget=Decimal('100000.00')
        )
        
        BudgetAmount.objects.create(
            budget_segment_value=seg_val_dept01,
            budget_header=self.budget,
            original_budget=Decimal('100000.00')
        )
        
        # Create test UOM
        self.uom = UnitOfMeasure.objects.create(
            code='EA',
            name='Each'
        )
    
    def test_pr_creation_consumes_budget_commitment(self):
        """Test PR approval consumes budget as commitment"""
        pr_amount = Decimal('5000.00')
        
        # Get initial budget state
        budget_amt = BudgetAmount.objects.get(
            budget_segment_value__segment_value=self.segment_5000
        )
        initial_committed = budget_amt.committed_amount
        
        # Create and approve PR
        pr = NonCatalog_PR.objects.create(
            pr_number='PR-001',
            
            date=date.today(),
            required_date=date.today() + timedelta(days=30),
            requester_name=self.user.name,
            requester_department='IT',
            segment_combination=self.segment_combo,
            status='APPROVED'
        )
        
        PRItem.objects.create(
            pr=pr.pr,
            line_number=1,
            item_name='Test Item',
            quantity=Decimal('1'),
            estimated_unit_price=pr_amount,
            total_price_per_item=pr_amount
        )
        
        # Trigger budget consumption
        pr.pr._check_and_consume_budget()
        
        # Refresh budget amount
        budget_amt.refresh_from_db()
        
        # Verify commitment increased
        self.assertEqual(
            budget_amt.committed_amount,
            initial_committed + pr_amount
        )
        
        # Verify PR has budget info
        pr.pr.refresh_from_db()
        self.assertEqual(pr.pr.budget_check_status, 'PASSED')
        self.assertIsNotNone(pr.pr.budget_committed_at)
    
    def test_pr_cancellation_releases_budget_commitment(self):
        """Test PR cancellation releases committed budget"""
        pr_amount = Decimal('5000.00')
        
        # Create and approve PR
        pr = NonCatalog_PR.objects.create(
            pr_number='PR-002',
            
            date=date.today(),
            required_date=date.today() + timedelta(days=30),
            requester_name=self.user.name,
            requester_department='IT',
            segment_combination=self.segment_combo,
            status='APPROVED'
        )
        
        PRItem.objects.create(
            pr=pr.pr,
            line_number=1,
            item_name='Test Item',
            quantity=Decimal('1'),
            unit_of_measure=self.uom,
            estimated_unit_price=pr_amount,
            total_price_per_item=pr_amount
        )
        
        pr.pr._check_and_consume_budget()
        
        # Get budget state after PR approval
        budget_amt = BudgetAmount.objects.get(
            budget_segment_value__segment_value=self.segment_5000
        )
        committed_after_approval = budget_amt.committed_amount
        
        # Cancel PR
        pr.cancel()
        
        # Refresh budget amount
        budget_amt.refresh_from_db()
        
        # Verify commitment was released
        self.assertEqual(
            budget_amt.committed_amount,
            committed_after_approval - pr_amount
        )
    
    def test_pr_rejection_does_not_consume_budget(self):
        """Test rejected PR doesn't consume budget"""
        pr_amount = Decimal('5000.00')
        
        # Get initial budget state
        budget_amt = BudgetAmount.objects.get(
            budget_segment_value__segment_value=self.segment_5000
        )
        initial_committed = budget_amt.committed_amount
        
        # Create PR with rejected status
        pr = NonCatalog_PR.objects.create(
            pr_number='PR-003',
            
            date=date.today(),
            required_date=date.today() + timedelta(days=30),
            requester_name=self.user.name,
            requester_department='IT',
            segment_combination=self.segment_combo,
            status='REJECTED'
        )
        
        PRItem.objects.create(
            pr=pr.pr,
            line_number=1,
            item_name='Test Item',
            quantity=Decimal('1'),
            unit_of_measure=self.uom,
            estimated_unit_price=pr_amount,
            total_price_per_item=pr_amount
        )
        
        # Refresh budget amount
        budget_amt.refresh_from_db()
        
        # Verify commitment not increased
        self.assertEqual(budget_amt.committed_amount, initial_committed)
    
    def test_pr_exceeding_budget_fails_check(self):
        """Test PR exceeding budget fails budget check"""
        # Set budget to low amount
        budget_amt = BudgetAmount.objects.get(
            budget_segment_value__segment_value=self.segment_5000
        )
        budget_amt.original_budget = Decimal('1000.00')
        budget_amt.save()
        
        # Try to create PR exceeding budget
        pr = NonCatalog_PR.objects.create(
            pr_number='PR-004',
            
            date=date.today(),
            required_date=date.today() + timedelta(days=30),
            requester_name=self.user.name,
            requester_department='IT',
            segment_combination=self.segment_combo,
            status='PENDING'
        )
        
        PRItem.objects.create(
            pr=pr.pr,
            line_number=1,
            item_name='Expensive Item',
            quantity=Decimal('1'),
            unit_of_measure=self.uom,
            estimated_unit_price=Decimal('5000.00'),
            total_price_per_item=Decimal('5000.00')
        )
        
        # Attempt budget check (should fail due to ABSOLUTE control)
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError) as context:
            pr.pr._check_and_consume_budget()
        
        # Verify check failed
        pr.pr.refresh_from_db()
        self.assertEqual(pr.pr.budget_check_status, 'FAILED')
        self.assertIn('Budget exceeded', str(context.exception))


class BudgetPOIntegrationTestCase(APITestCase):
    """Test budget integration with Purchase Orders"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.user = create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create currency
        self.currency = create_test_currency()
        
        # Create segment types and segments (same as PR test)
        self.account_type = XX_SegmentType.objects.create(
            segment_name='Account',
            is_required=True,
            length=4,
            display_order=1
        )
        
        self.segment_5000 = XX_Segment.objects.create(segment_type=self.account_type, code='5000', alias='Travel Expense', node_type='child', is_active=True)
        
        # Create segment combination
        self.segment_combo = XX_Segment_combination.create_combination(
            combination_list=[(self.account_type.id, '5000')]
        )
        
        # Create budget
        self.budget = BudgetHeader.objects.create(
            budget_code='POINT2026',
            budget_name='PO Integration Test',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            currency=self.currency,
            status='ACTIVE',
            is_active=True
        )
        
        seg_val = BudgetSegmentValue.objects.create(
            budget_header=self.budget,
            segment_value=self.segment_5000,
            control_level='ABSOLUTE'
        )
        
        BudgetAmount.objects.create(
            budget_segment_value=seg_val,
            budget_header=self.budget,
            original_budget=Decimal('100000.00')
        )
        
        # Create approved PR
        self.pr = NonCatalog_PR.objects.create(
            pr_number='PR-PO-001',
            
            date=date.today(),
            required_date=date.today() + timedelta(days=30),
            requester_name=self.user.name,
            requester_department='IT',
            segment_combination=self.segment_combo,
            status='APPROVED'
        )
        
        # Create test vendor and UOM
        self.vendor = Supplier.objects.create(
            name='Test Vendor',
            email='vendor@test.com'
        )
        
        self.uom = UnitOfMeasure.objects.create(
            code='PO',
            name='Each'
        )
        
        self.pr_line = PRItem.objects.create(
            pr=self.pr.pr,
            line_number=1,
            item_name='Test Item',
            quantity=Decimal('10'),
            unit_of_measure=self.uom,
            estimated_unit_price=Decimal('100.00'),
            total_price_per_item=Decimal('1000.00')
        )
        
        # Consume PR budget
        self.pr.pr._check_and_consume_budget()
    
    def test_po_from_pr_converts_commitment_to_encumbrance(self):
        """Test PO approval converts PR commitment to encumbrance"""
        po_amount = Decimal('1000.00')
        
        # Get budget state
        budget_amt = BudgetAmount.objects.get(
            budget_segment_value__segment_value=self.segment_5000
        )
        initial_committed = budget_amt.committed_amount
        initial_encumbered = budget_amt.encumbered_amount
        
        # Create PO from PR
        po = POHeader.objects.create(
            po_number='PO-001',
            po_type='Non-Catalog',
            supplier_name=self.vendor.business_partner,
            po_date=date.today(),
            created_by=self.user,
            currency=self.currency,
            segment_combination=self.segment_combo,
            status='APPROVED'
        )
        po.source_pr_headers.add(self.pr.pr)
        
        POLineItem.objects.create(
            po_header=po,
            source_pr_item=self.pr_line,
            line_number=1,
            line_type='Non-Catalog',
            item_name='Test Item',
            item_description='Test Item Description',
            quantity=Decimal('10'),
            unit_of_measure=self.uom,
            unit_price=Decimal('100.00')
        )
        
        # Trigger budget encumbrance
        po._consume_budget_encumbrance()
        
        # Refresh budget
        budget_amt.refresh_from_db()
        
        # Verify:
        # - Commitment decreased by PR amount
        # - Encumbrance increased by PO amount
        self.assertEqual(
            budget_amt.committed_amount,
            initial_committed - Decimal('1000.00')
        )
        self.assertEqual(
            budget_amt.encumbered_amount,
            initial_encumbered + po_amount
        )
        
        # Verify PO has budget info
        po.refresh_from_db()
        self.assertIsNotNone(po.budget_encumbered_at)
        self.assertTrue(po.budget_pr_commitment_released)
    
    def test_po_rejection_restores_pr_commitment(self):
        """Test PO rejection restores original PR commitment"""
        po_amount = Decimal('1000.00')
        
        # Create and approve PO
        po = POHeader.objects.create(
            po_number='PO-002',
            po_type='Non-Catalog',
            supplier_name=self.vendor.business_partner,
            po_date=date.today(),
            created_by=self.user,
            currency=self.currency,
            segment_combination=self.segment_combo,
            status='APPROVED'
        )
        po.source_pr_headers.add(self.pr.pr)
        
        POLineItem.objects.create(
            po_header=po,
            source_pr_item=self.pr_line,
            line_number=1,
            line_type='Non-Catalog',
            item_name='Test Item',
            item_description='Test Item Description',
            quantity=Decimal('10'),
            unit_of_measure=self.uom,
            unit_price=Decimal('100.00')
        )
        
        po._consume_budget_encumbrance()
        
        # Get budget state after PO approval
        budget_amt = BudgetAmount.objects.get(
            budget_segment_value__segment_value=self.segment_5000
        )
        committed_after_po = budget_amt.committed_amount
        encumbered_after_po = budget_amt.encumbered_amount
        
        # Reject PO
        po.on_rejected(reason='Budget test rejection', instance=po)
        
        # Refresh budget
        budget_amt.refresh_from_db()
        
        # Verify:
        # - Encumbrance released
        # - PR commitment restored
        self.assertEqual(
            budget_amt.encumbered_amount,
            encumbered_after_po - po_amount
        )
        self.assertEqual(
            budget_amt.committed_amount,
            committed_after_po + Decimal('1000.00')  # PR amount restored
        )
    
    def test_po_cancellation_releases_encumbrance(self):
        """Test PO cancellation releases encumbered budget"""
        po_amount = Decimal('1000.00')
        
        # Create and approve PO
        po = POHeader.objects.create(
            po_number='PO-003',
            po_type='Non-Catalog',
            supplier_name=self.vendor.business_partner,
            po_date=date.today(),
            created_by=self.user,
            currency=self.currency,
            segment_combination=self.segment_combo,
            status='APPROVED'
        )
        po.source_pr_headers.add(self.pr.pr)
        
        POLineItem.objects.create(
            po_header=po,
            source_pr_item=self.pr_line,
            line_number=1,
            line_type='Non-Catalog',
            item_name='Test Item',
            item_description='Test Item Description',
            quantity=Decimal('10'),
            unit_of_measure=self.uom,
            unit_price=Decimal('100.00')
        )
        
        po._consume_budget_encumbrance()
        
        # Get budget state
        budget_amt = BudgetAmount.objects.get(
            budget_segment_value__segment_value=self.segment_5000
        )
        encumbered_before = budget_amt.encumbered_amount
        
        # Cancel PO
        po.cancel_po(reason='Budget test cancellation', cancelled_by=self.user)
        
        # Refresh budget
        budget_amt.refresh_from_db()
        
        # Verify encumbrance released
        self.assertEqual(
            budget_amt.encumbered_amount,
            encumbered_before - po_amount
        )


class BudgetGRNIntegrationTestCase(APITestCase):
    """Test budget integration with Goods Receipt Notes"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.user = create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create currency
        self.currency = create_test_currency()
        
        # Create segment
        self.account_type = XX_SegmentType.objects.create(
            segment_name='Account',
            is_required=True,
            length=4,
            display_order=1
        )
        
        self.segment_5000 = XX_Segment.objects.create(segment_type=self.account_type, code='5000', alias='Travel Expense', node_type='child', is_active=True)
        
        # Create segment combination
        self.segment_combo = XX_Segment_combination.create_combination(
            combination_list=[(self.account_type.id, '5000')]
        )
        
        # Create budget
        self.budget = BudgetHeader.objects.create(
            budget_code='GRNINT2026',
            budget_name='GRN Integration Test',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            currency=self.currency,
            status='ACTIVE',
            is_active=True
        )
        
        seg_val = BudgetSegmentValue.objects.create(
            budget_header=self.budget,
            segment_value=self.segment_5000,
            control_level='ABSOLUTE'
        )
        
        BudgetAmount.objects.create(
            budget_segment_value=seg_val,
            budget_header=self.budget,
            original_budget=Decimal('100000.00')
        )
        
        # Create PR → PO flow
        self.pr = NonCatalog_PR.objects.create(
            pr_number='PR-GRN-001',
            
            date=date.today(),
            required_date=date.today() + timedelta(days=30),
            requester_name=self.user.name,
            requester_department='IT',
            segment_combination=self.segment_combo,
            status='APPROVED'
        )
        
        # Create test vendor and UOM
        self.vendor = Supplier.objects.create(
            name='Test Vendor',
            email='vendor@test.com'
        )
        
        self.uom = UnitOfMeasure.objects.create(
            code='GRN',
            name='Unit'
        )
        
        self.pr_line = PRItem.objects.create(
            pr=self.pr.pr,
            line_number=1,
            item_name='Test Item',
            quantity=Decimal('10'),
            unit_of_measure=self.uom,
            estimated_unit_price=Decimal('100.00'),
            total_price_per_item=Decimal('1000.00')
        )
        
        self.pr.pr._check_and_consume_budget()
        
        self.po = POHeader.objects.create(
            po_number='PO-GRN-001',
            po_type='Non-Catalog',
            supplier_name=self.vendor.business_partner,
            po_date=date.today(),
            created_by=self.user,
            currency=self.currency,
            segment_combination=self.segment_combo,
            status='APPROVED'
        )
        self.po.source_pr_headers.add(self.pr.pr)
        
        self.po_line = POLineItem.objects.create(
            po_header=self.po,
            source_pr_item=self.pr_line,
            line_number=1,
            line_type='Non-Catalog',
            item_name='Test Item',
            item_description='Test Item Description',
            quantity=Decimal('10'),
            unit_of_measure=self.uom,
            unit_price=Decimal('100.00')
        )
        
        self.po._consume_budget_encumbrance()
    
    def test_grn_creation_converts_encumbrance_to_actual(self):
        """Test GRN creation converts encumbrance to actual budget"""
        grn_amount = Decimal('1000.00')
        
        # Get budget state
        budget_amt = BudgetAmount.objects.get(
            budget_segment_value__segment_value=self.segment_5000
        )
        initial_encumbered = budget_amt.encumbered_amount
        initial_actual = budget_amt.actual_amount
        
        # Create GRN
        grn = GoodsReceipt.objects.create(
            po_header=self.po,
            receipt_date=date.today(),
            supplier=self.vendor,
            grn_type='Non-Catalog',
            received_by=self.user,
            notes=''
        )
        
        GoodsReceiptLine.objects.create(
            goods_receipt=grn,
            po_line_item=self.po_line,
            line_number=1,
            item_name='Test Item',
            item_description='Test Item Description',
            quantity_ordered=Decimal('10'),
            quantity_received=Decimal('10'),
            unit_of_measure=self.uom,
            unit_price=Decimal('100.00')
        )
        
        # Budget is automatically updated when GRN line is saved
        # Trigger budget actual update
        # grn.update_budget_actual()
        
        # Refresh budget
        budget_amt.refresh_from_db()
        
        # Verify:
        # - Encumbrance decreased
        # - Actual increased
        self.assertEqual(
            budget_amt.encumbered_amount,
            initial_encumbered - grn_amount
        )
        self.assertEqual(
            budget_amt.actual_amount,
            initial_actual + grn_amount
        )
        
        # Verify GRN has budget info
        grn.refresh_from_db()
        self.assertIsNotNone(grn.budget_actual_updated_at)
    
    def test_grn_deletion_reverses_actual_and_restores_encumbrance(self):
        """Test GRN deletion reverses actual and restores encumbrance"""
        grn_amount = Decimal('1000.00')
        
        # Create GRN
        grn = GoodsReceipt.objects.create(
            po_header=self.po,
            receipt_date=date.today(),
            supplier=self.vendor,
            grn_type='Non-Catalog',
            received_by=self.user,
            notes=''
        )
        
        GoodsReceiptLine.objects.create(
            goods_receipt=grn,
            po_line_item=self.po_line,
            line_number=1,
            item_name='Test Item',
            item_description='Test Item Description',
            quantity_ordered=Decimal('10'),
            quantity_received=Decimal('10'),
            unit_of_measure=self.uom,
            unit_price=Decimal('100.00')
        )
        
        # Budget is automatically updated when GRN line is saved
        # grn.update_budget_actual()
        
        # Get budget state after GRN
        budget_amt = BudgetAmount.objects.get(
            budget_segment_value__segment_value=self.segment_5000
        )
        encumbered_after_grn = budget_amt.encumbered_amount
        actual_after_grn = budget_amt.actual_amount
        
        # Delete GRN (reverse budget)
        grn.reverse_budget_actual()
        grn.delete()
        
        # Refresh budget
        budget_amt.refresh_from_db()
        
        # Verify:
        # - Actual decreased
        # - Encumbrance restored
        self.assertEqual(
            budget_amt.actual_amount,
            actual_after_grn - grn_amount
        )
        self.assertEqual(
            budget_amt.encumbered_amount,
            encumbered_after_grn + grn_amount
        )
    
    def test_partial_grn_partial_budget_conversion(self):
        """Test partial GRN converts partial encumbrance to actual"""
        # Receive only half of PO quantity
        partial_amount = Decimal('500.00')
        
        budget_amt = BudgetAmount.objects.get(
            budget_segment_value__segment_value=self.segment_5000
        )
        initial_encumbered = budget_amt.encumbered_amount
        initial_actual = budget_amt.actual_amount
        
        # Create partial GRN
        grn = GoodsReceipt.objects.create(
            po_header=self.po,
            receipt_date=date.today(),
            supplier=self.vendor,
            grn_type='Non-Catalog',
            received_by=self.user,
            notes=''
        )
        
        GoodsReceiptLine.objects.create(
            goods_receipt=grn,
            po_line_item=self.po_line,
            line_number=1,
            item_name='Test Item',
            item_description='Test Item Description',
            quantity_ordered=Decimal('10'),
            quantity_received=Decimal('5'),  # Half of 10
            unit_of_measure=self.uom,
            unit_price=Decimal('100.00')
        )
        
        # Budget is automatically updated when GRN line is saved
        # No need to manually call grn.update_budget_actual()
        
        # Refresh budget
        budget_amt.refresh_from_db()
        
        # Verify partial conversion
        self.assertEqual(
            budget_amt.encumbered_amount,
            initial_encumbered - partial_amount
        )
        self.assertEqual(
            budget_amt.actual_amount,
            initial_actual + partial_amount
        )
        
        # Remaining encumbrance should still exist for remaining PO quantity
        remaining_encumbrance = Decimal('500.00')
        self.assertGreater(budget_amt.encumbered_amount, Decimal('0'))



class BudgetEndToEndFlowTestCase(APITestCase):
    """Test complete end-to-end budget flow"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.user = create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create currency
        self.currency = create_test_currency()
        
        # Create segment
        self.account_type = XX_SegmentType.objects.create(
            segment_name='Account',
            is_required=True,
            length=4,
            display_order=1
        )
        
        self.segment_5000 = XX_Segment.objects.create(segment_type=self.account_type, code='5000', alias='Travel Expense', node_type='child', is_active=True)
        
        # Create segment combination
        self.segment_combo = XX_Segment_combination.create_combination(
            combination_list=[(self.account_type.id, '5000')]
        )
        
        # Create budget
        self.budget = BudgetHeader.objects.create(
            budget_code='E2E2026',
            budget_name='End to End Test',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            currency=self.currency,
            status='ACTIVE',
            is_active=True
        )
        
        seg_val = BudgetSegmentValue.objects.create(
            budget_header=self.budget,
            segment_value=self.segment_5000,
            control_level='ABSOLUTE'
        )
        
        self.budget_amount = BudgetAmount.objects.create(
            budget_segment_value=seg_val,
            budget_header=self.budget,
            original_budget=Decimal('50000.00')
        )
        
        # Create test vendor and UOM
        self.vendor = Supplier.objects.create(
            name='Test Vendor',
            email='vendor@test.com'
        )
        
        self.uom = UnitOfMeasure.objects.create(
            code='E2E',
            name='Each'
        )
    
    def test_complete_pr_po_grn_budget_flow(self):
        """Test complete PR → PO → GRN budget flow"""
        amount = Decimal('10000.00')
        
        # Stage 0: Initial state
        self.budget_amount.refresh_from_db()
        self.assertEqual(self.budget_amount.committed_amount, Decimal('0'))
        self.assertEqual(self.budget_amount.encumbered_amount, Decimal('0'))
        self.assertEqual(self.budget_amount.actual_amount, Decimal('0'))
        self.assertEqual(self.budget_amount.get_available(), Decimal('50000.00'))
        
        # Stage 1: Create and approve PR (Commitment)
        pr = NonCatalog_PR.objects.create(
            pr_number='PR-E2E',
            
            date=date.today(),
            required_date=date.today() + timedelta(days=30),
            requester_name=self.user.name,
            requester_department='IT',
            segment_combination=self.segment_combo,
            status='APPROVED'
        )
        
        pr_line = PRItem.objects.create(
            pr=pr.pr,
            line_number=1,
            item_name='Test Item',
            quantity=Decimal('100'),
            unit_of_measure=self.uom,
            estimated_unit_price=Decimal('100.00'),
            total_price_per_item=amount
        )
        
        pr.pr._check_and_consume_budget()
        
        self.budget_amount.refresh_from_db()
        self.assertEqual(self.budget_amount.committed_amount, amount)
        self.assertEqual(self.budget_amount.encumbered_amount, Decimal('0'))
        self.assertEqual(self.budget_amount.actual_amount, Decimal('0'))
        self.assertEqual(self.budget_amount.get_available(), Decimal('40000.00'))
        
        # Stage 2: Create and approve PO (Encumbrance)
        po = POHeader.objects.create(
            po_number='PO-E2E',
            po_type='Non-Catalog',
            supplier_name=self.vendor.business_partner,
            po_date=date.today(),
            created_by=self.user,
            currency=self.currency,
            segment_combination=self.segment_combo,
            status='APPROVED'
        )
        po.source_pr_headers.add(pr.pr)
        
        po_line = POLineItem.objects.create(
            po_header=po,
            source_pr_item=pr_line,
            line_number=1,
            line_type='Non-Catalog',
            item_name='Test Item',
            item_description='Test Item Description',
            quantity=Decimal('100'),
            unit_of_measure=self.uom,
            unit_price=Decimal('100.00')
        )
        
        po._consume_budget_encumbrance()
        
        self.budget_amount.refresh_from_db()
        self.assertEqual(self.budget_amount.committed_amount, Decimal('0'))  # Released
        self.assertEqual(self.budget_amount.encumbered_amount, amount)
        self.assertEqual(self.budget_amount.actual_amount, Decimal('0'))
        self.assertEqual(self.budget_amount.get_available(), Decimal('40000.00'))
        
        # Stage 3: Create GRN (Actual)
        grn = GoodsReceipt.objects.create(
            po_header=po,
            receipt_date=date.today(),
            supplier=self.vendor,
            grn_type='Non-Catalog',
            received_by=self.user,
            notes=''
        )
        
        GoodsReceiptLine.objects.create(
            goods_receipt=grn,
            po_line_item=po_line,
            line_number=1,
            item_name='Test Item',
            item_description='Test Item Description',
            quantity_ordered=Decimal('100'),
            quantity_received=Decimal('100'),
            unit_of_measure=self.uom,
            unit_price=Decimal('100.00')
        )
        
        # Budget is automatically updated when GRN line is saved
        # grn.update_budget_actual()
        
        self.budget_amount.refresh_from_db()
        self.assertEqual(self.budget_amount.committed_amount, Decimal('0'))
        self.assertEqual(self.budget_amount.encumbered_amount, Decimal('0'))  # Released
        self.assertEqual(self.budget_amount.actual_amount, amount)
        self.assertEqual(self.budget_amount.get_available(), Decimal('40000.00'))
        
        # Final verification: Total consumed = 10000, Available = 40000
        total_consumed = (
            self.budget_amount.committed_amount +
            self.budget_amount.encumbered_amount +
            self.budget_amount.actual_amount
        )
        self.assertEqual(total_consumed, amount)
        self.assertEqual(
            self.budget_amount.get_available(),
            Decimal('50000.00') - amount
        )
    
    def test_multiple_transactions_budget_tracking(self):
        """Test budget tracking with multiple concurrent transactions"""
        # Create 3 PRs with different amounts
        amounts = [Decimal('5000.00'), Decimal('8000.00'), Decimal('12000.00')]
        
        for i, amount in enumerate(amounts):
            pr = NonCatalog_PR.objects.create(
                pr_number=f'PR-MULTI-{i+1}',
                
                date=date.today(),
                required_date=date.today() + timedelta(days=30),
                requester_name=self.user.name,
                requester_department='IT',
                segment_combination=self.segment_combo,
                status='APPROVED'
            )
            
            PRItem.objects.create(
                pr=pr.pr,
                line_number=1,
                item_name=f'Item {i+1}',
                quantity=Decimal('1'),
                unit_of_measure=self.uom,
                estimated_unit_price=amount,
                total_price_per_item=amount
            )
            
            pr.pr._check_and_consume_budget()
        
        # Verify total commitment
        self.budget_amount.refresh_from_db()
        total_committed = sum(amounts)
        self.assertEqual(self.budget_amount.committed_amount, total_committed)
        
        # Available should be reduced by total committed
        expected_available = Decimal('50000.00') - total_committed
        self.assertEqual(self.budget_amount.get_available(), expected_available)





