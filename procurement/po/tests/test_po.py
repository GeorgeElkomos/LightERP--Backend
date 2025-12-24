"""
Comprehensive tests for PO API endpoints.

Tests all endpoints:
- POST   /procurement/po/                      - Create PO (manual or from PR)
- GET    /procurement/po/                      - List POs
- GET    /procurement/po/{id}/                 - Get PO detail
- DELETE /procurement/po/{id}/                 - Delete PO
- POST   /procurement/po/{id}/submit-for-approval/ - Submit for approval
- GET    /procurement/po/pending-approvals/    - Get pending approvals
- POST   /procurement/po/{id}/approval-action/ - Approve/Reject
- POST   /procurement/po/{id}/confirm/         - Confirm PO
- POST   /procurement/po/{id}/cancel/          - Cancel PO
- POST   /procurement/po/{id}/record-receipt/  - Record goods receipt
- GET    /procurement/po/{id}/receiving-summary/ - Get receiving summary
- GET    /procurement/po/by-status/            - PO count by status
- GET    /procurement/po/by-supplier/          - PO stats by supplier
- GET    /procurement/po/from-pr/              - POs created from PRs

Covers scenarios:
- Success cases
- Validation errors
- Edge cases
- Business rule violations
- Filter testing
- PR-to-PO conversion
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from datetime import date, timedelta

from procurement.po.models import POHeader, POLineItem
from procurement.PR.models import PRItem
from procurement.po.tests.fixtures import (
    create_unit_of_measure,
    create_catalog_item,
    create_supplier,
    create_currency,
    create_valid_po_data,
    get_or_create_test_user,
    create_simple_approval_template_for_po,
    approve_po_for_testing,
    create_approved_pr_with_items,
    create_valid_po_from_pr_data
)


# ============================================================================
# PO CREATION TESTS
# ============================================================================

class POCreateManualTests(TestCase):
    """Test PO creation endpoint (manual entry)"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        self.url = reverse('po:po-list')
        
        # Create test data
        self.uom = create_unit_of_measure()
        self.supplier = create_supplier()
        self.currency = create_currency()
        self.valid_data = create_valid_po_data(self.supplier, self.currency, self.uom)
    
    def test_create_po_success(self):
        """Test successful PO creation"""
        response = self.client.post(self.url, self.valid_data, format='json')
        
        if response.status_code != status.HTTP_201_CREATED:
            print(f"Response status: {response.status_code}")
            print(f"Response data: {response.data}")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('data', response.data)
        self.assertIn('id', response.data['data'])
        self.assertIn('po_number', response.data['data'])
        self.assertEqual(response.data['data']['po_type'], 'Catalog')
        self.assertEqual(response.data['data']['status'], 'DRAFT')
        
        # Verify PO was created
        po = POHeader.objects.get(id=response.data['data']['id'])
        self.assertIsNotNone(po)
        self.assertEqual(po.supplier_name.id, self.supplier.id)
        
        # Verify line items were created
        self.assertEqual(po.line_items.count(), 1)
        line = po.line_items.first()
        self.assertEqual(line.item_name, 'Test Laptop')
        self.assertEqual(line.quantity, Decimal('10.000'))
        self.assertEqual(line.unit_price, Decimal('1200.00'))
        self.assertEqual(line.line_total, Decimal('12000.00'))
    
    def test_create_po_auto_generates_po_number(self):
        """Test that PO number is auto-generated"""
        response = self.client.post(self.url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        po_number = response.data['data']['po_number']
        self.assertTrue(po_number.startswith('PO-'))
    
    def test_create_po_without_items(self):
        """Test creating PO without items fails"""
        data = self.valid_data.copy()
        data['items'] = []
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_po_mismatched_line_type(self):
        """Test creating PO with line type not matching PO type fails"""
        data = self.valid_data.copy()
        data['po_type'] = 'Catalog'
        data['items'][0]['line_type'] = 'Service'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('line', str(response.data).lower())
    
    def test_create_po_invalid_supplier(self):
        """Test creating PO with invalid supplier fails"""
        data = self.valid_data.copy()
        data['supplier_id'] = 99999
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('supplier', str(response.data).lower())
    
    def test_create_po_invalid_currency(self):
        """Test creating PO with invalid currency fails"""
        data = self.valid_data.copy()
        data['currency_id'] = 99999
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('currency', str(response.data).lower())
    
    def test_create_po_negative_quantity(self):
        """Test creating PO with negative quantity fails"""
        data = self.valid_data.copy()
        data['items'][0]['quantity'] = '-5'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_po_zero_quantity(self):
        """Test creating PO with zero quantity fails"""
        data = self.valid_data.copy()
        data['items'][0]['quantity'] = '0'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_po_multiple_items(self):
        """Test creating PO with multiple items"""
        data = self.valid_data.copy()
        data['items'].append({
            "line_number": 2,
            "line_type": "Catalog",
            "item_name": "Mouse",
            "item_description": "Wireless mouse",
            "quantity": "20",
            "unit_of_measure_id": self.uom.id,
            "unit_price": "50.00",
            "line_notes": ""
        })
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        po = POHeader.objects.get(id=response.data['data']['id'])
        self.assertEqual(po.line_items.count(), 2)
        
        # Verify subtotal calculation
        expected_subtotal = (Decimal('10.000') * Decimal('1200.00')) + (Decimal('20.000') * Decimal('50.00'))
        self.assertEqual(po.subtotal, expected_subtotal)
    
    def test_create_po_calculates_totals(self):
        """Test that PO auto-calculates subtotal and total"""
        response = self.client.post(self.url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        po = POHeader.objects.get(id=response.data['data']['id'])
        
        expected_subtotal = Decimal('10.000') * Decimal('1200.00')
        expected_total = expected_subtotal + Decimal('120.00')  # tax_amount
        
        self.assertEqual(po.subtotal, expected_subtotal)
        self.assertEqual(po.total_amount, expected_total)


class POCreateFromPRTests(TestCase):
    """Test PO creation from approved PR items"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        self.url = reverse('po:po-list')
        
        # Create approved PR with items
        self.pr, self.pr_items = create_approved_pr_with_items()
        self.supplier = create_supplier()
        self.currency = create_currency()
        self.valid_data = create_valid_po_from_pr_data(self.pr_items, self.supplier, self.currency)
    
    def test_create_po_from_pr_success(self):
        """Test successful PO creation from PR items"""
        response = self.client.post(self.url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('data', response.data)
        
        # Verify PO was created
        po = POHeader.objects.get(id=response.data['data']['id'])
        self.assertEqual(po.line_items.count(), 2)
        
        # Verify PR tracking
        self.assertIn(self.pr.pr, po.source_pr_headers.all())
        
        # Verify line items populated from PR
        line1 = po.line_items.get(line_number=1)
        self.assertEqual(line1.item_name, self.pr_items[0].item_name)
        self.assertEqual(line1.item_description, self.pr_items[0].item_description)
        self.assertEqual(line1.source_pr_item, self.pr_items[0])
        self.assertEqual(line1.quantity_from_pr, self.pr_items[0].quantity)
        self.assertEqual(line1.price_from_pr, self.pr_items[0].estimated_unit_price)
    
    def test_create_po_from_pr_updates_conversion_tracking(self):
        """Test that creating PO updates PR item conversion tracking"""
        response = self.client.post(self.url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Refresh PR items from database
        pr_item1 = PRItem.objects.get(id=self.pr_items[0].id)
        pr_item2 = PRItem.objects.get(id=self.pr_items[1].id)
        
        # Verify conversion tracking updated
        self.assertEqual(pr_item1.quantity_converted, pr_item1.quantity)
        self.assertTrue(pr_item1.converted_to_po)
        self.assertIsNotNone(pr_item1.conversion_date)
        
        self.assertEqual(pr_item2.quantity_converted, pr_item2.quantity)
        self.assertTrue(pr_item2.converted_to_po)
    
    def test_create_po_from_pr_partial_conversion(self):
        """Test partial conversion of PR item quantity"""
        data = self.valid_data.copy()
        # Convert only 5 out of 10 laptops
        data['items_from_pr'][0]['quantity_to_convert'] = '5.000'
        data['items_from_pr'].pop(1)  # Remove second item
        
        response = self.client.post(self.url, data, format='json')
        
        if response.status_code != status.HTTP_201_CREATED:
            print(f"Response status: {response.status_code}")
            print(f"Response data: {response.data}")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify partial conversion
        pr_item1 = PRItem.objects.get(id=self.pr_items[0].id)
        self.assertEqual(pr_item1.quantity_converted, Decimal('5.000'))
        self.assertFalse(pr_item1.converted_to_po)  # Not fully converted
    
    def test_create_po_from_unapproved_pr_fails(self):
        """Test creating PO from unapproved PR fails"""
        # Create a draft PR
        from procurement.PR.models import Catalog_PR, PRItem
        uom = create_unit_of_measure()
        
        draft_pr = Catalog_PR.objects.create(
            date=date.today(),
            required_date=date.today() + timedelta(days=10),
            requester_name="Test",
            requester_department="IT",
            priority="MEDIUM"
        )
        
        draft_item = PRItem.objects.create(
            pr=draft_pr.pr,
            line_number=1,
            item_name="Test Item",
            item_description="Test",
            quantity=Decimal('5.000'),
            unit_of_measure=uom,
            estimated_unit_price=Decimal('100.00')
        )
        
        data = {
            "po_date": str(date.today()),
            "po_type": "Catalog",
            "supplier_id": self.supplier.id,
            "currency_id": self.currency.id,
            "description": "Test",
            "tax_amount": "0.00",
            "items_from_pr": [
                {
                    "pr_item_id": draft_item.id,
                    "unit_price": "100.00"
                }
            ]
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('approved', str(response.data).lower())
    
    def test_create_po_from_pr_exceeds_available_quantity(self):
        """Test creating PO with quantity exceeding available PR quantity fails"""
        data = self.valid_data.copy()
        # Try to convert more than available
        data['items_from_pr'][0]['quantity_to_convert'] = '15.000'  # PR has only 10
        data['items_from_pr'].pop(1)
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('exceed', str(response.data).lower())
    
    def test_create_po_from_pr_type_mismatch(self):
        """Test creating PO with type not matching PR type fails"""
        data = self.valid_data.copy()
        data['po_type'] = 'Service'  # PR is Catalog type
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_cannot_specify_both_items_and_items_from_pr(self):
        """Test that specifying both items and items_from_pr fails"""
        data = self.valid_data.copy()
        data['items'] = [{
            "line_number": 1,
            "line_type": "Catalog",
            "item_name": "Test",
            "item_description": "Test",
            "quantity": "1",
            "unit_of_measure_id": create_unit_of_measure().id,
            "unit_price": "100.00"
        }]
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ============================================================================
# PO LIST AND DETAIL TESTS
# ============================================================================

class POListTests(TestCase):
    """Test PO list endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        self.url = reverse('po:po-list')
        
        # Create test POs
        supplier = create_supplier()
        currency = create_currency()
        uom = create_unit_of_measure()
        
        # Create 3 POs with different statuses
        for i, po_status in enumerate(['DRAFT', 'SUBMITTED', 'APPROVED']):
            po = POHeader.objects.create(
                po_date=date.today(),
                po_type='Catalog',
                supplier_name_id=supplier.business_partner_id,
                currency=currency,
                status=po_status,
                created_by=self.user
            )
            POLineItem.objects.create(
                po_header=po,
                line_number=1,
                line_type='Catalog',
                item_name=f'Item {i}',
                item_description=f'Description {i}',
                quantity=Decimal('1.000'),
                unit_of_measure=uom,
                unit_price=Decimal('100.00')
            )
    
    def test_list_pos_success(self):
        """Test listing POs"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        # Check paginated response
        self.assertEqual(response.data['data']['count'], 3)
        self.assertEqual(len(response.data['data']['results']), 3)
    
    def test_list_pos_filter_by_status(self):
        """Test filtering POs by status"""
        response = self.client.get(self.url, {'status': 'DRAFT'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['count'], 1)
        self.assertEqual(response.data['data']['results'][0]['status'], 'DRAFT')
    
    def test_list_pos_filter_by_po_type(self):
        """Test filtering POs by type"""
        response = self.client.get(self.url, {'po_type': 'Catalog'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['count'], 3)
    
    def test_list_pos_filter_by_supplier(self):
        """Test filtering POs by supplier"""
        supplier = create_supplier(name='Specific Supplier')
        currency = create_currency()
        uom = create_unit_of_measure()
        
        po = POHeader.objects.create(
            po_date=date.today(),
            po_type='Catalog',
            supplier_name_id=supplier.business_partner_id,
            currency=currency,
            created_by=self.user
        )
        POLineItem.objects.create(
            po_header=po,
            line_number=1,
            line_type='Catalog',
            item_name='Test',
            item_description='Test',
            quantity=Decimal('1.000'),
            unit_of_measure=uom,
            unit_price=Decimal('100.00')
        )
        
        response = self.client.get(self.url, {'supplier_id': supplier.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['count'], 1)
    
    def test_list_pos_search(self):
        """Test searching POs"""
        po = POHeader.objects.first()
        po.description = 'Special order for laptops'
        po.save()
        
        response = self.client.get(self.url, {'search': 'laptops'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(response.data['data']['count'], 0)


class PODetailTests(TestCase):
    """Test PO detail endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create test PO
        supplier = create_supplier()
        currency = create_currency()
        uom = create_unit_of_measure()
        
        self.po = POHeader.objects.create(
            po_date=date.today(),
            po_type='Catalog',
            supplier_name_id=supplier.business_partner_id,
            currency=currency,
            created_by=self.user
        )
        POLineItem.objects.create(
            po_header=self.po,
            line_number=1,
            line_type='Catalog',
            item_name='Test Item',
            item_description='Test Description',
            quantity=Decimal('10.000'),
            unit_of_measure=uom,
            unit_price=Decimal('100.00')
        )
        
        self.url = reverse('po:po-detail', kwargs={'pk': self.po.id})
    
    def test_get_po_detail_success(self):
        """Test retrieving PO detail"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['id'], self.po.id)
        self.assertEqual(len(response.data['data']['items']), 1)
    
    def test_get_po_detail_not_found(self):
        """Test retrieving non-existent PO"""
        url = reverse('po:po-detail', kwargs={'pk': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_delete_draft_po_success(self):
        """Test deleting draft PO"""
        response = self.client.delete(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(POHeader.objects.filter(id=self.po.id).exists())
    
    def test_delete_non_draft_po_fails(self):
        """Test deleting non-draft PO fails"""
        self.po.status = 'SUBMITTED'
        self.po.save()
        
        response = self.client.delete(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(POHeader.objects.filter(id=self.po.id).exists())


# ============================================================================
# PO WORKFLOW TESTS
# ============================================================================

class POWorkflowTests(TestCase):
    """Test PO workflow actions"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create approval template
        create_simple_approval_template_for_po()
        
        # Create test PO
        supplier = create_supplier()
        currency = create_currency()
        uom = create_unit_of_measure()
        
        self.po = POHeader.objects.create(
            po_date=date.today(),
            po_type='Catalog',
            supplier_name_id=supplier.business_partner_id,
            currency=currency,
            created_by=self.user
        )
        POLineItem.objects.create(
            po_header=self.po,
            line_number=1,
            line_type='Catalog',
            item_name='Test Item',
            item_description='Test',
            quantity=Decimal('10.000'),
            unit_of_measure=uom,
            unit_price=Decimal('100.00')
        )
    
    def test_submit_po_for_approval_success(self):
        """Test submitting PO for approval"""
        url = reverse('po:po-submit-for-approval', kwargs={'pk': self.po.id})
        response = self.client.post(url)
        
        if response.status_code != status.HTTP_200_OK:
            print(f"Response status: {response.status_code}")
            print(f"Response data: {response.data}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, 'SUBMITTED')
    
    def test_submit_non_draft_po_fails(self):
        """Test submitting non-draft PO fails"""
        self.po.status = 'APPROVED'
        self.po.save()
        
        url = reverse('po:po-submit-for-approval', kwargs={'pk': self.po.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_approve_po_success(self):
        """Test approving PO"""
        # Submit first
        self.po.submit_for_approval(submitted_by=self.user)
        
        url = reverse('po:po-approval-action', kwargs={'pk': self.po.id})
        response = self.client.post(url, {'action': 'approve', 'comment': 'Approved'})
        
        if response.status_code != status.HTTP_200_OK:
            print(f"Response status: {response.status_code}")
            print(f"Response data: {response.data}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, 'APPROVED')
    
    def test_reject_po_success(self):
        """Test rejecting PO"""
        # Submit first
        self.po.submit_for_approval(submitted_by=self.user)
        
        url = reverse('po:po-approval-action', kwargs={'pk': self.po.id})
        response = self.client.post(url, {'action': 'reject', 'comment': 'Rejected'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, 'DRAFT')
    
    def test_approval_action_invalid_action(self):
        """Test approval action with invalid action"""
        url = reverse('po:po-approval-action', kwargs={'pk': self.po.id})
        response = self.client.post(url, {'action': 'invalid'})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_confirm_po_success(self):
        """Test confirming approved PO"""
        # Approve PO first
        approve_po_for_testing(self.po)
        
        url = reverse('po:po-confirm', kwargs={'pk': self.po.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, 'CONFIRMED')
    
    def test_confirm_non_approved_po_fails(self):
        """Test confirming non-approved PO fails"""
        url = reverse('po:po-confirm', kwargs={'pk': self.po.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_cancel_po_success(self):
        """Test cancelling PO"""
        url = reverse('po:po-cancel', kwargs={'pk': self.po.id})
        response = self.client.post(url, {'reason': 'No longer needed'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, 'CANCELLED')
        self.assertEqual(self.po.cancellation_reason, 'No longer needed')
    
    def test_cancel_po_without_reason_fails(self):
        """Test cancelling PO without reason fails"""
        url = reverse('po:po-cancel', kwargs={'pk': self.po.id})
        response = self.client.post(url, {})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ============================================================================
# GOODS RECEIVING TESTS
# ============================================================================

class POReceivingTests(TestCase):
    """Test goods receiving functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create and confirm PO
        supplier = create_supplier()
        currency = create_currency()
        uom = create_unit_of_measure()
        
        self.po = POHeader.objects.create(
            po_date=date.today(),
            po_type='Catalog',
            supplier_name_id=supplier.business_partner_id,
            currency=currency,
            status='CONFIRMED',
            created_by=self.user
        )
        self.line_item = POLineItem.objects.create(
            po_header=self.po,
            line_number=1,
            line_type='Catalog',
            item_name='Test Item',
            item_description='Test',
            quantity=Decimal('10.000'),
            unit_of_measure=uom,
            unit_price=Decimal('100.00')
        )
    
    def test_record_receipt_success(self):
        """Test recording goods receipt"""
        url = reverse('po:po-record-receipt', kwargs={'pk': self.po.id})
        response = self.client.post(url, {
            'line_item_id': self.line_item.id,
            'quantity_received': '5.000'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.line_item.refresh_from_db()
        self.assertEqual(self.line_item.quantity_received, Decimal('5.000'))
        
        # PO should be partially received
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, 'PARTIALLY_RECEIVED')
    
    def test_record_full_receipt(self):
        """Test recording full goods receipt"""
        url = reverse('po:po-record-receipt', kwargs={'pk': self.po.id})
        response = self.client.post(url, {
            'line_item_id': self.line_item.id,
            'quantity_received': '10.000'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # PO should be fully received
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, 'RECEIVED')
    
    def test_record_receipt_exceeds_quantity_fails(self):
        """Test recording receipt exceeding ordered quantity fails"""
        url = reverse('po:po-record-receipt', kwargs={'pk': self.po.id})
        response = self.client.post(url, {
            'line_item_id': self.line_item.id,
            'quantity_received': '15.000'
        })
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_record_receipt_invalid_line_item(self):
        """Test recording receipt with invalid line item fails"""
        url = reverse('po:po-record-receipt', kwargs={'pk': self.po.id})
        response = self.client.post(url, {
            'line_item_id': 99999,
            'quantity_received': '5.000'
        })
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_record_receipt_on_non_confirmed_po_fails(self):
        """Test recording receipt on non-confirmed PO fails"""
        self.po.status = 'DRAFT'
        self.po.save()
        
        url = reverse('po:po-record-receipt', kwargs={'pk': self.po.id})
        response = self.client.post(url, {
            'line_item_id': self.line_item.id,
            'quantity_received': '5.000'
        })
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_get_receiving_summary(self):
        """Test getting receiving summary"""
        # Record partial receipt
        self.line_item.record_receipt(Decimal('5.000'))
        
        url = reverse('po:po-receiving-summary', kwargs={'pk': self.po.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['total_ordered'], 10.0)
        self.assertEqual(response.data['data']['total_received'], 5.0)
        self.assertEqual(response.data['data']['receiving_percentage'], 50.0)


# ============================================================================
# REPORTING TESTS
# ============================================================================

class POReportingTests(TestCase):
    """Test PO reporting endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create test POs with different statuses
        supplier = create_supplier()
        currency = create_currency()
        uom = create_unit_of_measure()
        
        for po_status in ['DRAFT', 'DRAFT', 'SUBMITTED', 'APPROVED']:
            po = POHeader.objects.create(
                po_date=date.today(),
                po_type='Catalog',
                supplier_name_id=supplier.business_partner_id,
                currency=currency,
                status=po_status,
                created_by=self.user
            )
            POLineItem.objects.create(
                po_header=po,
                line_number=1,
                line_type='Catalog',
                item_name='Test',
                item_description='Test',
                quantity=Decimal('1.000'),
                unit_of_measure=uom,
                unit_price=Decimal('100.00')
            )
    
    def test_po_by_status(self):
        """Test PO count by status report"""
        url = reverse('po:po-by-status')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        
        # Verify counts
        status_dict = {item['status']: item['count'] for item in response.data['data']}
        self.assertEqual(status_dict.get('DRAFT', 0), 2)
        self.assertEqual(status_dict.get('SUBMITTED', 0), 1)
        self.assertEqual(status_dict.get('APPROVED', 0), 1)
    
    def test_po_by_supplier(self):
        """Test PO statistics by supplier"""
        url = reverse('po:po-by-supplier')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertGreater(len(response.data['data']), 0)
    
    def test_po_from_pr(self):
        """Test listing POs created from PRs"""
        # Create PO from PR
        pr, pr_items = create_approved_pr_with_items()
        supplier = create_supplier()
        currency = create_currency()
        
        po = POHeader.objects.create(
            po_date=date.today(),
            po_type='Catalog',
            supplier_name_id=supplier.business_partner_id,
            currency=currency,
            created_by=self.user
        )
        po.source_pr_headers.add(pr.pr)
        
        url = reverse('po:po-from-pr')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        # Should have at least 1 PO from PR
        self.assertGreater(len(response.data['data']), 0)


# ============================================================================
# AUTHENTICATION TESTS
# ============================================================================

class POAuthenticationTests(TestCase):
    """Test authentication requirements"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.url = reverse('po:po-list')
    
    def test_list_pos_requires_authentication(self):
        """Test that listing POs requires authentication"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_create_po_requires_authentication(self):
        """Test that creating PO requires authentication"""
        response = self.client.post(self.url, {})
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
