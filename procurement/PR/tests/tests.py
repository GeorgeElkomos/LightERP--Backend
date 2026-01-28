"""
Comprehensive tests for Purchase Requisition (PR) API endpoints.
Tests all CRUD operations, approval workflow, filtering, and PR-to-PO conversion.
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from datetime import date, timedelta
from decimal import Decimal

from procurement.PR.models import PR, PRItem, Catalog_PR, NonCatalog_PR, Service_PR
from procurement.catalog.models import UnitOfMeasure, catalogItem

User = get_user_model()


class PRTestBase(TestCase):
    """Base class with common setup for PR tests"""
    
    def setUp(self):
        self.client = APIClient()
        
        # Create test user
        self.user = User.objects.create_user(
            email='testuser@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create UoM
        self.uom_pcs = UnitOfMeasure.objects.create(
            code='PCS',
            name='Pieces',
            uom_type='QUANTITY'
        )
        
        # Create catalog item
        self.catalog_item = catalogItem.objects.create(
            code='LAPTOP01',
            name='Dell Laptop',
            description='Business laptop'
        )


# ============================================================================
# CATALOG PR TESTS
# ============================================================================

class CatalogPRCreateTests(PRTestBase):
    """Test creating Catalog PRs"""
    
    def setUp(self):
        super().setUp()
        self.url = '/procurement/pr/catalog/'
    
    def test_create_catalog_pr_success(self):
        """Test successful Catalog PR creation"""
        data = {
            'date': str(date.today()),
            'required_date': str(date.today() + timedelta(days=10)),
            'requester_name': 'John Doe',
            'requester_department': 'IT',
            'requester_email': 'john@example.com',
            'priority': 'MEDIUM',
            'description': 'IT equipment purchase',
            'items': [
                {
                    'item_name': 'Dell Laptop',
                    'item_description': 'High-performance laptop',
                    'catalog_item_id': self.catalog_item.id,
                    'quantity': '10',
                    'unit_of_measure_id': self.uom_pcs.id,
                    'estimated_unit_price': '1200.00',
                    'notes': 'Urgent need'
                }
            ]
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'success')
        self.assertIn('pr_number', response.data['data'])
        self.assertEqual(response.data['data']['requester_name'], 'John Doe')
        self.assertEqual(len(response.data['data']['items']), 1)
        
        # Verify in database
        pr = PR.objects.get(pr_number=response.data['data']['pr_number'])
        self.assertEqual(pr.type_of_pr, 'Catalog')
        self.assertEqual(pr.status, 'DRAFT')
        self.assertEqual(pr.items.count(), 1)
    
    def test_create_catalog_pr_without_items_fails(self):
        """Test creating Catalog PR without items fails"""
        data = {
            'date': str(date.today()),
            'required_date': str(date.today() + timedelta(days=10)),
            'requester_name': 'John Doe',
            'requester_department': 'IT',
            'items': []
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('items', response.data['data'])
    
    def test_create_catalog_pr_without_catalog_item_fails(self):
        """Test creating Catalog PR item without catalog_item_id fails"""
        data = {
            'date': str(date.today()),
            'required_date': str(date.today() + timedelta(days=10)),
            'requester_name': 'John Doe',
            'requester_department': 'IT',
            'items': [
                {
                    'item_name': 'Dell Laptop',
                    'quantity': '10',
                    'unit_of_measure_id': self.uom_pcs.id,
                    'estimated_unit_price': '1200.00'
                }
            ]
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_catalog_pr_calculates_total(self):
        """Test that total is calculated correctly"""
        data = {
            'date': str(date.today()),
            'required_date': str(date.today() + timedelta(days=10)),
            'requester_name': 'John Doe',
            'requester_department': 'IT',
            'items': [
                {
                    'item_name': 'Dell Laptop',
                    'catalog_item_id': self.catalog_item.id,
                    'quantity': '10',
                    'unit_of_measure_id': self.uom_pcs.id,
                    'estimated_unit_price': '1200.00'
                }
            ]
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(response.data['data']['total']), Decimal('12000.00'))


class CatalogPRListTests(PRTestBase):
    """Test listing Catalog PRs"""
    
    def setUp(self):
        super().setUp()
        self.url = '/procurement/pr/catalog/'
        
        # Create test PRs
        for i in range(3):
            catalog_pr = Catalog_PR.objects.create(
                date=date.today(),
                required_date=date.today() + timedelta(days=10),
                requester_name=f'User {i}',
                requester_department='IT',
                priority='MEDIUM'
            )
            PRItem.objects.create(
                pr=catalog_pr.pr,
                item_name=f'Item {i}',
                catalog_item=self.catalog_item,
                quantity=10,
                unit_of_measure=self.uom_pcs,
                estimated_unit_price=1000
            )
    
    def test_list_catalog_prs(self):
        """Test listing all Catalog PRs"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        # Check count from pagination
        self.assertEqual(response.data['data']['count'], 3)
        self.assertEqual(len(response.data['data']['results']), 3)
    
    def test_filter_catalog_prs_by_status(self):
        """Test filtering Catalog PRs by status"""
        response = self.client.get(self.url, {'status': 'DRAFT'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['count'], 3)
    
    def test_filter_catalog_prs_by_department(self):
        """Test filtering Catalog PRs by department"""
        response = self.client.get(self.url, {'requester_department': 'IT'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['count'], 3)


class CatalogPRDetailTests(PRTestBase):
    """Test Catalog PR detail operations"""
    
    def setUp(self):
        super().setUp()
        
        # Create a test PR
        self.catalog_pr = Catalog_PR.objects.create(
            date=date.today(),
            required_date=date.today() + timedelta(days=10),
            requester_name='John Doe',
            requester_department='IT'
        )
        self.pr_item = PRItem.objects.create(
            pr=self.catalog_pr.pr,
            item_name='Dell Laptop',
            catalog_item=self.catalog_item,
            quantity=10,
            unit_of_measure=self.uom_pcs,
            estimated_unit_price=1200
        )
    
    def test_get_catalog_pr_detail(self):
        """Test retrieving Catalog PR details"""
        url = f'/procurement/pr/catalog/{self.catalog_pr.pr.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['requester_name'], 'John Doe')
        self.assertEqual(len(response.data['data']['items']), 1)
    
    def test_delete_draft_catalog_pr(self):
        """Test deleting a draft Catalog PR"""
        url = f'/procurement/pr/catalog/{self.catalog_pr.pr.id}/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Catalog_PR.objects.filter(pr=self.catalog_pr.pr).exists())


# ============================================================================
# NON-CATALOG PR TESTS
# ============================================================================

class NonCatalogPRCreateTests(PRTestBase):
    """Test creating Non-Catalog PRs"""
    
    def setUp(self):
        super().setUp()
        self.url = '/procurement/pr/non-catalog/'
    
    def test_create_noncatalog_pr_success(self):
        """Test successful Non-Catalog PR creation"""
        data = {
            'date': str(date.today()),
            'required_date': str(date.today() + timedelta(days=10)),
            'requester_name': 'Jane Smith',
            'requester_department': 'Engineering',
            'priority': 'HIGH',
            'items': [
                {
                    'item_name': 'Custom Equipment',
                    'item_description': 'Special equipment not in catalog',
                    'quantity': '5',
                    'unit_of_measure_id': self.uom_pcs.id,
                    'estimated_unit_price': '5000.00'
                }
            ]
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('pr_number', response.data['data'])
        
        # Verify type
        pr = PR.objects.get(pr_number=response.data['data']['pr_number'])
        self.assertEqual(pr.type_of_pr, 'Non-Catalog')


# ============================================================================
# SERVICE PR TESTS
# ============================================================================

class ServicePRCreateTests(PRTestBase):
    """Test creating Service PRs"""
    
    def setUp(self):
        super().setUp()
        self.url = '/procurement/pr/service/'
    
    def test_create_service_pr_success(self):
        """Test successful Service PR creation"""
        data = {
            'date': str(date.today()),
            'required_date': str(date.today() + timedelta(days=10)),
            'requester_name': 'Bob Johnson',
            'requester_department': 'Facilities',
            'priority': 'URGENT',
            'items': [
                {
                    'item_name': 'HVAC Maintenance',
                    'item_description': 'Annual maintenance service',
                    'quantity': '1',
                    'unit_of_measure_id': self.uom_pcs.id,
                    'estimated_unit_price': '15000.00'
                }
            ]
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify type
        pr = PR.objects.get(pr_number=response.data['data']['pr_number'])
        self.assertEqual(pr.type_of_pr, 'Service')


# ============================================================================
# PR-TO-PO CONVERSION TESTS
# ============================================================================

class PRConversionTests(PRTestBase):
    """Test PR-to-PO conversion endpoints"""
    
    def setUp(self):
        super().setUp()
        
        # Create approved Catalog PR
        self.catalog_pr = Catalog_PR.objects.create(
            date=date.today(),
            required_date=date.today() + timedelta(days=10),
            requester_name='John Doe',
            requester_department='IT'
        )
        self.catalog_pr.pr.status = 'APPROVED'
        self.catalog_pr.pr._allow_direct_save = True
        self.catalog_pr.pr.save()
        
        self.pr_item = PRItem.objects.create(
            pr=self.catalog_pr.pr,
            item_name='Dell Laptop',
            catalog_item=self.catalog_item,
            quantity=10,
            unit_of_measure=self.uom_pcs,
            estimated_unit_price=1200
        )
    
    def test_get_approved_prs_for_conversion(self):
        """Test getting approved PRs filtered by type"""
        url = '/procurement/pr/approved-for-conversion/'
        response = self.client.get(url, {'pr_type': 'Catalog'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertGreaterEqual(len(response.data['data']), 1)
        self.assertEqual(response.data['data'][0]['pr_type'], 'Catalog')
    
    def test_get_approved_prs_invalid_type_fails(self):
        """Test getting approved PRs with invalid type fails"""
        url = '/procurement/pr/approved-for-conversion/'
        response = self.client.get(url, {'pr_type': 'Invalid'})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_get_pr_available_items(self):
        """Test getting available items from specific PR"""
        url = f'/procurement/pr/{self.catalog_pr.pr.id}/available-items/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['pr_type'], 'Catalog')
        self.assertEqual(len(response.data['data']['items']), 1)
        self.assertEqual(response.data['data']['items'][0]['remaining_quantity'], 10.0)
    
    def test_get_items_by_type(self):
        """Test getting all available items filtered by type"""
        url = '/procurement/pr/items-by-type/'
        response = self.client.get(url, {'pr_type': 'Catalog'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['pr_type'], 'Catalog')
        self.assertGreaterEqual(response.data['data']['total_items'], 1)
    
    def test_partial_conversion_tracking(self):
        """Test that partial conversion updates quantity_converted"""
        # Simulate partial conversion
        self.pr_item.quantity_converted = 5
        self.pr_item.save()
        
        url = f'/procurement/pr/{self.catalog_pr.pr.id}/available-items/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        items = response.data['data']['items']
        self.assertEqual(items[0]['quantity_converted'], '5.00')
        self.assertEqual(items[0]['remaining_quantity'], 5.0)
        self.assertEqual(items[0]['conversion_percentage'], 50.0)


# ============================================================================
# APPROVAL WORKFLOW TESTS
# ============================================================================

class PRApprovalTests(PRTestBase):
    """Test PR approval workflow"""
    
    def setUp(self):
        super().setUp()
        
        # Create a Catalog PR
        self.catalog_pr = Catalog_PR.objects.create(
            date=date.today(),
            required_date=date.today() + timedelta(days=10),
            requester_name='John Doe',
            requester_department='IT'
        )
        PRItem.objects.create(
            pr=self.catalog_pr.pr,
            item_name='Dell Laptop',
            catalog_item=self.catalog_item,
            quantity=10,
            unit_of_measure=self.uom_pcs,
            estimated_unit_price=1200
        )
    
    def test_pr_initial_status_is_draft(self):
        """Test that new PR starts in DRAFT status"""
        self.assertEqual(self.catalog_pr.pr.status, 'DRAFT')
    
    def test_pr_has_approval_fields(self):
        """Test that PR has approval tracking fields"""
        self.assertIsNone(self.catalog_pr.pr.submitted_for_approval_at)
        self.assertIsNone(self.catalog_pr.pr.approved_at)
        self.assertEqual(self.catalog_pr.pr.approved_by, '')


# ============================================================================
# PRITEM MODEL TESTS
# ============================================================================

class PRItemTests(PRTestBase):
    """Test PRItem model methods"""
    
    def setUp(self):
        super().setUp()
        
        # Create a PR
        catalog_pr = Catalog_PR.objects.create(
            date=date.today(),
            required_date=date.today() + timedelta(days=10),
            requester_name='John Doe',
            requester_department='IT'
        )
        
        self.pr_item = PRItem.objects.create(
            pr=catalog_pr.pr,
            item_name='Dell Laptop',
            catalog_item=self.catalog_item,
            quantity=10,
            unit_of_measure=self.uom_pcs,
            estimated_unit_price=1200
        )
    
    def test_pr_item_total_calculation(self):
        """Test that item total is calculated correctly"""
        self.assertEqual(self.pr_item.total_price_per_item, Decimal('12000.00'))
    
    def test_pr_item_remaining_quantity(self):
        """Test remaining quantity calculation"""
        self.pr_item.quantity_converted = 3
        self.pr_item.save()
        
        remaining = self.pr_item.quantity - self.pr_item.quantity_converted
        self.assertEqual(remaining, Decimal('7.00'))
    
    def test_pr_item_conversion_status(self):
        """Test conversion status tracking"""
        self.assertFalse(self.pr_item.converted_to_po)
        self.assertEqual(self.pr_item.quantity_converted, 0)
        
        # Mark as fully converted
        self.pr_item.quantity_converted = 10
        self.pr_item.converted_to_po = True
        self.pr_item.save()
        
        self.assertTrue(self.pr_item.converted_to_po)

