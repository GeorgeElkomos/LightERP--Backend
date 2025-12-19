"""
Comprehensive tests for Non-Catalog PR API endpoints.

Tests all endpoints for Non-Catalog PRs (items not in the catalog).
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from datetime import date, timedelta

from procurement.PR.models import NonCatalog_PR, PR, PRItem
from procurement.PR.tests.fixtures import (
    create_unit_of_measure,
    create_catalog_item,
    create_valid_noncatalog_pr_data,
    get_or_create_test_user,
    create_simple_approval_template_for_pr,
    approve_pr_for_testing
)


class NonCatalogPRCreateTests(TestCase):
    """Test Non-Catalog PR creation endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        self.url = reverse('pr:noncatalog-pr-list')
        
        # Create test data
        self.uom = create_unit_of_measure()
        self.valid_data = create_valid_noncatalog_pr_data(self.uom)
    
    def test_create_noncatalog_pr_success(self):
        """Test successful Non-Catalog PR creation"""
        response = self.client.post(self.url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('pr_id', response.data)
        self.assertIn('pr_number', response.data)
        self.assertTrue(response.data['pr_number'].startswith('PR-NC'))
        self.assertEqual(response.data['requester_name'], 'Jane Smith')
        self.assertEqual(response.data['status'], 'DRAFT')
        
        # Verify PR was created
        pr = NonCatalog_PR.objects.get(pr_id=response.data['pr_id'])
        self.assertIsNotNone(pr)
        self.assertEqual(pr.pr.requester_department, 'Engineering')
        
        # Verify items were created
        self.assertEqual(pr.pr.items.count(), 1)
        item = pr.pr.items.first()
        self.assertEqual(item.item_name, 'Custom CNC Machine Part')
        self.assertEqual(item.quantity, Decimal('3'))
    
    def test_create_noncatalog_pr_without_items(self):
        """Test creating Non-Catalog PR without items fails"""
        data = self.valid_data.copy()
        data['items'] = []
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_noncatalog_pr_with_optional_catalog_item(self):
        """Test creating Non-Catalog PR with optional catalog_item_id for categorization"""
        catalog_item = create_catalog_item(name='Machinery', description='Machine category')
        
        data = self.valid_data.copy()
        data['items'][0]['catalog_item_id'] = catalog_item.id
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pr = NonCatalog_PR.objects.get(pr_id=response.data['pr_id'])
        item = pr.pr.items.first()
        self.assertEqual(item.catalog_item_id, catalog_item.id)
    
    def test_create_noncatalog_pr_multiple_items(self):
        """Test creating Non-Catalog PR with multiple items"""
        data = self.valid_data.copy()
        data['items'].append({
            "item_name": "Custom Tool Set",
            "item_description": "Specialized tools",
            "quantity": "2",
            "unit_of_measure_id": self.uom.id,
            "estimated_unit_price": "2500.00",
            "notes": "Made to order"
        })
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pr = NonCatalog_PR.objects.get(pr_id=response.data['pr_id'])
        self.assertEqual(pr.pr.items.count(), 2)
        
        # Verify total calculation
        expected_total = (Decimal('3') * Decimal('5000.00')) + (Decimal('2') * Decimal('2500.00'))
        self.assertEqual(pr.pr.total, expected_total)
    
    def test_create_noncatalog_pr_high_priority(self):
        """Test creating high priority Non-Catalog PR"""
        data = self.valid_data.copy()
        data['priority'] = 'URGENT'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pr = NonCatalog_PR.objects.get(pr_id=response.data['pr_id'])
        self.assertEqual(pr.pr.priority, 'URGENT')


class NonCatalogPRListTests(TestCase):
    """Test Non-Catalog PR list endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        self.url = reverse('pr:noncatalog-pr-list')
        
        # Create test data
        self.uom = create_unit_of_measure()
        
        # Create multiple PRs
        for i in range(3):
            data = create_valid_noncatalog_pr_data(self.uom)
            data['requester_name'] = f'User {i}'
            data['requester_department'] = 'Engineering' if i < 2 else 'Production'
            data['priority'] = 'URGENT' if i == 0 else 'HIGH'
            self.client.post(self.url, data, format='json')
    
    def test_list_noncatalog_prs(self):
        """Test listing all Non-Catalog PRs"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIn('results', response.data['data'])
        self.assertEqual(len(response.data['data']['results']), 3)
    
    def test_filter_by_status(self):
        """Test filtering PRs by status"""
        response = self.client.get(self.url, {'status': 'DRAFT'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']['results']), 3)
    
    def test_filter_by_priority(self):
        """Test filtering PRs by priority"""
        response = self.client.get(self.url, {'priority': 'URGENT'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']['results']), 1)
        self.assertEqual(response.data['data']['results'][0]['priority'], 'URGENT')
    
    def test_filter_by_department(self):
        """Test filtering PRs by department"""
        response = self.client.get(self.url, {'requester_department': 'Engineering'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']['results']), 2)


class NonCatalogPRDetailTests(TestCase):
    """Test Non-Catalog PR detail endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test data
        self.uom = create_unit_of_measure()
        data = create_valid_noncatalog_pr_data(self.uom)
        
        # Create PR
        response = self.client.post(reverse('pr:noncatalog-pr-list'), data, format='json')
        self.pr_id = response.data['pr_id']
        self.url = reverse('pr:noncatalog-pr-detail', kwargs={'pk': self.pr_id})
    
    def test_get_noncatalog_pr_detail(self):
        """Test getting Non-Catalog PR detail"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['pr_id'], self.pr_id)
        self.assertIn('items', response.data)
        self.assertEqual(len(response.data['items']), 1)
        self.assertIn('pr_number', response.data)
        self.assertIn('total', response.data)
    
    def test_get_nonexistent_pr(self):
        """Test getting nonexistent PR returns 404"""
        url = reverse('pr:noncatalog-pr-detail', kwargs={'pk': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class NonCatalogPRDeleteTests(TestCase):
    """Test Non-Catalog PR delete endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test data
        self.uom = create_unit_of_measure()
        data = create_valid_noncatalog_pr_data(self.uom)
        
        # Create PR
        response = self.client.post(reverse('pr:noncatalog-pr-list'), data, format='json')
        self.pr_id = response.data['pr_id']
        self.url = reverse('pr:noncatalog-pr-detail', kwargs={'pk': self.pr_id})
    
    def test_delete_draft_pr_success(self):
        """Test deleting a draft PR"""
        response = self.client.delete(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify PR was deleted
        self.assertFalse(NonCatalog_PR.objects.filter(pr_id=self.pr_id).exists())
    
    def test_delete_approved_pr_fails(self):
        """Test deleting an approved PR fails"""
        # Approve the PR
        pr = NonCatalog_PR.objects.get(pr_id=self.pr_id)
        create_simple_approval_template_for_pr()
        approve_pr_for_testing(pr.pr)
        
        response = self.client.delete(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class NonCatalogPRApprovalTests(TestCase):
    """Test Non-Catalog PR approval endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create approval template
        create_simple_approval_template_for_pr()
        
        # Create test data
        self.uom = create_unit_of_measure()
        data = create_valid_noncatalog_pr_data(self.uom)
        
        # Create PR
        response = self.client.post(reverse('pr:noncatalog-pr-list'), data, format='json')
        self.pr_id = response.data['pr_id']
        self.submit_url = reverse('pr:noncatalog-pr-submit-for-approval', kwargs={'pk': self.pr_id})
        self.action_url = reverse('pr:noncatalog-pr-approval-action', kwargs={'pk': self.pr_id})
    
    def test_submit_for_approval_success(self):
        """Test submitting PR for approval"""
        response = self.client.post(self.submit_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response may be wrapped or unwrapped
        if 'data' in response.data and isinstance(response.data['data'], dict):
            self.assertIn('workflow_id', response.data['data'])
        else:
            self.assertIn('workflow_id', response.data)
        
        # Verify status changed
        pr = NonCatalog_PR.objects.get(pr_id=self.pr_id)
        self.assertEqual(pr.pr.status, 'PENDING_APPROVAL')
    
    def test_approve_pr_success(self):
        """Test approving a PR"""
        # Submit for approval
        self.client.post(self.submit_url)
        
        # Approve
        response = self.client.post(self.action_url, {
            'action': 'approve',
            'comment': 'Approved for custom procurement'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify status
        pr = NonCatalog_PR.objects.get(pr_id=self.pr_id)
        self.assertEqual(pr.pr.status, 'APPROVED')
    
    def test_reject_pr_success(self):
        """Test rejecting a PR"""
        # Submit for approval
        self.client.post(self.submit_url)
        
        # Reject
        response = self.client.post(self.action_url, {
            'action': 'reject',
            'comment': 'Please provide more justification'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify status
        pr = NonCatalog_PR.objects.get(pr_id=self.pr_id)
        self.assertEqual(pr.pr.status, 'REJECTED')


class NonCatalogPRCancelTests(TestCase):
    """Test Non-Catalog PR cancel endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test data
        self.uom = create_unit_of_measure()
        data = create_valid_noncatalog_pr_data(self.uom)
        
        # Create PR
        response = self.client.post(reverse('pr:noncatalog-pr-list'), data, format='json')
        self.pr_id = response.data['pr_id']
        self.url = reverse('pr:noncatalog-pr-cancel', kwargs={'pk': self.pr_id})
    
    def test_cancel_pr_success(self):
        """Test cancelling a PR"""
        response = self.client.post(self.url, {
            'reason': 'Vendor not available'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify status
        pr = NonCatalog_PR.objects.get(pr_id=self.pr_id)
        self.assertEqual(pr.pr.status, 'CANCELLED')
        self.assertIn('Vendor not available', pr.pr.notes)


class NonCatalogPRBusinessLogicTests(TestCase):
    """Test Non-Catalog PR business logic"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        self.url = reverse('pr:noncatalog-pr-list')
        
        self.uom = create_unit_of_measure()
    
    def test_high_value_noncatalog_pr(self):
        """Test creating high-value Non-Catalog PR"""
        data = create_valid_noncatalog_pr_data(self.uom)
        data['items'][0]['quantity'] = '10'
        data['items'][0]['estimated_unit_price'] = '50000.00'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pr = NonCatalog_PR.objects.get(pr_id=response.data['pr_id'])
        self.assertEqual(pr.pr.total, Decimal('500000.00'))
    
    def test_noncatalog_pr_with_detailed_specifications(self):
        """Test Non-Catalog PR with detailed item descriptions"""
        data = create_valid_noncatalog_pr_data(self.uom)
        data['items'][0]['item_description'] = 'Very detailed specification: ' + 'X' * 500
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_noncatalog_pr_zero_price(self):
        """Test Non-Catalog PR with zero price (free item)"""
        data = create_valid_noncatalog_pr_data(self.uom)
        data['items'][0]['estimated_unit_price'] = '0.00'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pr = NonCatalog_PR.objects.get(pr_id=response.data['pr_id'])
        self.assertEqual(pr.pr.total, Decimal('0.00'))
