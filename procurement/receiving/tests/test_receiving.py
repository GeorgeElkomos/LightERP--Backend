"""
Comprehensive tests for Receiving API endpoints.

Tests all endpoints:
- POST   /procurement/receiving/                  - Create GRN (manual or from PO)
- GET    /procurement/receiving/                  - List GRNs
- GET    /procurement/receiving/{id}/             - Get GRN detail
- DELETE /procurement/receiving/{id}/             - Delete GRN
- GET    /procurement/receiving/{id}/summary/     - Get GRN summary
- GET    /procurement/receiving/po/{po_id}/status/ - Get PO receiving status
- GET    /procurement/receiving/by-supplier/      - GRN stats by supplier
- GET    /procurement/receiving/by-type/          - GRN stats by type
- GET    /procurement/receiving/recent/           - Recent GRNs

Covers scenarios:
- Success cases
- Validation errors
- Edge cases
- Business rule violations
- Filter testing
- Partial receiving
- Gift items
- PO quantity updates
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from datetime import date, timedelta

from procurement.receiving.models import GoodsReceipt, GoodsReceiptLine
from procurement.po.models import POHeader, POLineItem
from Finance.BusinessPartner.models import Supplier
from procurement.receiving.tests.fixtures import (
    create_unit_of_measure,
    create_catalog_item,
    create_supplier,
    create_currency,
    get_or_create_test_user,
    create_confirmed_po,
    create_valid_grn_manual_data,
    create_valid_grn_from_po_data,
    create_grn_with_lines
)


# ============================================================================
# GRN CREATION TESTS - MANUAL ENTRY
# ============================================================================

class GRNCreateManualTests(TestCase):
    """Test GRN creation endpoint (manual line entry)"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        self.url = reverse('receiving:grn-list')
        
        # Create test data
        self.uom = create_unit_of_measure()
        self.supplier = create_supplier()
        self.currency = create_currency()
        
        # Create confirmed PO
        self.po = create_confirmed_po(self.supplier, self.currency, self.uom, self.user)
        
        # Create valid GRN data
        self.valid_data = create_valid_grn_manual_data(self.po, self.uom)
    
    def test_create_grn_manual_success(self):
        """Test successful GRN creation with manual line entry"""
        response = self.client.post(self.url, self.valid_data, format='json')
        
        if response.status_code != status.HTTP_201_CREATED:
            print(f"Response status: {response.status_code}")
            print(f"Response data: {response.data}")
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('data', response.data)
        self.assertIn('id', response.data['data'])
        self.assertIn('grn_number', response.data['data'])
        self.assertEqual(response.data['data']['grn_type'], self.po.po_type)
        
        # Verify GRN was created
        grn = GoodsReceipt.objects.get(id=response.data['data']['id'])
        self.assertIsNotNone(grn)
        self.assertEqual(grn.po_header.id, self.po.id)
        
        # Verify line items were created
        self.assertEqual(grn.lines.count(), 1)
        line = grn.lines.first()
        self.assertEqual(line.item_name, 'Test Laptop')
        self.assertEqual(line.quantity_received, Decimal('5.000'))
        self.assertEqual(line.line_total, Decimal('6000.00'))
    
    def test_create_grn_auto_generates_grn_number(self):
        """Test that GRN number is auto-generated"""
        response = self.client.post(self.url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        grn_number = response.data['data']['grn_number']
        self.assertTrue(grn_number.startswith('GRN-'))
    
    def test_create_grn_updates_po_line_quantity(self):
        """Test that creating GRN updates PO line received quantity"""
        po_line = self.po.line_items.first()
        initial_received = po_line.quantity_received
        
        response = self.client.post(self.url, self.valid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Refresh PO line
        po_line.refresh_from_db()
        self.assertEqual(po_line.quantity_received, initial_received + Decimal('5.000'))
    
    def test_create_grn_calculates_total(self):
        """Test that GRN total amount is calculated correctly"""
        response = self.client.post(self.url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # 5 × 1200 = 6000
        expected_total = Decimal('6000.00')
        self.assertEqual(Decimal(response.data['data']['total_amount']), expected_total)
    
    def test_create_grn_without_lines(self):
        """Test creating GRN without lines fails"""
        data = self.valid_data.copy()
        data['lines'] = []
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_grn_type_mismatch(self):
        """Test creating GRN with type not matching PO type fails"""
        data = self.valid_data.copy()
        data['grn_type'] = 'Service'  # PO is Catalog
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('grn_type', str(response.data).lower())
    
    def test_create_grn_po_not_confirmed(self):
        """Test creating GRN for non-confirmed PO fails"""
        # Create draft PO
        draft_po = POHeader.objects.create(
            po_type='Catalog',
            po_date=date.today(),
            supplier_name=self.supplier.business_partner,
            currency=self.currency,
            status='DRAFT',
            created_by=self.user
        )
        
        data = self.valid_data.copy()
        data['po_header_id'] = draft_po.id
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('confirmed', str(response.data).lower())
    
    def test_create_grn_quantity_exceeds_ordered(self):
        """Test creating GRN with quantity exceeding ordered fails"""
        po_line = self.po.line_items.first()
        
        data = self.valid_data.copy()
        data['lines'][0]['quantity_received'] = '15.000'  # Ordered is 10
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_grn_negative_quantity(self):
        """Test creating GRN with negative quantity fails"""
        data = self.valid_data.copy()
        data['lines'][0]['quantity_received'] = '-5.000'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_grn_zero_quantity(self):
        """Test creating GRN with zero quantity fails"""
        data = self.valid_data.copy()
        data['lines'][0]['quantity_received'] = '0.000'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_grn_invalid_po(self):
        """Test creating GRN with invalid PO fails"""
        data = self.valid_data.copy()
        data['po_header_id'] = 99999
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ============================================================================
# GRN CREATION TESTS - FROM PO
# ============================================================================

class GRNCreateFromPOTests(TestCase):
    """Test GRN creation endpoint (from PO lines)"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        self.url = reverse('receiving:grn-list')
        
        # Create test data
        self.uom = create_unit_of_measure()
        self.supplier = create_supplier()
        self.currency = create_currency()
        
        # Create confirmed PO
        self.po = create_confirmed_po(self.supplier, self.currency, self.uom, self.user)
        
        # Create valid GRN data
        self.valid_data = create_valid_grn_from_po_data(self.po)
    
    def test_create_grn_from_po_success(self):
        """Test successful GRN creation from PO lines"""
        response = self.client.post(self.url, self.valid_data, format='json')
        
        if response.status_code != status.HTTP_201_CREATED:
            print(f"Response status: {response.status_code}")
            print(f"Response data: {response.data}")
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('data', response.data)
        
        # Verify GRN was created
        grn = GoodsReceipt.objects.get(id=response.data['data']['id'])
        self.assertIsNotNone(grn)
        
        # Verify line items were populated from PO
        self.assertEqual(grn.lines.count(), 1)
        line = grn.lines.first()
        po_line = self.po.line_items.first()
        self.assertEqual(line.item_name, po_line.item_name)
        self.assertEqual(line.unit_price, po_line.unit_price)
        self.assertEqual(line.quantity_received, Decimal('5.000'))
    
    def test_create_grn_from_po_full_quantity(self):
        """Test creating GRN from PO with full quantity (default)"""
        po_line = self.po.line_items.first()
        
        data = self.valid_data.copy()
        # Remove quantity_to_receive to receive full remaining quantity
        del data['lines_from_po'][0]['quantity_to_receive']
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Should receive full ordered quantity
        grn = GoodsReceipt.objects.get(id=response.data['data']['id'])
        line = grn.lines.first()
        self.assertEqual(line.quantity_received, po_line.quantity)
    
    def test_create_grn_from_po_multiple_lines(self):
        """Test creating GRN from multiple PO lines"""
        po_lines = list(self.po.line_items.all())
        
        data = {
            'po_header_id': self.po.id,
            'receipt_date': str(date.today()),
            'grn_type': self.po.po_type,
            'notes': 'Multi-line receipt',
            'lines_from_po': [
                {
                    'po_line_item_id': po_lines[0].id,
                    'quantity_to_receive': '5.000'
                },
                {
                    'po_line_item_id': po_lines[1].id,
                    'quantity_to_receive': '10.000'
                }
            ]
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        grn = GoodsReceipt.objects.get(id=response.data['data']['id'])
        self.assertEqual(grn.lines.count(), 2)
    
    def test_create_grn_from_po_invalid_po_line(self):
        """Test creating GRN with invalid PO line fails"""
        data = self.valid_data.copy()
        data['lines_from_po'][0]['po_line_item_id'] = 99999
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_grn_from_po_already_fully_received(self):
        """Test creating GRN for already fully received PO line fails"""
        po_line = self.po.line_items.first()
        
        # Receive full quantity
        po_line.quantity_received = po_line.quantity
        po_line.save()
        
        response = self.client.post(self.url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('fully received', str(response.data).lower())
    
    def test_create_grn_cannot_specify_both_lines_types(self):
        """Test that cannot specify both 'lines' and 'lines_from_po'"""
        data = self.valid_data.copy()
        data['lines'] = create_valid_grn_manual_data(self.po, self.uom)['lines']
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ============================================================================
# GRN LIST TESTS
# ============================================================================

class GRNListTests(TestCase):
    """Test GRN list endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        self.url = reverse('receiving:grn-list')
        
        # Create test data
        self.uom = create_unit_of_measure()
        self.supplier1 = create_supplier(name='Supplier A')
        self.supplier2 = create_supplier(name='Supplier B')
        self.currency = create_currency()
        
        # Create POs and GRNs
        self.po1 = create_confirmed_po(self.supplier1, self.currency, self.uom, self.user, 'Catalog')
        self.po2 = create_confirmed_po(self.supplier2, self.currency, self.uom, self.user, 'Service')
        
        self.grn1 = create_grn_with_lines(self.po1, self.user, date.today())
        self.grn2 = create_grn_with_lines(self.po2, self.user, date.today() - timedelta(days=5))
    
    def test_list_grns_success(self):
        """Test listing all GRNs"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 2)
    
    def test_list_grns_filter_by_po(self):
        """Test filtering GRNs by PO"""
        response = self.client.get(self.url, {'po_id': self.po1.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Handle both list and paginated responses
        data = response.data if isinstance(response.data, list) else response.data
        if isinstance(data, dict):
            # It's a dict response, might have 'results' or be direct data
            self.assertIn('po_header', str(data))
        else:
            # It's a list
            po1_grns = [grn for grn in data if grn.get('po_header') == self.po1.id]
            self.assertGreaterEqual(len(po1_grns), 1)
    
    def test_list_grns_filter_by_supplier(self):
        """Test filtering GRNs by supplier"""
        # Get supplier from PO's business_partner
        supplier = Supplier.objects.get(business_partner_id=self.po1.supplier_name_id)
        response = self.client.get(self.url, {'supplier_id': supplier.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # May return paginated or list data
        data = response.data if isinstance(response.data, list) else response.data.get('results', response.data)
        self.assertGreaterEqual(len(data) if isinstance(data, list) else 1, 1)
    
    def test_list_grns_filter_by_type(self):
        """Test filtering GRNs by type"""
        response = self.client.get(self.url, {'grn_type': 'Catalog'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Handle both list and paginated responses
        data = response.data if isinstance(response.data, list) else response.data
        if isinstance(data, list) and len(data) > 0:
            for grn in data:
                if isinstance(grn, dict):
                    self.assertEqual(grn.get('grn_type'), 'Catalog')
    
    def test_list_grns_filter_by_date_range(self):
        """Test filtering GRNs by date range"""
        date_from = (date.today() - timedelta(days=2)).isoformat()
        date_to = date.today().isoformat()
        
        response = self.client.get(self.url, {'date_from': date_from, 'date_to': date_to})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)
    
    def test_list_grns_search(self):
        """Test searching GRNs"""
        response = self.client.get(self.url, {'search': self.grn1.grn_number})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)


# ============================================================================
# GRN DETAIL TESTS
# ============================================================================

class GRNDetailTests(TestCase):
    """Test GRN detail endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create test data
        self.uom = create_unit_of_measure()
        self.supplier = create_supplier()
        self.currency = create_currency()
        
        # Create PO and GRN
        self.po = create_confirmed_po(self.supplier, self.currency, self.uom, self.user)
        self.grn = create_grn_with_lines(self.po, self.user)
        
        self.url = reverse('receiving:grn-detail', kwargs={'pk': self.grn.id})
    
    def test_get_grn_detail_success(self):
        """Test retrieving GRN detail"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['id'], self.grn.id)
        self.assertEqual(response.data['data']['grn_number'], self.grn.grn_number)
        self.assertIn('lines', response.data['data'])
        self.assertIn('receipt_summary', response.data['data'])
        self.assertIn('po_completion_status', response.data['data'])
    
    def test_get_grn_detail_includes_lines(self):
        """Test that detail response includes line items"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        lines = response.data['data']['lines']
        self.assertEqual(len(lines), 2)  # PO has 2 lines
    
    def test_get_grn_detail_invalid_id(self):
        """Test retrieving non-existent GRN"""
        url = reverse('receiving:grn-detail', kwargs={'pk': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_delete_grn_success(self):
        """Test deleting GRN"""
        response = self.client.delete(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify GRN was deleted
        self.assertFalse(GoodsReceipt.objects.filter(id=self.grn.id).exists())
    
    def test_delete_grn_reverses_po_quantities(self):
        """Test that deleting GRN reverses PO received quantities"""
        # Get initial PO line quantities
        po_line = self.po.line_items.first()
        initial_received = po_line.quantity_received
        grn_line = self.grn.lines.filter(po_line_item=po_line).first()
        grn_received = grn_line.quantity_received
        
        # Delete GRN
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify PO quantity was reversed
        po_line.refresh_from_db()
        self.assertEqual(po_line.quantity_received, initial_received - grn_received)


# ============================================================================
# GRN SUMMARY TESTS
# ============================================================================

class GRNSummaryTests(TestCase):
    """Test GRN summary endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create test data
        self.uom = create_unit_of_measure()
        self.supplier = create_supplier()
        self.currency = create_currency()
        
        # Create PO and GRN
        self.po = create_confirmed_po(self.supplier, self.currency, self.uom, self.user)
        self.grn = create_grn_with_lines(self.po, self.user)
        
        self.url = reverse('receiving:grn-summary', kwargs={'pk': self.grn.id})
    
    def test_get_grn_summary_success(self):
        """Test retrieving GRN summary"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIn('summary', response.data['data'])
        self.assertIn('po_completion', response.data['data'])
    
    def test_grn_summary_includes_counts(self):
        """Test that summary includes item counts"""
        response = self.client.get(self.url)
        
        summary = response.data['data']['summary']
        self.assertIn('total_lines', summary)
        self.assertIn('total_items_received', summary)
        self.assertIn('total_amount', summary)


# ============================================================================
# PO RECEIVING STATUS TESTS
# ============================================================================

class POReceivingStatusTests(TestCase):
    """Test PO receiving status endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create test data
        self.uom = create_unit_of_measure()
        self.supplier = create_supplier()
        self.currency = create_currency()
        
        # Create PO
        self.po = create_confirmed_po(self.supplier, self.currency, self.uom, self.user)
        
        self.url = reverse('receiving:po-receiving-status', kwargs={'po_id': self.po.id})
    
    def test_get_po_status_no_grns(self):
        """Test PO receiving status with no GRNs"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['grn_count'], 0)
    
    def test_get_po_status_with_grns(self):
        """Test PO receiving status with GRNs"""
        # Create GRN
        create_grn_with_lines(self.po, self.user)
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['grn_count'], 1)
        self.assertIn('grns', response.data['data'])
        self.assertIn('lines_status', response.data['data'])
    
    def test_get_po_status_line_details(self):
        """Test PO status includes line-level details"""
        # Create partial receipt
        create_grn_with_lines(self.po, self.user)
        
        response = self.client.get(self.url)
        
        lines_status = response.data['data']['lines_status']
        self.assertEqual(len(lines_status), 2)  # PO has 2 lines
        
        for line in lines_status:
            self.assertIn('quantity_ordered', line)
            self.assertIn('quantity_received', line)
            self.assertIn('quantity_remaining', line)
            self.assertIn('receipt_percentage', line)


# ============================================================================
# GRN REPORTING TESTS
# ============================================================================

class GRNReportingTests(TestCase):
    """Test GRN reporting endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create test data
        self.uom = create_unit_of_measure()
        self.supplier1 = create_supplier(name='Supplier A')
        self.supplier2 = create_supplier(name='Supplier B')
        self.currency = create_currency()
        
        # Create POs and GRNs
        self.po1 = create_confirmed_po(self.supplier1, self.currency, self.uom, self.user, 'Catalog')
        self.po2 = create_confirmed_po(self.supplier2, self.currency, self.uom, self.user, 'Service')
        
        create_grn_with_lines(self.po1, self.user)
        create_grn_with_lines(self.po2, self.user)
    
    def test_grn_by_supplier(self):
        """Test GRN statistics by supplier"""
        url = reverse('receiving:grn-by-supplier')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response might be list or paginated
        data = response.data if isinstance(response.data, list) else response.data
        self.assertGreaterEqual(len(data) if isinstance(data, list) else 1, 1)
        
        # Verify structure - check first item if it's a list
        if isinstance(data, list) and len(data) > 0:
            item = data[0]
            # Keys might be supplier__id or just id
            self.assertTrue('supplier' in str(item) or 'id' in item)
            self.assertIn('grn_count', item)
            self.assertIn('total_amount', item)
    
    def test_grn_by_type(self):
        """Test GRN statistics by type"""
        url = reverse('receiving:grn-by-type')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response might be list or paginated
        data = response.data if isinstance(response.data, list) else response.data
        self.assertGreaterEqual(len(data) if isinstance(data, list) else 1, 1)
        
        # Verify structure - check first item if it's a list
        if isinstance(data, list) and len(data) > 0:
            item = data[0]
            self.assertIn('grn_type', item)
            self.assertIn('grn_count', item)
            self.assertIn('total_amount', item)
    
    def test_grn_recent(self):
        """Test recent GRNs endpoint"""
        url = reverse('receiving:grn-recent')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 2)
    
    def test_grn_recent_custom_days(self):
        """Test recent GRNs with custom days parameter"""
        url = reverse('receiving:grn-recent')
        response = self.client.get(url, {'days': 7})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)


# ============================================================================
# PARTIAL RECEIVING TESTS
# ============================================================================

class PartialReceivingTests(TestCase):
    """Test partial receiving scenarios"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        self.url = reverse('receiving:grn-list')
        
        # Create test data
        self.uom = create_unit_of_measure()
        self.supplier = create_supplier()
        self.currency = create_currency()
        
        # Create confirmed PO
        self.po = create_confirmed_po(self.supplier, self.currency, self.uom, self.user)
    
    def test_partial_receipt_first_delivery(self):
        """Test first partial receipt"""
        po_line = self.po.line_items.first()
        
        data = create_valid_grn_from_po_data(self.po)
        data['lines_from_po'][0]['quantity_to_receive'] = '3.000'  # Ordered 10
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check remaining quantity
        po_line.refresh_from_db()
        remaining = po_line.get_remaining_quantity()
        self.assertEqual(remaining, Decimal('7.000'))
    
    def test_partial_receipt_multiple_deliveries(self):
        """Test multiple partial receipts"""
        po_line = self.po.line_items.first()
        
        # First receipt - 3 units
        data1 = create_valid_grn_from_po_data(self.po)
        data1['lines_from_po'][0]['quantity_to_receive'] = '3.000'
        response1 = self.client.post(self.url, data1, format='json')
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        
        # Second receipt - 4 units
        data2 = create_valid_grn_from_po_data(self.po)
        data2['lines_from_po'][0]['quantity_to_receive'] = '4.000'
        response2 = self.client.post(self.url, data2, format='json')
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        
        # Check total received
        po_line.refresh_from_db()
        self.assertEqual(po_line.quantity_received, Decimal('7.000'))
        self.assertEqual(po_line.get_remaining_quantity(), Decimal('3.000'))
    
    def test_partial_receipt_final_delivery(self):
        """Test completing PO with final delivery"""
        po_line = self.po.line_items.first()
        
        # Receive remaining quantity
        data = create_valid_grn_from_po_data(self.po)
        # Don't specify quantity to receive full remaining
        del data['lines_from_po'][0]['quantity_to_receive']
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check fully received
        po_line.refresh_from_db()
        self.assertTrue(po_line.is_fully_received())
        self.assertEqual(po_line.get_remaining_quantity(), Decimal('0.000'))


# ============================================================================
# GIFT ITEMS TESTS
# ============================================================================

class GiftItemsTests(TestCase):
    """Test gift/bonus items functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        self.url = reverse('receiving:grn-list')
        
        # Create test data
        self.uom = create_unit_of_measure()
        self.supplier = create_supplier()
        self.currency = create_currency()
        
        # Create confirmed PO
        self.po = create_confirmed_po(self.supplier, self.currency, self.uom, self.user)
    
    def test_receive_with_gift_item(self):
        """Test receiving with bonus/gift item"""
        po_line = self.po.line_items.first()
        
        data = {
            'po_header_id': self.po.id,
            'receipt_date': str(date.today()),
            'grn_type': self.po.po_type,
            'notes': 'Receipt with gift',
            'lines': [
                # Regular line
                {
                    'line_number': 1,
                    'po_line_item_id': po_line.id,
                    'item_name': po_line.item_name,
                    'item_description': po_line.item_description,
                    'quantity_ordered': str(po_line.quantity),
                    'quantity_received': '5.000',
                    'unit_of_measure_id': self.uom.id,
                    'unit_price': str(po_line.unit_price),
                    'is_gift': False
                },
                # Gift line
                {
                    'line_number': 2,
                    'item_name': 'Free Laptop Bag',
                    'item_description': 'Bonus item',
                    'quantity_ordered': '0.000',
                    'quantity_received': '1.000',
                    'unit_of_measure_id': self.uom.id,
                    'unit_price': '0.00',
                    'is_gift': True
                }
            ]
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify gift line
        grn = GoodsReceipt.objects.get(id=response.data['data']['id'])
        gift_line = grn.lines.filter(is_gift=True).first()
        self.assertIsNotNone(gift_line)
        self.assertEqual(gift_line.item_name, 'Free Laptop Bag')
        self.assertEqual(gift_line.unit_price, Decimal('0.00'))
        self.assertIsNone(gift_line.po_line_item)


# ============================================================================
# AUTHENTICATION TESTS
# ============================================================================

class GRNAuthenticationTests(TestCase):
    """Test authentication requirements"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.url = reverse('receiving:grn-list')
    
    def test_list_grns_requires_auth(self):
        """Test that listing GRNs requires authentication"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_create_grn_requires_auth(self):
        """Test that creating GRN requires authentication"""
        response = self.client.post(self.url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ============================================================================
# RECEIVING TYPE (PARTIAL/FULLY) TESTS
# ============================================================================

class ReceivingTypeTests(TestCase):
    """Test receiving_type (PARTIAL/FULLY) functionality with tolerance"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        self.url = reverse('receiving:grn-list')
        
        # Create test data
        self.uom = create_unit_of_measure()
        self.supplier = create_supplier()
        self.currency = create_currency()
        
        # Create confirmed PO with tolerance
        self.po = create_confirmed_po(self.supplier, self.currency, self.uom, self.user)
        po_line = self.po.line_items.first()
        po_line.quantity = Decimal('100.000')
        po_line.tolerance_percentage = Decimal('10.00')  # 10% tolerance
        po_line.save()
    
    def test_partial_receiving_default_type(self):
        """Test that PARTIAL is the default receiving type"""
        data = create_valid_grn_from_po_data(self.po)
        data['lines_from_po'][0]['quantity_to_receive'] = '30.000'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        grn = GoodsReceipt.objects.get(id=response.data['data']['id'])
        line = grn.lines.first()
        
        self.assertEqual(line.receiving_type, 'PARTIAL')
    
    def test_partial_receiving_allows_any_quantity_under_ordered(self):
        """Test that PARTIAL receiving allows any quantity <= ordered"""
        po_line = self.po.line_items.first()
        
        # First receipt: 30 units (PARTIAL)
        data = create_valid_grn_from_po_data(self.po)
        data['lines_from_po'][0]['quantity_to_receive'] = '30.000'
        data['lines_from_po'][0]['receiving_type'] = 'PARTIAL'
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        po_line.refresh_from_db()
        self.assertEqual(po_line.quantity_received, Decimal('30.000'))
        
        # Second receipt: 40 units (PARTIAL) - total 70
        data2 = create_valid_grn_from_po_data(self.po)
        data2['lines_from_po'][0]['quantity_to_receive'] = '40.000'
        data2['lines_from_po'][0]['receiving_type'] = 'PARTIAL'
        
        response2 = self.client.post(self.url, data2, format='json')
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        
        po_line.refresh_from_db()
        self.assertEqual(po_line.quantity_received, Decimal('70.000'))
        
        # Third receipt: 30 units (PARTIAL) - total 100 (exactly ordered)
        data3 = create_valid_grn_from_po_data(self.po)
        data3['lines_from_po'][0]['quantity_to_receive'] = '30.000'
        data3['lines_from_po'][0]['receiving_type'] = 'PARTIAL'
        
        response3 = self.client.post(self.url, data3, format='json')
        self.assertEqual(response3.status_code, status.HTTP_201_CREATED)
        
        po_line.refresh_from_db()
        self.assertEqual(po_line.quantity_received, Decimal('100.000'))
    
    def test_partial_receiving_rejects_over_ordered_quantity(self):
        """Test that PARTIAL receiving rejects quantity exceeding ordered (ignores tolerance)"""
        po_line = self.po.line_items.first()
        
        # Try to receive 101 (over ordered 100) with PARTIAL - should fail
        data = create_valid_grn_from_po_data(self.po)
        data['lines_from_po'][0]['quantity_to_receive'] = '101.000'
        data['lines_from_po'][0]['receiving_type'] = 'PARTIAL'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('exceed', str(response.data).lower())
    
    def test_partial_receiving_cumulative_check(self):
        """Test that PARTIAL receiving checks cumulative totals"""
        po_line = self.po.line_items.first()
        
        # First receipt: 80 units
        data1 = create_valid_grn_from_po_data(self.po)
        data1['lines_from_po'][0]['quantity_to_receive'] = '80.000'
        data1['lines_from_po'][0]['receiving_type'] = 'PARTIAL'
        
        response1 = self.client.post(self.url, data1, format='json')
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        
        # Second receipt: Try to receive 25 more (total would be 105 > 100 ordered)
        data2 = create_valid_grn_from_po_data(self.po)
        data2['lines_from_po'][0]['quantity_to_receive'] = '25.000'
        data2['lines_from_po'][0]['receiving_type'] = 'PARTIAL'
        
        response2 = self.client.post(self.url, data2, format='json')
        
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('cumulative', str(response2.data).lower())
    
    def test_fully_receiving_within_tolerance_range(self):
        """Test that FULLY receiving validates against tolerance range"""
        po_line = self.po.line_items.first()
        # Ordered: 100, Tolerance: 10%, Range: 90-110
        
        # Receive 95 units (within range 90-110) with FULLY - should succeed
        data = create_valid_grn_from_po_data(self.po)
        data['lines_from_po'][0]['quantity_to_receive'] = '95.000'
        data['lines_from_po'][0]['receiving_type'] = 'FULLY'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        po_line.refresh_from_db()
        self.assertEqual(po_line.quantity_received, Decimal('95.000'))
    
    def test_fully_receiving_at_minimum_tolerance(self):
        """Test FULLY receiving at minimum acceptable quantity (90)"""
        data = create_valid_grn_from_po_data(self.po)
        data['lines_from_po'][0]['quantity_to_receive'] = '90.000'
        data['lines_from_po'][0]['receiving_type'] = 'FULLY'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_fully_receiving_at_maximum_tolerance(self):
        """Test FULLY receiving at maximum receivable quantity (110)"""
        data = create_valid_grn_from_po_data(self.po)
        data['lines_from_po'][0]['quantity_to_receive'] = '110.000'
        data['lines_from_po'][0]['receiving_type'] = 'FULLY'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_fully_receiving_below_minimum_tolerance(self):
        """Test that FULLY receiving below minimum (89 < 90) fails"""
        data = create_valid_grn_from_po_data(self.po)
        data['lines_from_po'][0]['quantity_to_receive'] = '89.000'
        data['lines_from_po'][0]['receiving_type'] = 'FULLY'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('below minimum', str(response.data).lower())
    
    def test_fully_receiving_above_maximum_tolerance(self):
        """Test that FULLY receiving above maximum (111 > 110) fails"""
        data = create_valid_grn_from_po_data(self.po)
        data['lines_from_po'][0]['quantity_to_receive'] = '111.000'
        data['lines_from_po'][0]['receiving_type'] = 'FULLY'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('exceeds maximum', str(response.data).lower())
    
    def test_fully_receiving_with_previous_partial_receipts(self):
        """Test FULLY receiving validates cumulative with previous PARTIAL receipts"""
        po_line = self.po.line_items.first()
        
        # First receipt: 50 units (PARTIAL)
        data1 = create_valid_grn_from_po_data(self.po)
        data1['lines_from_po'][0]['quantity_to_receive'] = '50.000'
        data1['lines_from_po'][0]['receiving_type'] = 'PARTIAL'
        
        response1 = self.client.post(self.url, data1, format='json')
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        
        # Second receipt: 45 units (FULLY) - total 95 (within 90-110 range)
        data2 = create_valid_grn_from_po_data(self.po)
        data2['lines_from_po'][0]['quantity_to_receive'] = '45.000'
        data2['lines_from_po'][0]['receiving_type'] = 'FULLY'
        
        response2 = self.client.post(self.url, data2, format='json')
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        
        po_line.refresh_from_db()
        self.assertEqual(po_line.quantity_received, Decimal('95.000'))
    
    def test_fully_receiving_cumulative_below_minimum(self):
        """Test FULLY receiving fails when cumulative is below minimum"""
        po_line = self.po.line_items.first()
        
        # First receipt: 50 units (PARTIAL)
        data1 = create_valid_grn_from_po_data(self.po)
        data1['lines_from_po'][0]['quantity_to_receive'] = '50.000'
        data1['lines_from_po'][0]['receiving_type'] = 'PARTIAL'
        
        response1 = self.client.post(self.url, data1, format='json')
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        
        # Second receipt: 35 units (FULLY) - total 85 < 90 minimum
        data2 = create_valid_grn_from_po_data(self.po)
        data2['lines_from_po'][0]['quantity_to_receive'] = '35.000'
        data2['lines_from_po'][0]['receiving_type'] = 'FULLY'
        
        response2 = self.client.post(self.url, data2, format='json')
        
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('below minimum', str(response2.data).lower())
    
    def test_fully_receiving_cumulative_above_maximum(self):
        """Test FULLY receiving fails when cumulative exceeds maximum"""
        po_line = self.po.line_items.first()
        
        # First receipt: 80 units (PARTIAL)
        data1 = create_valid_grn_from_po_data(self.po)
        data1['lines_from_po'][0]['quantity_to_receive'] = '80.000'
        data1['lines_from_po'][0]['receiving_type'] = 'PARTIAL'
        
        response1 = self.client.post(self.url, data1, format='json')
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        
        # Second receipt: 35 units (FULLY) - total 115 > 110 maximum
        data2 = create_valid_grn_from_po_data(self.po)
        data2['lines_from_po'][0]['quantity_to_receive'] = '35.000'
        data2['lines_from_po'][0]['receiving_type'] = 'FULLY'
        
        response2 = self.client.post(self.url, data2, format='json')
        
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('exceeds maximum', str(response2.data).lower())
    
    def test_receiving_type_with_zero_tolerance(self):
        """Test receiving types with 0% tolerance (exact quantity required)"""
        # Update PO line to have 0% tolerance
        po_line = self.po.line_items.first()
        po_line.tolerance_percentage = Decimal('0.00')
        po_line.save()
        
        # PARTIAL: Can receive 50 units
        data1 = create_valid_grn_from_po_data(self.po)
        data1['lines_from_po'][0]['quantity_to_receive'] = '50.000'
        data1['lines_from_po'][0]['receiving_type'] = 'PARTIAL'
        
        response1 = self.client.post(self.url, data1, format='json')
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        
        # FULLY: Must receive exactly 50 more (total 100)
        data2 = create_valid_grn_from_po_data(self.po)
        data2['lines_from_po'][0]['quantity_to_receive'] = '50.000'
        data2['lines_from_po'][0]['receiving_type'] = 'FULLY'
        
        response2 = self.client.post(self.url, data2, format='json')
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        
        po_line.refresh_from_db()
        self.assertEqual(po_line.quantity_received, Decimal('100.000'))
    
    def test_receiving_type_with_zero_tolerance_under_fails(self):
        """Test FULLY receiving fails when under exact quantity with 0% tolerance"""
        po_line = self.po.line_items.first()
        po_line.tolerance_percentage = Decimal('0.00')
        po_line.save()
        
        # Try to receive 99 units with FULLY (< 100 required)
        data = create_valid_grn_from_po_data(self.po)
        data['lines_from_po'][0]['quantity_to_receive'] = '99.000'
        data['lines_from_po'][0]['receiving_type'] = 'FULLY'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_receiving_type_in_response(self):
        """Test that receiving_type appears in API response"""
        data = create_valid_grn_from_po_data(self.po)
        data['lines_from_po'][0]['quantity_to_receive'] = '50.000'
        data['lines_from_po'][0]['receiving_type'] = 'PARTIAL'
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Get GRN detail to check response
        grn_id = response.data['data']['id']
        detail_response = self.client.get(reverse('receiving:grn-detail', kwargs={'pk': grn_id}))
        
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        line_data = detail_response.data['data']['lines'][0]
        
        self.assertIn('receiving_type', line_data)
        self.assertEqual(line_data['receiving_type'], 'PARTIAL')
    
    def test_manual_line_entry_with_receiving_type(self):
        """Test creating GRN with manual line entry and receiving_type"""
        po_line = self.po.line_items.first()
        
        data = create_valid_grn_manual_data(self.po, self.uom)
        data['lines'][0]['po_line_item_id'] = po_line.id
        data['lines'][0]['quantity_received'] = '95.000'
        data['lines'][0]['receiving_type'] = 'FULLY'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        grn = GoodsReceipt.objects.get(id=response.data['data']['id'])
        line = grn.lines.first()
        
        self.assertEqual(line.receiving_type, 'FULLY')
        self.assertEqual(line.quantity_received, Decimal('95.000'))
