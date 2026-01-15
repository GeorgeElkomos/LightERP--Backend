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
    create_tax_rate,
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
        self.tax_rate = create_tax_rate()  # 5% tax rate
        self.valid_data = create_valid_po_data(self.supplier, self.currency, self.uom, self.tax_rate)
    
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
        """Test that PO auto-calculates subtotal, tax, delivery, and total"""
        response = self.client.post(self.url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        po = POHeader.objects.get(id=response.data['data']['id'])
        
        # Expected calculations:
        # Subtotal = 10 × 1200.00 = 12,000.00
        # Tax = 12,000.00 × 5% = 600.00
        # Delivery = 50.00 (from fixtures)
        # Total = 12,000.00 + 600.00 + 50.00 = 12,650.00
        
        expected_subtotal = Decimal('10.000') * Decimal('1200.00')
        expected_tax = expected_subtotal * (Decimal('5.00') / Decimal('100'))  # 5% tax
        expected_delivery = Decimal('50.00')
        expected_total = expected_subtotal + expected_tax + expected_delivery
        
        self.assertEqual(po.subtotal, expected_subtotal)
        self.assertEqual(po.tax_amount, expected_tax)
        self.assertEqual(po.delivery_amount, expected_delivery)
        self.assertEqual(po.total_amount, expected_total)
    
    def test_tax_calculation_with_different_rates(self):
        """Test tax calculation with different tax rates"""
        # Create PO with 10% tax rate using different country to avoid unique constraint
        from procurement.po.tests.fixtures import create_country
        uk_country = create_country(code='GB', name='United Kingdom')
        tax_rate_10 = create_tax_rate(country=uk_country, rate=Decimal('10.00'), category='STANDARD')
        
        data = create_valid_po_data(
            self.supplier, 
            self.currency, 
            self.uom, 
            tax_rate=tax_rate_10,
            delivery_amount='100.00'
        )
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        po = POHeader.objects.get(id=response.data['data']['id'])
        
        # Subtotal = 10 × 1200.00 = 12,000.00
        # Tax = 12,000.00 × 10% = 1,200.00
        # Delivery = 100.00
        # Total = 12,000.00 + 1,200.00 + 100.00 = 13,300.00
        
        expected_subtotal = Decimal('12000.00')
        expected_tax = Decimal('1200.00')
        expected_delivery = Decimal('100.00')
        expected_total = Decimal('13300.00')
        
        self.assertEqual(po.subtotal, expected_subtotal)
        self.assertEqual(po.tax_amount, expected_tax)
        self.assertEqual(po.delivery_amount, expected_delivery)
        self.assertEqual(po.total_amount, expected_total)
    
    def test_zero_tax_rate_calculation(self):
        """Test calculation with zero-rated tax (0%)"""
        # Create PO with 0% tax rate
        tax_rate_zero = create_tax_rate(rate=Decimal('0.00'), category='ZERO')
        data = create_valid_po_data(
            self.supplier, 
            self.currency, 
            self.uom, 
            tax_rate=tax_rate_zero,
            delivery_amount='25.00'
        )
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        po = POHeader.objects.get(id=response.data['data']['id'])
        
        # Subtotal = 12,000.00
        # Tax = 12,000.00 × 0% = 0.00
        # Delivery = 25.00
        # Total = 12,000.00 + 0.00 + 25.00 = 12,025.00
        
        self.assertEqual(po.subtotal, Decimal('12000.00'))
        self.assertEqual(po.tax_amount, Decimal('0.00'))
        self.assertEqual(po.delivery_amount, Decimal('25.00'))
        self.assertEqual(po.total_amount, Decimal('12025.00'))
    
    def test_multiple_line_items_tax_calculation(self):
        """Test tax calculation with multiple line items"""
        data = create_valid_po_data(
            self.supplier, 
            self.currency, 
            self.uom,
            self.tax_rate,
            delivery_amount='150.00'
        )
        
        # Add second line item
        data['items'].append({
            "line_number": 2,
            "line_type": "Catalog",
            "item_name": "Monitor",
            "item_description": "27-inch Monitor",
            "quantity": "5",
            "unit_of_measure_id": self.uom.id,
            "unit_price": "500.00",
            "line_notes": ""
        })
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        po = POHeader.objects.get(id=response.data['data']['id'])
        
        # Subtotal = (10 × 1200.00) + (5 × 500.00) = 12,000.00 + 2,500.00 = 14,500.00
        # Tax = 14,500.00 × 5% = 725.00
        # Delivery = 150.00
        # Total = 14,500.00 + 725.00 + 150.00 = 15,375.00
        
        expected_subtotal = Decimal('14500.00')
        expected_tax = Decimal('725.00')
        expected_delivery = Decimal('150.00')
        expected_total = Decimal('15375.00')
        
        self.assertEqual(po.subtotal, expected_subtotal)
        self.assertEqual(po.tax_amount, expected_tax)
        self.assertEqual(po.delivery_amount, expected_delivery)
        self.assertEqual(po.total_amount, expected_total)
    
    def test_no_delivery_amount(self):
        """Test calculation with no delivery charges"""
        data = create_valid_po_data(
            self.supplier, 
            self.currency, 
            self.uom,
            self.tax_rate,
            delivery_amount='0.00'
        )
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        po = POHeader.objects.get(id=response.data['data']['id'])
        
        # Subtotal = 12,000.00
        # Tax = 12,000.00 × 5% = 600.00
        # Delivery = 0.00
        # Total = 12,000.00 + 600.00 + 0.00 = 12,600.00
        
        self.assertEqual(po.subtotal, Decimal('12000.00'))
        self.assertEqual(po.tax_amount, Decimal('600.00'))
        self.assertEqual(po.delivery_amount, Decimal('0.00'))
        self.assertEqual(po.total_amount, Decimal('12600.00'))
    
    def test_recalculate_totals_after_line_update(self):
        """Test that totals are recalculated when line items change"""
        # Create initial PO
        response = self.client.post(self.url, self.valid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        po = POHeader.objects.get(id=response.data['data']['id'])
        initial_total = po.total_amount
        
        # Update line item quantity
        line_item = po.line_items.first()
        line_item.quantity = Decimal('20.000')  # Double the quantity
        line_item.save()
        
        # Refresh from database
        po.refresh_from_db()
        
        # New calculations:
        # Subtotal = 20 × 1200.00 = 24,000.00
        # Tax = 24,000.00 × 5% = 1,200.00
        # Delivery = 50.00
        # Total = 24,000.00 + 1,200.00 + 50.00 = 25,250.00
        
        expected_subtotal = Decimal('24000.00')
        expected_tax = Decimal('1200.00')
        expected_total = Decimal('25250.00')
        
        self.assertEqual(po.subtotal, expected_subtotal)
        self.assertEqual(po.tax_amount, expected_tax)
        self.assertEqual(po.total_amount, expected_total)
        self.assertNotEqual(po.total_amount, initial_total)


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
        self.tax_rate = create_tax_rate()  # 5% tax rate
        self.valid_data = create_valid_po_from_pr_data(self.pr_items, self.supplier, self.currency, self.tax_rate)
    
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


# ============================================================================
# ATTACHMENT TESTS
# ============================================================================

class POAttachmentTests(TestCase):
    """Test PO attachment functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create a PO for testing
        self.uom = create_unit_of_measure()
        self.supplier = create_supplier()
        self.currency = create_currency()
        self.tax_rate = create_tax_rate()
        
        po_data = create_valid_po_data(self.supplier, self.currency, self.uom, self.tax_rate)
        response = self.client.post(reverse('po:po-list'), po_data, format='json')
        self.po_id = response.data['data']['id']
        
        self.list_url = reverse('po:po-attachment-list', kwargs={'po_id': self.po_id})
    
    def test_upload_attachment_success(self):
        """Test successful attachment upload"""
        import base64
        
        # Create a simple test file
        test_file_content = b"This is a test PDF file content"
        file_data_base64 = base64.b64encode(test_file_content).decode('utf-8')
        
        data = {
            'file_name': 'test_invoice.pdf',
            'file_type': 'application/pdf',
            'file_data_base64': file_data_base64,
            'description': 'Test vendor invoice'
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['file_name'], 'test_invoice.pdf')
        self.assertEqual(response.data['data']['file_size'], len(test_file_content))
        self.assertIn('uploaded_by_email', response.data['data'])
    
    def test_list_attachments(self):
        """Test listing all attachments for a PO"""
        import base64
        
        # Upload a couple of attachments
        for i in range(2):
            test_content = f"Test file {i}".encode()
            data = {
                'file_name': f'test_file_{i}.txt',
                'file_type': 'text/plain',
                'file_data_base64': base64.b64encode(test_content).decode('utf-8'),
                'description': f'Test file {i}'
            }
            self.client.post(self.list_url, data, format='json')
        
        # List attachments
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(len(response.data['data']), 2)
        # Check that both files are present (ordering may vary)
        file_names = [att['file_name'] for att in response.data['data']]
        self.assertIn('test_file_0.txt', file_names)
        self.assertIn('test_file_1.txt', file_names)
    
    def test_download_attachment(self):
        """Test downloading a specific attachment"""
        import base64
        
        # Upload an attachment first
        test_content = b"Download test content"
        upload_data = {
            'file_name': 'download_test.pdf',
            'file_type': 'application/pdf',
            'file_data_base64': base64.b64encode(test_content).decode('utf-8'),
            'description': 'Download test'
        }
        upload_response = self.client.post(self.list_url, upload_data, format='json')
        attachment_id = upload_response.data['data']['attachment_id']
        
        # Download the attachment
        detail_url = reverse('po:po-attachment-detail', kwargs={'attachment_id': attachment_id})
        response = self.client.get(detail_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['file_name'], 'download_test.pdf')
        self.assertIn('file_data_base64', response.data['data'])
        
        # Verify file content
        downloaded_content = base64.b64decode(response.data['data']['file_data_base64'])
        self.assertEqual(downloaded_content, test_content)
    
    def test_delete_attachment(self):
        """Test deleting an attachment"""
        import base64
        
        # Upload an attachment
        test_content = b"Delete test content"
        upload_data = {
            'file_name': 'delete_test.pdf',
            'file_type': 'application/pdf',
            'file_data_base64': base64.b64encode(test_content).decode('utf-8')
        }
        upload_response = self.client.post(self.list_url, upload_data, format='json')
        attachment_id = upload_response.data['data']['attachment_id']
        
        # Delete the attachment
        detail_url = reverse('po:po-attachment-detail', kwargs={'attachment_id': attachment_id})
        response = self.client.delete(detail_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify attachment was deleted
        list_response = self.client.get(self.list_url)
        self.assertEqual(len(list_response.data['data']), 0)
    
    def test_upload_attachment_without_file_data(self):
        """Test upload fails without file data"""
        data = {
            'file_name': 'test.pdf',
            'file_type': 'application/pdf',
            'description': 'Missing file data'
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_upload_attachment_invalid_base64(self):
        """Test upload fails with invalid base64"""
        data = {
            'file_name': 'test.pdf',
            'file_type': 'application/pdf',
            'file_data_base64': 'not-valid-base64!!!',
            'description': 'Invalid base64'
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_upload_attachment_to_nonexistent_po(self):
        """Test upload fails for non-existent PO"""
        import base64
        
        invalid_url = reverse('po:po-attachment-list', kwargs={'po_id': 99999})
        data = {
            'file_name': 'test.pdf',
            'file_type': 'application/pdf',
            'file_data_base64': base64.b64encode(b"test").decode('utf-8')
        }
        
        response = self.client.post(invalid_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_download_nonexistent_attachment(self):
        """Test download fails for non-existent attachment"""
        detail_url = reverse('po:po-attachment-detail', kwargs={'attachment_id': 99999})
        response = self.client.get(detail_url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_attachment_file_size_display(self):
        """Test file size is displayed in human-readable format"""
        import base64
        
        # Upload a 1KB file
        test_content = b"x" * 1024
        data = {
            'file_name': 'size_test.txt',
            'file_type': 'text/plain',
            'file_data_base64': base64.b64encode(test_content).decode('utf-8')
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['data']['file_size'], 1024)
        self.assertIn('KB', response.data['data']['file_size_display'])
    
    def test_attachment_uploaded_by_auto_set(self):
        """Test uploaded_by is automatically set to authenticated user"""
        import base64
        
        data = {
            'file_name': 'user_test.pdf',
            'file_type': 'application/pdf',
            'file_data_base64': base64.b64encode(b"test").decode('utf-8')
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['data']['uploaded_by_email'], self.user.email)
    
    def test_attachment_included_in_po_detail(self):
        """Test attachments are included in PO detail response"""
        import base64
        
        # Upload an attachment
        data = {
            'file_name': 'detail_test.pdf',
            'file_type': 'application/pdf',
            'file_data_base64': base64.b64encode(b"test").decode('utf-8')
        }
        self.client.post(self.list_url, data, format='json')
        
        # Get PO detail
        detail_url = reverse('po:po-detail', kwargs={'pk': self.po_id})
        response = self.client.get(detail_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('attachments', response.data['data'])
        self.assertEqual(len(response.data['data']['attachments']), 1)
        self.assertEqual(response.data['data']['attachments'][0]['file_name'], 'detail_test.pdf')
    
    def test_attachments_require_authentication(self):
        """Test attachment endpoints require authentication"""
        # Logout
        self.client.force_authenticate(user=None)
        
        # Try to list attachments
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Try to upload attachment
        response = self.client.post(self.list_url, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ============================================================================
# TOLERANCE PERCENTAGE TESTS
# ============================================================================

class POLineToleranceTests(TestCase):
    """Test PO line item tolerance percentage functionality"""
    
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
        self.tax_rate = create_tax_rate()
        self.valid_data = create_valid_po_data(self.supplier, self.currency, self.uom, self.tax_rate)
    
    def test_create_po_with_tolerance(self):
        """Test creating PO line with tolerance percentage"""
        data = self.valid_data.copy()
        data['items'][0]['tolerance_percentage'] = '10.00'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        po = POHeader.objects.get(id=response.data['data']['id'])
        line = po.line_items.first()
        
        self.assertEqual(line.tolerance_percentage, Decimal('10.00'))
    
    def test_create_po_default_zero_tolerance(self):
        """Test that PO line has default 0% tolerance if not specified"""
        response = self.client.post(self.url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        po = POHeader.objects.get(id=response.data['data']['id'])
        line = po.line_items.first()
        
        self.assertEqual(line.tolerance_percentage, Decimal('0.00'))
    
    def test_tolerance_percentage_validation_negative(self):
        """Test that negative tolerance percentage is rejected"""
        data = self.valid_data.copy()
        data['items'][0]['tolerance_percentage'] = '-5.00'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_tolerance_percentage_validation_over_100(self):
        """Test that tolerance percentage over 100 is rejected"""
        data = self.valid_data.copy()
        data['items'][0]['tolerance_percentage'] = '150.00'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_get_max_receivable_quantity(self):
        """Test max receivable quantity calculation with tolerance"""
        data = self.valid_data.copy()
        data['items'][0]['quantity'] = '100.000'
        data['items'][0]['tolerance_percentage'] = '10.00'
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        po = POHeader.objects.get(id=response.data['data']['id'])
        line = po.line_items.first()
        
        # 100 + 10% = 110
        self.assertEqual(line.get_max_receivable_quantity(), Decimal('110.000'))
    
    def test_get_min_acceptable_quantity(self):
        """Test min acceptable quantity calculation with tolerance"""
        data = self.valid_data.copy()
        data['items'][0]['quantity'] = '100.000'
        data['items'][0]['tolerance_percentage'] = '10.00'
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        po = POHeader.objects.get(id=response.data['data']['id'])
        line = po.line_items.first()
        
        # 100 - 10% = 90
        self.assertEqual(line.get_min_acceptable_quantity(), Decimal('90.000'))
    
    def test_get_remaining_quantity_with_tolerance(self):
        """Test remaining quantity includes tolerance in max calculation"""
        data = self.valid_data.copy()
        data['items'][0]['quantity'] = '100.000'
        data['items'][0]['tolerance_percentage'] = '10.00'
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        po = POHeader.objects.get(id=response.data['data']['id'])
        line = po.line_items.first()
        
        # Max receivable = 110, received = 0, remaining = 110
        self.assertEqual(line.get_remaining_quantity(), Decimal('110.000'))
        
        # Receive 50
        line.quantity_received = Decimal('50.000')
        line.save()
        
        # Remaining = 110 - 50 = 60
        self.assertEqual(line.get_remaining_quantity(), Decimal('60.000'))
    
    def test_is_fully_received_with_tolerance(self):
        """Test fully received check considers minimum tolerance"""
        data = self.valid_data.copy()
        data['items'][0]['quantity'] = '100.000'
        data['items'][0]['tolerance_percentage'] = '10.00'
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        po = POHeader.objects.get(id=response.data['data']['id'])
        line = po.line_items.first()
        
        # Not fully received initially
        self.assertFalse(line.is_fully_received())
        
        # Receive 89 (below minimum 90) - not fully received
        line.quantity_received = Decimal('89.000')
        line.save()
        self.assertFalse(line.is_fully_received())
        
        # Receive 90 (exactly minimum) - fully received
        line.quantity_received = Decimal('90.000')
        line.save()
        self.assertTrue(line.is_fully_received())
        
        # Receive 100 (exactly ordered) - fully received
        line.quantity_received = Decimal('100.000')
        line.save()
        self.assertTrue(line.is_fully_received())
        
        # Receive 110 (maximum with tolerance) - fully received
        line.quantity_received = Decimal('110.000')
        line.save()
        self.assertTrue(line.is_fully_received())
    
    def test_tolerance_in_serializer_response(self):
        """Test that tolerance fields appear in API response"""
        data = self.valid_data.copy()
        data['items'][0]['quantity'] = '100.000'
        data['items'][0]['tolerance_percentage'] = '15.00'
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Get PO detail to check serializer response
        po_id = response.data['data']['id']
        detail_response = self.client.get(reverse('po:po-detail', kwargs={'pk': po_id}))
        
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        line_data = detail_response.data['data']['items'][0]
        
        self.assertIn('tolerance_percentage', line_data)
        self.assertEqual(Decimal(line_data['tolerance_percentage']), Decimal('15.00'))
        self.assertIn('max_receivable_quantity', line_data)
        self.assertEqual(Decimal(line_data['max_receivable_quantity']), Decimal('115.000'))
        self.assertIn('min_acceptable_quantity', line_data)
        self.assertEqual(Decimal(line_data['min_acceptable_quantity']), Decimal('85.000'))
    
    def test_different_tolerances_per_line(self):
        """Test that each line can have different tolerance"""
        data = self.valid_data.copy()
        data['items'][0]['quantity'] = '100.000'
        data['items'][0]['tolerance_percentage'] = '10.00'
        
        # Add second line with different tolerance
        data['items'].append({
            "line_number": 2,
            "line_type": "Catalog",
            "item_name": "Monitor",
            "item_description": "27-inch Monitor",
            "quantity": "50.000",
            "unit_of_measure_id": self.uom.id,
            "unit_price": "500.00",
            "tolerance_percentage": "5.00",
            "line_notes": ""
        })
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        po = POHeader.objects.get(id=response.data['data']['id'])
        lines = list(po.line_items.all().order_by('line_number'))
        
        # First line: 10% tolerance
        self.assertEqual(lines[0].tolerance_percentage, Decimal('10.00'))
        self.assertEqual(lines[0].get_max_receivable_quantity(), Decimal('110.000'))
        
        # Second line: 5% tolerance
        self.assertEqual(lines[1].tolerance_percentage, Decimal('5.00'))
        self.assertEqual(lines[1].get_max_receivable_quantity(), Decimal('52.500'))
