"""
Comprehensive tests for Catalog PR API endpoints.

Tests all endpoints:
- POST   /procurement/pr/catalog/                      - Create Catalog PR
- GET    /procurement/pr/catalog/                      - List Catalog PRs
- GET    /procurement/pr/catalog/{id}/                 - Get Catalog PR detail
- DELETE /procurement/pr/catalog/{id}/                 - Delete Catalog PR
- POST   /procurement/pr/catalog/{id}/submit-for-approval/ - Submit for approval
- GET    /procurement/pr/catalog/pending-approvals/    - Get pending approvals
- POST   /procurement/pr/catalog/{id}/approval-action/ - Approve/Reject/Delegate
- POST   /procurement/pr/catalog/{id}/cancel/          - Cancel PR

Covers scenarios:
- Success cases
- Validation errors
- Edge cases
- Business rule violations
- Filter testing
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from datetime import date, timedelta

from procurement.PR.models import Catalog_PR, PR, PRItem
from procurement.PR.tests.fixtures import (
    create_unit_of_measure,
    create_catalog_item,
    create_valid_catalog_pr_data,
    get_or_create_test_user,
    create_simple_approval_template_for_pr,
    approve_pr_for_testing
)


class CatalogPRCreateTests(TestCase):
    """Test Catalog PR creation endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        self.url = reverse('pr:catalog-pr-list')
        
        # Create test data
        self.uom = create_unit_of_measure()
        self.catalog_item = create_catalog_item()
        self.valid_data = create_valid_catalog_pr_data(self.catalog_item, self.uom)
    
    def test_create_catalog_pr_success(self):
        """Test successful Catalog PR creation"""
        response = self.client.post(self.url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('data', response.data)
        self.assertIn('pr_id', response.data['data'])
        self.assertIn('pr_number', response.data['data'])
        self.assertEqual(response.data['data']['requester_name'], 'John Doe')
        self.assertEqual(response.data['data']['status'], 'DRAFT')
        
        # Verify PR was created
        pr = Catalog_PR.objects.get(pr_id=response.data['data']['pr_id'])
        self.assertIsNotNone(pr)
        self.assertEqual(pr.pr.requester_name, 'John Doe')
        
        # Verify items were created
        self.assertEqual(pr.pr.items.count(), 1)
        item = pr.pr.items.first()
        self.assertEqual(item.item_name, 'Test Laptop')
        self.assertEqual(item.quantity, Decimal('5'))
    
    def test_create_catalog_pr_without_items(self):
        """Test creating Catalog PR without items fails"""
        data = self.valid_data.copy()
        data['items'] = []
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('items', str(response.data).lower())
    
    def test_create_catalog_pr_without_catalog_item_id(self):
        """Test creating Catalog PR without catalog_item_id fails"""
        data = self.valid_data.copy()
        data['items'][0].pop('catalog_item_id')
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_catalog_pr_invalid_date_range(self):
        """Test creating PR with required_date before date fails"""
        data = self.valid_data.copy()
        data['required_date'] = str(date.today() - timedelta(days=5))
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_catalog_pr_negative_quantity(self):
        """Test creating PR with negative quantity fails"""
        data = self.valid_data.copy()
        data['items'][0]['quantity'] = '-5'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_catalog_pr_zero_quantity(self):
        """Test creating PR with zero quantity fails"""
        data = self.valid_data.copy()
        data['items'][0]['quantity'] = '0'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_catalog_pr_multiple_items(self):
        """Test creating Catalog PR with multiple items"""
        data = self.valid_data.copy()
        data['items'].append({
            "item_name": "Mouse",
            "item_description": "Wireless mouse",
            "catalog_item_id": self.catalog_item.id,
            "quantity": "10",
            "unit_of_measure_id": self.uom.id,
            "estimated_unit_price": "50.00",
            "notes": ""
        })
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pr = Catalog_PR.objects.get(pr_id=response.data['data']['pr_id'])
        self.assertEqual(pr.pr.items.count(), 2)
        
        # Verify total calculation
        expected_total = (Decimal('5') * Decimal('1200.00')) + (Decimal('10') * Decimal('50.00'))
        self.assertEqual(pr.pr.total, expected_total)
    
    def test_create_catalog_pr_auto_generates_pr_number(self):
        """Test that PR number is auto-generated"""
        response = self.client.post(self.url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNotNone(response.data['data']['pr_number'])
        self.assertTrue(response.data['data']['pr_number'].startswith('PR-CAT'))


class CatalogPRListTests(TestCase):
    """Test Catalog PR list endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        self.url = reverse('pr:catalog-pr-list')
        
        # Create test data
        self.uom = create_unit_of_measure()
        self.catalog_item = create_catalog_item()
        
        # Create multiple PRs
        for i in range(3):
            data = create_valid_catalog_pr_data(self.catalog_item, self.uom)
            data['requester_name'] = f'User {i}'
            data['requester_department'] = 'IT' if i < 2 else 'HR'
            data['priority'] = 'HIGH' if i == 0 else 'MEDIUM'
            self.client.post(self.url, data, format='json')
    
    def test_list_catalog_prs(self):
        """Test listing all Catalog PRs"""
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
        response = self.client.get(self.url, {'priority': 'HIGH'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']['results']), 1)
        self.assertEqual(response.data['data']['results'][0]['priority'], 'HIGH')
    
    def test_filter_by_department(self):
        """Test filtering PRs by department"""
        response = self.client.get(self.url, {'requester_department': 'IT'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']['results']), 2)
    
    def test_filter_by_date_range(self):
        """Test filtering PRs by date range"""
        today = date.today()
        response = self.client.get(self.url, {
            'date_from': str(today - timedelta(days=1)),
            'date_to': str(today + timedelta(days=1))
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']['results']), 3)


class CatalogPRDetailTests(TestCase):
    """Test Catalog PR detail endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create test data
        self.uom = create_unit_of_measure()
        self.catalog_item = create_catalog_item()
        data = create_valid_catalog_pr_data(self.catalog_item, self.uom)
        
        # Create PR
        response = self.client.post(reverse('pr:catalog-pr-list'), data, format='json')
        self.pr_id = response.data['data']['pr_id']
        self.url = reverse('pr:catalog-pr-detail', kwargs={'pk': self.pr_id})
    
    def test_get_catalog_pr_detail(self):
        """Test getting Catalog PR detail"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['pr_id'], self.pr_id)
        self.assertIn('items', response.data['data'])
        self.assertEqual(len(response.data['data']['items']), 1)
        self.assertIn('pr_number', response.data['data'])
        self.assertIn('total', response.data['data'])
    
    def test_get_nonexistent_pr(self):
        """Test getting nonexistent PR returns 404"""
        url = reverse('pr:catalog-pr-detail', kwargs={'pk': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CatalogPRDeleteTests(TestCase):
    """Test Catalog PR delete endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create test data
        self.uom = create_unit_of_measure()
        self.catalog_item = create_catalog_item()
        data = create_valid_catalog_pr_data(self.catalog_item, self.uom)
        
        # Create PR
        response = self.client.post(reverse('pr:catalog-pr-list'), data, format='json')
        self.pr_id = response.data['data']['pr_id']
        self.url = reverse('pr:catalog-pr-detail', kwargs={'pk': self.pr_id})
    
    def test_delete_draft_pr_success(self):
        """Test deleting a draft PR"""
        response = self.client.delete(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify PR was deleted
        self.assertFalse(Catalog_PR.objects.filter(pr_id=self.pr_id).exists())
    
    def test_delete_approved_pr_fails(self):
        """Test deleting an approved PR fails"""
        # Approve the PR
        pr = Catalog_PR.objects.get(pr_id=self.pr_id)
        create_simple_approval_template_for_pr()
        approve_pr_for_testing(pr.pr)
        
        response = self.client.delete(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'error')


class CatalogPRApprovalTests(TestCase):
    """Test Catalog PR approval endpoints"""
    
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
        self.uom = create_unit_of_measure()
        self.catalog_item = create_catalog_item()
        data = create_valid_catalog_pr_data(self.catalog_item, self.uom)
        
        # Create PR
        response = self.client.post(reverse('pr:catalog-pr-list'), data, format='json')
        self.pr_id = response.data['data']['pr_id']
        self.submit_url = reverse('pr:catalog-pr-submit-for-approval', kwargs={'pk': self.pr_id})
        self.action_url = reverse('pr:catalog-pr-approval-action', kwargs={'pk': self.pr_id})
    
    def test_submit_for_approval_success(self):
        """Test submitting PR for approval"""
        response = self.client.post(self.submit_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response may be wrapped or unwrapped depending on config
        if 'data' in response.data and isinstance(response.data['data'], dict):
            self.assertIn('workflow_id', response.data['data'])
        else:
            self.assertIn('workflow_id', response.data)
        
        # Verify status changed
        pr = Catalog_PR.objects.get(pr_id=self.pr_id)
        self.assertEqual(pr.pr.status, 'PENDING_APPROVAL')
    
    def test_submit_already_submitted_pr_fails(self):
        """Test submitting already submitted PR fails"""
        # Submit first time
        self.client.post(self.submit_url)
        
        # Try to submit again
        response = self.client.post(self.submit_url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_approve_pr_success(self):
        """Test approving a PR"""
        # Submit for approval
        self.client.post(self.submit_url)
        
        # Approve
        response = self.client.post(self.action_url, {
            'action': 'approve',
            'comment': 'Looks good'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify status
        pr = Catalog_PR.objects.get(pr_id=self.pr_id)
        self.assertEqual(pr.pr.status, 'APPROVED')
    
    def test_reject_pr_success(self):
        """Test rejecting a PR"""
        # Submit for approval
        self.client.post(self.submit_url)
        
        # Reject
        response = self.client.post(self.action_url, {
            'action': 'reject',
            'comment': 'Needs revision'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify status
        pr = Catalog_PR.objects.get(pr_id=self.pr_id)
        self.assertEqual(pr.pr.status, 'REJECTED')
    
    def test_approval_action_without_workflow_fails(self):
        """Test approval action on PR without workflow fails"""
        response = self.client.post(self.action_url, {
            'action': 'approve'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_get_pending_approvals(self):
        """Test getting pending approvals for user"""
        # Submit for approval
        self.client.post(self.submit_url)
        
        # Get pending approvals
        url = reverse('pr:catalog-pr-pending-approvals')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should have pending approvals in paginated response
        self.assertIn('data', response.data)
        self.assertIn('results', response.data['data'])


class CatalogPRCancelTests(TestCase):
    """Test Catalog PR cancel endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create test data
        self.uom = create_unit_of_measure()
        self.catalog_item = create_catalog_item()
        data = create_valid_catalog_pr_data(self.catalog_item, self.uom)
        
        # Create PR
        response = self.client.post(reverse('pr:catalog-pr-list'), data, format='json')
        self.pr_id = response.data['data']['pr_id']
        self.url = reverse('pr:catalog-pr-cancel', kwargs={'pk': self.pr_id})
    
    def test_cancel_pr_success(self):
        """Test cancelling a PR"""
        response = self.client.post(self.url, {
            'reason': 'No longer needed'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify status
        pr = Catalog_PR.objects.get(pr_id=self.pr_id)
        self.assertEqual(pr.pr.status, 'CANCELLED')
        self.assertIn('No longer needed', pr.pr.notes)
    
    def test_cancel_pr_without_reason(self):
        """Test cancelling PR without reason should fail"""
        response = self.client.post(self.url, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Reason required', response.data['message'])


class CatalogPREdgeCaseTests(TestCase):
    """Test edge cases for Catalog PR"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        self.url = reverse('pr:catalog-pr-list')
        
        self.uom = create_unit_of_measure()
        self.catalog_item = create_catalog_item()
    
    def test_create_pr_with_very_large_quantity(self):
        """Test creating PR with very large quantity"""
        data = create_valid_catalog_pr_data(self.catalog_item, self.uom)
        data['items'][0]['quantity'] = '999999.99'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_create_pr_with_decimal_quantity(self):
        """Test creating PR with decimal quantity"""
        data = create_valid_catalog_pr_data(self.catalog_item, self.uom)
        data['items'][0]['quantity'] = '5.5'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pr = Catalog_PR.objects.get(pr_id=response.data['data']['pr_id'])
        self.assertEqual(pr.pr.items.first().quantity, Decimal('5.5'))
    
    def test_create_pr_with_missing_optional_fields(self):
        """Test creating PR with only required fields"""
        data = create_valid_catalog_pr_data(self.catalog_item, self.uom)
        data.pop('requester_email', None)
        data.pop('description', None)
        data.pop('notes', None)
        data['items'][0].pop('notes', None)
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_pr_total_calculation_accuracy(self):
        """Test PR total is calculated accurately"""
        data = create_valid_catalog_pr_data(self.catalog_item, self.uom)
        data['items'][0]['quantity'] = '3'
        data['items'][0]['estimated_unit_price'] = '1234.56'
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        expected_total = Decimal('3') * Decimal('1234.56')
        self.assertEqual(Decimal(response.data['data']['total']), expected_total)


# ============================================================================
# ATTACHMENT TESTS
# ============================================================================

class CatalogPRAttachmentTests(TestCase):
    """Test Catalog PR attachment functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create a Catalog PR for testing
        self.uom = create_unit_of_measure()
        self.catalog_item = create_catalog_item()
        
        pr_data = create_valid_catalog_pr_data(self.catalog_item, self.uom)
        response = self.client.post(reverse('pr:catalog-pr-list'), pr_data, format='json')
        self.pr_id = response.data['data']['pr_id']
        
        self.list_url = reverse('pr:pr-attachment-list', kwargs={'pr_id': self.pr_id})
    
    def test_upload_attachment_success(self):
        """Test successful attachment upload"""
        import base64
        
        # Create a simple test file
        test_file_content = b"This is a test quote document"
        file_data_base64 = base64.b64encode(test_file_content).decode('utf-8')
        
        data = {
            'file_name': 'vendor_quote.pdf',
            'file_type': 'application/pdf',
            'file_data_base64': file_data_base64,
            'description': 'Vendor quotation'
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['file_name'], 'vendor_quote.pdf')
        self.assertEqual(response.data['data']['file_size'], len(test_file_content))
        self.assertIn('uploaded_by', response.data['data'])
    
    def test_list_attachments(self):
        """Test listing all attachments for a PR"""
        import base64
        
        # Upload multiple attachments
        for i in range(3):
            test_content = f"PR attachment {i}".encode()
            data = {
                'file_name': f'pr_doc_{i}.pdf',
                'file_type': 'application/pdf',
                'file_data_base64': base64.b64encode(test_content).decode('utf-8'),
                'description': f'PR document {i}'
            }
            self.client.post(self.list_url, data, format='json')
        
        # List attachments
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(len(response.data['data']), 3)
        # Check that all files are present (ordering may vary)
        file_names = [att['file_name'] for att in response.data['data']]
        self.assertIn('pr_doc_0.pdf', file_names)
        self.assertIn('pr_doc_1.pdf', file_names)
        self.assertIn('pr_doc_2.pdf', file_names)
    
    def test_download_attachment(self):
        """Test downloading a specific attachment"""
        import base64
        
        # Upload an attachment first
        test_content = b"PR download test content"
        upload_data = {
            'file_name': 'pr_download.pdf',
            'file_type': 'application/pdf',
            'file_data_base64': base64.b64encode(test_content).decode('utf-8'),
            'description': 'Download test'
        }
        upload_response = self.client.post(self.list_url, upload_data, format='json')
        attachment_id = upload_response.data['data']['attachment_id']
        
        # Download the attachment
        detail_url = reverse('pr:pr-attachment-detail', kwargs={'attachment_id': attachment_id})
        response = self.client.get(detail_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['file_name'], 'pr_download.pdf')
        self.assertIn('file_data_base64', response.data['data'])
        
        # Verify file content
        downloaded_content = base64.b64decode(response.data['data']['file_data_base64'])
        self.assertEqual(downloaded_content, test_content)
    
    def test_delete_attachment(self):
        """Test deleting an attachment"""
        import base64
        
        # Upload an attachment
        test_content = b"PR delete test"
        upload_data = {
            'file_name': 'pr_delete.pdf',
            'file_type': 'application/pdf',
            'file_data_base64': base64.b64encode(test_content).decode('utf-8')
        }
        upload_response = self.client.post(self.list_url, upload_data, format='json')
        attachment_id = upload_response.data['data']['attachment_id']
        
        # Delete the attachment
        detail_url = reverse('pr:pr-attachment-detail', kwargs={'attachment_id': attachment_id})
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
            'file_data_base64': 'invalid-base64-string!!!',
            'description': 'Invalid encoding'
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_upload_attachment_to_nonexistent_pr(self):
        """Test upload fails for non-existent PR"""
        import base64
        
        invalid_url = reverse('pr:pr-attachment-list', kwargs={'pr_id': 99999})
        data = {
            'file_name': 'test.pdf',
            'file_type': 'application/pdf',
            'file_data_base64': base64.b64encode(b"test").decode('utf-8')
        }
        
        response = self.client.post(invalid_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_download_nonexistent_attachment(self):
        """Test download fails for non-existent attachment"""
        detail_url = reverse('pr:pr-attachment-detail', kwargs={'attachment_id': 99999})
        response = self.client.get(detail_url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_attachment_file_size_display(self):
        """Test file size is displayed in human-readable format"""
        import base64
        
        # Upload a 2KB file
        test_content = b"x" * 2048
        data = {
            'file_name': 'size_test.txt',
            'file_type': 'text/plain',
            'file_data_base64': base64.b64encode(test_content).decode('utf-8')
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['data']['file_size'], 2048)
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
        # uploaded_by is a CharField storing username/email
        self.assertIsNotNone(response.data['data']['uploaded_by'])
    
    def test_attachment_included_in_pr_detail(self):
        """Test attachments are included in PR detail response"""
        import base64
        
        # Upload an attachment
        data = {
            'file_name': 'detail_test.pdf',
            'file_type': 'application/pdf',
            'file_data_base64': base64.b64encode(b"test").decode('utf-8')
        }
        self.client.post(self.list_url, data, format='json')
        
        # Get PR detail
        detail_url = reverse('pr:catalog-pr-detail', kwargs={'pk': self.pr_id})
        response = self.client.get(detail_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('attachments', response.data['data'])
        self.assertEqual(len(response.data['data']['attachments']), 1)
        self.assertEqual(response.data['data']['attachments'][0]['file_name'], 'detail_test.pdf')
    
    def test_multiple_attachments_different_types(self):
        """Test uploading multiple attachments with different file types"""
        import base64
        
        attachments = [
            {'file_name': 'quote.pdf', 'file_type': 'application/pdf', 'content': b'PDF content'},
            {'file_name': 'specs.docx', 'file_type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'content': b'Word content'},
            {'file_name': 'image.jpg', 'file_type': 'image/jpeg', 'content': b'JPEG content'}
        ]
        
        for att in attachments:
            data = {
                'file_name': att['file_name'],
                'file_type': att['file_type'],
                'file_data_base64': base64.b64encode(att['content']).decode('utf-8')
            }
            response = self.client.post(self.list_url, data, format='json')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify all attachments are listed
        list_response = self.client.get(self.list_url)
        self.assertEqual(len(list_response.data['data']), 3)
    
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
    
    def test_attachment_description_optional(self):
        """Test that attachment description is optional"""
        import base64
        
        data = {
            'file_name': 'no_description.pdf',
            'file_type': 'application/pdf',
            'file_data_base64': base64.b64encode(b"test").decode('utf-8')
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['data']['description'], '')
