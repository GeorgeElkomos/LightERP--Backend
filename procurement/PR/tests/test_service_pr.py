"""
Comprehensive tests for Service PR API endpoints.

Tests all endpoints for Service PRs (service requests).
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from datetime import date, timedelta

from procurement.PR.models import Service_PR, PR, PRItem
from procurement.PR.tests.fixtures import (
    create_unit_of_measure,
    create_valid_service_pr_data,
    get_or_create_test_user,
    create_simple_approval_template_for_pr,
    approve_pr_for_testing
)
from procurement.catalog.models import UnitOfMeasure


class ServicePRCreateTests(TestCase):
    """Test Service PR creation endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        self.url = reverse('pr:service-pr-list')
        
        # Create service UOM
        self.uom, _ = UnitOfMeasure.objects.get_or_create(
            code='SRV',
            defaults={
                'name': 'Service',
                'uom_type': 'QUANTITY'
            }
        )
        self.valid_data = create_valid_service_pr_data(self.uom)
    
    def test_create_service_pr_success(self):
        """Test successful Service PR creation"""
        response = self.client.post(self.url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('data', response.data)
        self.assertIn('pr_id', response.data['data'])
        self.assertIn('pr_number', response.data['data'])
        self.assertTrue(response.data['data']['pr_number'].startswith('PR-SRV'))
        self.assertEqual(response.data['data']['requester_name'], 'Bob Johnson')
        self.assertEqual(response.data['data']['status'], 'DRAFT')
        
        # Verify PR was created
        pr = Service_PR.objects.get(pr_id=response.data['data']['pr_id'])
        self.assertIsNotNone(pr)
        self.assertEqual(pr.pr.requester_department, 'Facilities')
        
        # Verify service items were created
        self.assertEqual(pr.pr.items.count(), 1)
        item = pr.pr.items.first()
        self.assertEqual(item.item_name, 'HVAC Maintenance Service')
        self.assertEqual(item.quantity, Decimal('1'))
    
    def test_create_service_pr_without_items(self):
        """Test creating Service PR without items fails"""
        data = self.valid_data.copy()
        data['items'] = []
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_service_pr_multiple_services(self):
        """Test creating Service PR with multiple services"""
        data = self.valid_data.copy()
        data['items'].append({
            "item_name": "Electrical System Inspection",
            "item_description": "Annual electrical safety inspection",
            "quantity": "1",
            "unit_of_measure_id": self.uom.id,
            "estimated_unit_price": "2500.00",
            "notes": "Required by law"
        })
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pr = Service_PR.objects.get(pr_id=response.data['data']['pr_id'])
        self.assertEqual(pr.pr.items.count(), 2)
        
        # Verify total calculation
        expected_total = Decimal('15000.00') + Decimal('2500.00')
        self.assertEqual(pr.pr.total, expected_total)
    
    def test_create_service_pr_urgent_priority(self):
        """Test creating urgent Service PR"""
        data = self.valid_data.copy()
        data['priority'] = 'URGENT'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pr = Service_PR.objects.get(pr_id=response.data['data']['pr_id'])
        self.assertEqual(pr.pr.priority, 'URGENT')
        self.assertTrue(pr.pr.is_urgent())
    
    def test_create_service_pr_recurring_service(self):
        """Test creating Service PR for recurring service"""
        data = self.valid_data.copy()
        data['description'] = 'Annual recurring maintenance contract'
        data['items'][0]['item_description'] = 'Monthly service for 12 months'
        data['items'][0]['quantity'] = '12'
        data['items'][0]['estimated_unit_price'] = '1000.00'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pr = Service_PR.objects.get(pr_id=response.data['data']['pr_id'])
        self.assertEqual(pr.pr.total, Decimal('12000.00'))


class ServicePRListTests(TestCase):
    """Test Service PR list endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        self.url = reverse('pr:service-pr-list')
        
        # Create service UOM
        self.uom, _ = UnitOfMeasure.objects.get_or_create(
            code='SRV',
            defaults={'name': 'Service', 'uom_type': 'QUANTITY'}
        )
        
        # Create multiple PRs
        for i in range(3):
            data = create_valid_service_pr_data(self.uom)
            data['requester_name'] = f'User {i}'
            data['requester_department'] = 'Facilities' if i < 2 else 'Maintenance'
            data['priority'] = 'URGENT' if i == 0 else 'MEDIUM'
            self.client.post(self.url, data, format='json')
    
    def test_list_service_prs(self):
        """Test listing all Service PRs"""
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
        response = self.client.get(self.url, {'requester_department': 'Facilities'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']['results']), 2)


class ServicePRDetailTests(TestCase):
    """Test Service PR detail endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create test data
        self.uom, _ = UnitOfMeasure.objects.get_or_create(
            code='SRV',
            defaults={'name': 'Service', 'uom_type': 'QUANTITY'}
        )
        data = create_valid_service_pr_data(self.uom)
        
        # Create PR
        response = self.client.post(reverse('pr:service-pr-list'), data, format='json')
        self.pr_id = response.data['data']['pr_id']
        self.url = reverse('pr:service-pr-detail', kwargs={'pk': self.pr_id})
    
    def test_get_service_pr_detail(self):
        """Test getting Service PR detail"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['pr_id'], self.pr_id)
        self.assertIn('items', response.data['data'])
        self.assertEqual(len(response.data['data']['items']), 1)
        self.assertIn('pr_number', response.data['data'])
        self.assertIn('total', response.data['data'])
    
    def test_get_nonexistent_pr(self):
        """Test getting nonexistent PR returns 404"""
        url = reverse('pr:service-pr-detail', kwargs={'pk': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ServicePRDeleteTests(TestCase):
    """Test Service PR delete endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create test data
        self.uom, _ = UnitOfMeasure.objects.get_or_create(
            code='SRV',
            defaults={'name': 'Service', 'uom_type': 'QUANTITY'}
        )
        data = create_valid_service_pr_data(self.uom)
        
        # Create PR
        response = self.client.post(reverse('pr:service-pr-list'), data, format='json')
        self.pr_id = response.data['data']['pr_id']
        self.url = reverse('pr:service-pr-detail', kwargs={'pk': self.pr_id})
    
    def test_delete_draft_pr_success(self):
        """Test deleting a draft PR"""
        response = self.client.delete(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify PR was deleted
        self.assertFalse(Service_PR.objects.filter(pr_id=self.pr_id).exists())
    
    def test_delete_approved_pr_fails(self):
        """Test deleting an approved PR fails"""
        # Approve the PR
        pr = Service_PR.objects.get(pr_id=self.pr_id)
        create_simple_approval_template_for_pr()
        approve_pr_for_testing(pr.pr)
        
        response = self.client.delete(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ServicePRApprovalTests(TestCase):
    """Test Service PR approval endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create approval template
        create_simple_approval_template_for_pr()
        
        # Create test data
        self.uom, _ = UnitOfMeasure.objects.get_or_create(
            code='SRV',
            defaults={'name': 'Service', 'uom_type': 'QUANTITY'}
        )
        data = create_valid_service_pr_data(self.uom)
        
        # Create PR
        response = self.client.post(reverse('pr:service-pr-list'), data, format='json')
        self.pr_id = response.data['data']['pr_id']
        self.submit_url = reverse('pr:service-pr-submit-for-approval', kwargs={'pk': self.pr_id})
        self.action_url = reverse('pr:service-pr-approval-action', kwargs={'pk': self.pr_id})
    
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
        pr = Service_PR.objects.get(pr_id=self.pr_id)
        self.assertEqual(pr.pr.status, 'PENDING_APPROVAL')
    
    def test_approve_pr_success(self):
        """Test approving a PR"""
        # Submit for approval
        self.client.post(self.submit_url)
        
        # Approve
        response = self.client.post(self.action_url, {
            'action': 'approve',
            'comment': 'Service approved'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify status
        pr = Service_PR.objects.get(pr_id=self.pr_id)
        self.assertEqual(pr.pr.status, 'APPROVED')
    
    def test_reject_pr_success(self):
        """Test rejecting a PR"""
        # Submit for approval
        self.client.post(self.submit_url)
        
        # Reject
        response = self.client.post(self.action_url, {
            'action': 'reject',
            'comment': 'Service not needed'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify status
        pr = Service_PR.objects.get(pr_id=self.pr_id)
        self.assertEqual(pr.pr.status, 'REJECTED')
    
    def test_get_pending_approvals(self):
        """Test getting pending service approvals"""
        # Submit for approval
        self.client.post(self.submit_url)
        
        # Get pending approvals
        url = reverse('pr:service-pr-pending-approvals')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIn('results', response.data['data'])


class ServicePRCancelTests(TestCase):
    """Test Service PR cancel endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create test data
        self.uom, _ = UnitOfMeasure.objects.get_or_create(
            code='SRV',
            defaults={'name': 'Service', 'uom_type': 'QUANTITY'}
        )
        data = create_valid_service_pr_data(self.uom)
        
        # Create PR
        response = self.client.post(reverse('pr:service-pr-list'), data, format='json')
        self.pr_id = response.data['data']['pr_id']
        self.url = reverse('pr:service-pr-cancel', kwargs={'pk': self.pr_id})
    
    def test_cancel_pr_success(self):
        """Test cancelling a Service PR"""
        response = self.client.post(self.url, {
            'reason': 'Service vendor unavailable'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify status
        pr = Service_PR.objects.get(pr_id=self.pr_id)
        self.assertEqual(pr.pr.status, 'CANCELLED')
        self.assertIn('Service vendor unavailable', pr.pr.notes)


class ServicePRBusinessLogicTests(TestCase):
    """Test Service PR business logic"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        self.url = reverse('pr:service-pr-list')
        
        self.uom, _ = UnitOfMeasure.objects.get_or_create(
            code='SRV',
            defaults={'name': 'Service', 'uom_type': 'QUANTITY'}
        )
    
    def test_high_value_service_pr(self):
        """Test creating high-value Service PR (>50000)"""
        data = create_valid_service_pr_data(self.uom)
        data['items'][0]['estimated_unit_price'] = '75000.00'
        data['description'] = 'High-value service requiring special approval'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pr = Service_PR.objects.get(pr_id=response.data['data']['pr_id'])
        self.assertEqual(pr.pr.total, Decimal('75000.00'))
        self.assertTrue(pr.is_high_value_service())
    
    def test_service_pr_with_multiple_service_types(self):
        """Test Service PR with different types of services"""
        data = create_valid_service_pr_data(self.uom)
        data['items'] = [
            {
                "item_name": "Plumbing Repair",
                "item_description": "Fix leaking pipes",
                "quantity": "1",
                "unit_of_measure_id": self.uom.id,
                "estimated_unit_price": "500.00"
            },
            {
                "item_name": "Electrical Repair",
                "item_description": "Replace circuit breakers",
                "quantity": "1",
                "unit_of_measure_id": self.uom.id,
                "estimated_unit_price": "750.00"
            },
            {
                "item_name": "HVAC Maintenance",
                "item_description": "Routine maintenance",
                "quantity": "1",
                "unit_of_measure_id": self.uom.id,
                "estimated_unit_price": "1200.00"
            }
        ]
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pr = Service_PR.objects.get(pr_id=response.data['data']['pr_id'])
        self.assertEqual(pr.pr.items.count(), 3)
        self.assertEqual(pr.pr.total, Decimal('2450.00'))
    
    def test_service_pr_zero_cost_service(self):
        """Test Service PR with zero cost (warranty service)"""
        data = create_valid_service_pr_data(self.uom)
        data['items'][0]['estimated_unit_price'] = '0.00'
        data['items'][0]['notes'] = 'Under warranty'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pr = Service_PR.objects.get(pr_id=response.data['data']['pr_id'])
        self.assertEqual(pr.pr.total, Decimal('0.00'))
    
    def test_service_count_method(self):
        """Test get_service_count method"""
        data = create_valid_service_pr_data(self.uom)
        data['items'].append({
            "item_name": "Additional Service",
            "item_description": "Extra service",
            "quantity": "1",
            "unit_of_measure_id": self.uom.id,
            "estimated_unit_price": "500.00"
        })
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pr = Service_PR.objects.get(pr_id=response.data['data']['pr_id'])
        self.assertEqual(pr.get_service_count(), 2)
    
    def test_service_pr_days_until_required(self):
        """Test days_until_required calculation"""
        data = create_valid_service_pr_data(self.uom)
        data['required_date'] = str(date.today() + timedelta(days=7))
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pr = Service_PR.objects.get(pr_id=response.data['data']['pr_id'])
        self.assertEqual(pr.pr.days_until_required(), 7)
