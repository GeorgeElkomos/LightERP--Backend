"""
Comprehensive Tests for Default Combinations module
Tests for models, serializers, and API endpoints
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.urls import reverse
from decimal import Decimal

from Finance.GL.models import XX_SegmentType, XX_Segment, XX_Segment_combination, segment_combination_detials
from .models import set_default_combinations
from .serializers import (
    DefaultCombinationsListSerializer,
    DefaultCombinationsDetailSerializer,
    DefaultCombinationsCreateSerializer,
    DefaultCombinationsUpdateSerializer,
)

User = get_user_model()


class DefaultCombinationsModelTestCase(TestCase):
    """Test cases for set_default_combinations model"""
    
    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create_user(
            email='test@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass123'
        )
        
        # Create segment types
        self.segment_type_entity = XX_SegmentType.objects.create(
            segment_name='Entity',
            is_required=True,
            length=3,
            display_order=1
        )
        self.segment_type_account = XX_SegmentType.objects.create(
            segment_name='Account',
            is_required=True,
            length=5,
            display_order=2
        )
        self.segment_type_project = XX_SegmentType.objects.create(
            segment_name='Project',
            is_required=False,
            length=4,
            display_order=3
        )
        
        # Create segment values
        self.segment_entity = XX_Segment.objects.create(
            segment_type=self.segment_type_entity,
            code='001',
            alias='Main Entity',
            node_type='child'
        )
        self.segment_account = XX_Segment.objects.create(
            segment_type=self.segment_type_account,
            code='50000',
            alias='Accounts Payable',
            node_type='child'
        )
        self.segment_project = XX_Segment.objects.create(
            segment_type=self.segment_type_project,
            code='PROJ',
            alias='Test Project',
            node_type='child'
        )
        
        # Create a complete segment combination
        self.complete_combination = XX_Segment_combination.objects.create(
            description='Complete test combination',
            is_active=True
        )
        segment_combination_detials.objects.create(
            segment_combination=self.complete_combination,
            segment_type=self.segment_type_entity,
            segment=self.segment_entity
        )
        segment_combination_detials.objects.create(
            segment_combination=self.complete_combination,
            segment_type=self.segment_type_account,
            segment=self.segment_account
        )
        
        # Create an incomplete segment combination (missing optional project)
        self.incomplete_combination = XX_Segment_combination.objects.create(
            description='Incomplete test combination',
            is_active=True
        )
        segment_combination_detials.objects.create(
            segment_combination=self.incomplete_combination,
            segment_type=self.segment_type_entity,
            segment=self.segment_entity
        )
    
    def test_create_default_combination(self):
        """Test creating a default combination"""
        default = set_default_combinations.objects.create(
            transaction_type='AP_INVOICE',
            segment_combination=self.complete_combination,
            is_active=True,
            created_by=self.user
        )
        
        self.assertEqual(default.transaction_type, 'AP_INVOICE')
        self.assertEqual(default.segment_combination, self.complete_combination)
        self.assertTrue(default.is_active)
        self.assertEqual(default.created_by, self.user)
    
    def test_unique_transaction_type_constraint(self):
        """Test that only one default can exist per transaction type"""
        # Create first default
        set_default_combinations.objects.create(
            transaction_type='AP_INVOICE',
            segment_combination=self.complete_combination,
            is_active=True,
            created_by=self.user
        )
        
        # Try to create second default for same transaction type
        with self.assertRaises(Exception):  # Should raise IntegrityError
            set_default_combinations.objects.create(
                transaction_type='AP_INVOICE',
                segment_combination=self.incomplete_combination,
                is_active=True,
                created_by=self.user
            )
    
    def test_validate_segment_combination_completeness_valid(self):
        """Test validation of a complete segment combination"""
        default = set_default_combinations.objects.create(
            transaction_type='AP_INVOICE',
            segment_combination=self.complete_combination,
            is_active=True,
            created_by=self.user
        )
        
        is_valid, message = default.validate_segment_combination_completeness()
        self.assertTrue(is_valid)
        self.assertEqual(message, "")
    
    def test_validate_segment_combination_completeness_invalid(self):
        """Test validation of an incomplete segment combination"""
        default = set_default_combinations.objects.create(
            transaction_type='AR_INVOICE',
            segment_combination=self.incomplete_combination,
            is_active=True,
            created_by=self.user
        )
        
        is_valid, message = default.validate_segment_combination_completeness()
        self.assertFalse(is_valid)
        self.assertIn('missing required segment types', message.lower())
    
    def test_create_or_update_default_creates_new(self):
        """Test create_or_update_default creates new record"""
        default, created = set_default_combinations.create_or_update_default(
            transaction_type='AP_INVOICE',
            segment_combination=self.complete_combination,
            user=self.user
        )
        
        self.assertIsNotNone(default)
        self.assertTrue(created)
        self.assertEqual(default.transaction_type, 'AP_INVOICE')
        self.assertEqual(default.created_by, self.user)
    
    def test_create_or_update_default_updates_existing(self):
        """Test create_or_update_default updates existing record"""
        # Create initial default
        initial_default, created = set_default_combinations.create_or_update_default(
            transaction_type='AP_INVOICE',
            segment_combination=self.complete_combination,
            user=self.user
        )
        self.assertTrue(created)
        initial_id = initial_default.id
        
        # Create another valid combination for update
        another_combination = XX_Segment_combination.objects.create(
            description='Another complete combination',
            is_active=True
        )
        segment_combination_detials.objects.create(
            segment_combination=another_combination,
            segment_type=self.segment_type_entity,
            segment=self.segment_entity
        )
        segment_combination_detials.objects.create(
            segment_combination=another_combination,
            segment_type=self.segment_type_account,
            segment=self.segment_account
        )
        
        # Update with different combination
        updated_default, created = set_default_combinations.create_or_update_default(
            transaction_type='AP_INVOICE',
            segment_combination=another_combination,
            user=self.user
        )
        
        # Should be same record (same ID)
        self.assertFalse(created)
        self.assertEqual(updated_default.id, initial_id)
        self.assertEqual(updated_default.segment_combination, another_combination)
        self.assertEqual(updated_default.updated_by, self.user)
    
    def test_get_default_for_transaction_type(self):
        """Test retrieving default by transaction type"""
        # Create default
        default = set_default_combinations.objects.create(
            transaction_type='AP_INVOICE',
            segment_combination=self.complete_combination,
            is_active=True,
            created_by=self.user
        )
        
        # Retrieve it - returns segment_combination, not default object
        retrieved = set_default_combinations.get_default_for_transaction_type('AP_INVOICE')
        self.assertEqual(retrieved, self.complete_combination)
        
        # Try non-existent type
        none_result = set_default_combinations.get_default_for_transaction_type('NONEXISTENT')
        self.assertIsNone(none_result)
    
    def test_get_default_for_ap_invoice(self):
        """Test AP invoice specific helper method"""
        default = set_default_combinations.objects.create(
            transaction_type='AP_INVOICE',
            segment_combination=self.complete_combination,
            is_active=True,
            created_by=self.user
        )
        
        retrieved = set_default_combinations.get_default_for_ap_invoice()
        self.assertEqual(retrieved, self.complete_combination)
    
    def test_get_default_for_ar_invoice(self):
        """Test AR invoice specific helper method"""
        default = set_default_combinations.objects.create(
            transaction_type='AR_INVOICE',
            segment_combination=self.complete_combination,
            is_active=True,
            created_by=self.user
        )
        
        retrieved = set_default_combinations.get_default_for_ar_invoice()
        self.assertEqual(retrieved, self.complete_combination)
    
    def test_get_segment_details(self):
        """Test getting segment details"""
        default = set_default_combinations.objects.create(
            transaction_type='AP_INVOICE',
            segment_combination=self.complete_combination,
            is_active=True,
            created_by=self.user
        )
        
        details = default.get_segment_details()
        self.assertIsInstance(details, dict)
        self.assertIn('segments', details)
        self.assertGreater(len(details['segments']), 0)
        
        # Check structure of first segment
        first_segment = details['segments'][0]
        self.assertIn('segment_type', first_segment)
        self.assertIn('segment_code', first_segment)
        self.assertIn('segment_alias', first_segment)
    
    def test_is_valid_combination(self):
        """Test is_valid_combination method"""
        complete_default = set_default_combinations.objects.create(
            transaction_type='AP_INVOICE',
            segment_combination=self.complete_combination,
            is_active=True,
            created_by=self.user
        )
        
        incomplete_default = set_default_combinations.objects.create(
            transaction_type='AR_INVOICE',
            segment_combination=self.incomplete_combination,
            is_active=True,
            created_by=self.user
        )
        
        self.assertTrue(complete_default.is_valid_combination())
        self.assertTrue(incomplete_default.is_valid_combination())
    
    def test_check_and_deactivate_if_invalid(self):
        """Test automatic deactivation of invalid combinations"""
        default = set_default_combinations.objects.create(
            transaction_type='AP_INVOICE',
            segment_combination=self.incomplete_combination,
            is_active=True,
            created_by=self.user
        )
        
        # Should be active initially
        self.assertTrue(default.is_active)
        
        # Check and deactivate
        result = default.check_and_deactivate_if_invalid()
        
        # Should be deactivated now
        default.refresh_from_db()
        self.assertFalse(default.is_active)
        self.assertTrue(result)
    
    def test_check_all_defaults_validity(self):
        """Test checking validity of all defaults"""
        # Create valid and invalid defaults
        valid_default = set_default_combinations.objects.create(
            transaction_type='AP_INVOICE',
            segment_combination=self.complete_combination,
            is_active=True,
            created_by=self.user
        )
        
        invalid_default = set_default_combinations.objects.create(
            transaction_type='AR_INVOICE',
            segment_combination=self.incomplete_combination,
            is_active=True,
            created_by=self.user
        )
        
        # Check all
        set_default_combinations.check_all_defaults_validity()
        
        # Refresh from database
        valid_default.refresh_from_db()
        invalid_default.refresh_from_db()
        
        # Valid should still be active, invalid should be deactivated
        self.assertTrue(valid_default.is_active)
        self.assertFalse(invalid_default.is_active)
    
    def test_get_all_defaults(self):
        """Test retrieving all defaults"""
        # Create multiple defaults
        ap_default = set_default_combinations.objects.create(
            transaction_type='AP_INVOICE',
            segment_combination=self.complete_combination,
            is_active=True,
            created_by=self.user
        )
        
        ar_default = set_default_combinations.objects.create(
            transaction_type='AR_INVOICE',
            segment_combination=self.incomplete_combination,
            is_active=False,
            created_by=self.user
        )
        
        # Get all defaults - returns dict
        all_defaults = set_default_combinations.get_all_defaults()
        self.assertIsInstance(all_defaults, dict)
        self.assertEqual(len(all_defaults), 2)
        self.assertIn('AP_INVOICE', all_defaults)
        self.assertIn('AR_INVOICE', all_defaults)
        self.assertEqual(all_defaults['AP_INVOICE'], self.complete_combination)
    
    def test_update_default(self):
        """Test update_default instance method"""
        default = set_default_combinations.objects.create(
            transaction_type='AP_INVOICE',
            segment_combination=self.complete_combination,
            is_active=True,
            created_by=self.user
        )
        
        # Create another valid combination
        another_combination = XX_Segment_combination.objects.create(
            description='Another valid combination',
            is_active=True
        )
        segment_combination_detials.objects.create(
            segment_combination=another_combination,
            segment_type=self.segment_type_entity,
            segment=self.segment_entity
        )
        segment_combination_detials.objects.create(
            segment_combination=another_combination,
            segment_type=self.segment_type_account,
            segment=self.segment_account
        )
        
        # Update it using instance method
        default.update_default(another_combination, self.user)
        default.refresh_from_db()
        
        # Check updates
        self.assertEqual(default.segment_combination, another_combination)
        self.assertEqual(default.updated_by, self.user)
    
    def test_str_representation(self):
        """Test string representation"""
        default = set_default_combinations.objects.create(
            transaction_type='AP_INVOICE',
            segment_combination=self.complete_combination,
            is_active=True,
            created_by=self.user
        )
        
        str_repr = str(default)
        self.assertIn('Accounts Payable Invoice', str_repr)


class DefaultCombinationsSerializerTestCase(TestCase):
    """Test cases for serializers"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='test@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass123'
        )
        
        # Create segment types and values
        self.segment_type_entity = XX_SegmentType.objects.create(
            segment_name='Entity',
            is_required=True,
            length=3,
            display_order=1
        )
        self.segment_type_account = XX_SegmentType.objects.create(
            segment_name='Account',
            is_required=True,
            length=5,
            display_order=2
        )
        
        self.segment_entity = XX_Segment.objects.create(
            segment_type=self.segment_type_entity,
            code='001',
            alias='Main Entity',
            node_type='child'
        )
        self.segment_account = XX_Segment.objects.create(
            segment_type=self.segment_type_account,
            code='50000',
            alias='Accounts Payable',
            node_type='child'
        )
        
        self.combination = XX_Segment_combination.objects.create(
            description='Test combination',
            is_active=True
        )
        segment_combination_detials.objects.create(
            segment_combination=self.combination,
            segment_type=self.segment_type_entity,
            segment=self.segment_entity
        )
        segment_combination_detials.objects.create(
            segment_combination=self.combination,
            segment_type=self.segment_type_account,
            segment=self.segment_account
        )
    
    def test_list_serializer(self):
        """Test list serializer"""
        default = set_default_combinations.objects.create(
            transaction_type='AP_INVOICE',
            segment_combination=self.combination,
            is_active=True,
            created_by=self.user
        )
        
        serializer = DefaultCombinationsListSerializer(default)
        data = serializer.data
        
        self.assertEqual(data['transaction_type'], 'AP_INVOICE')
        self.assertIn('is_valid', data)
        self.assertIn('segment_combination_id', data)
    
    def test_detail_serializer(self):
        """Test detail serializer"""
        default = set_default_combinations.objects.create(
            transaction_type='AP_INVOICE',
            segment_combination=self.combination,
            is_active=True,
            created_by=self.user
        )
        
        serializer = DefaultCombinationsDetailSerializer(default)
        data = serializer.data
        
        self.assertEqual(data['transaction_type'], 'AP_INVOICE')
        self.assertIn('segment_details', data)
        self.assertIn('validation_status', data)
        self.assertIn('created_by_id', data)
    
    def test_create_serializer_validation(self):
        """Test create serializer validation"""
        from unittest.mock import Mock
        
        request = Mock()
        request.user = self.user
        
        data = {
            'transaction_type': 'AP_INVOICE',
            'segments': [
                {
                    'segment_type_id': self.segment_type_entity.id,
                    'segment_code': self.segment_entity.code
                },
                {
                    'segment_type_id': self.segment_type_account.id,
                    'segment_code': self.segment_account.code
                }
            ]
        }
        
        serializer = DefaultCombinationsCreateSerializer(
            data=data,
            context={'request': request}
        )
        
        is_valid = serializer.is_valid()
        if not is_valid:
            print(f"Validation errors: {serializer.errors}")
        self.assertTrue(is_valid)


class DefaultCombinationsAPITestCase(APITestCase):
    """Test cases for API endpoints"""
    
    def setUp(self):
        """Set up test data and authentication"""
        # Create test user
        self.user = User.objects.create_user(
            email='test@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass123'
        )
        
        # Authenticate client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        # Create segment types
        self.segment_type_entity = XX_SegmentType.objects.create(
            segment_name='Entity',
            is_required=True,
            length=3,
            display_order=1
        )
        self.segment_type_account = XX_SegmentType.objects.create(
            segment_name='Account',
            is_required=True,
            length=5,
            display_order=2
        )
        
        # Create segment values
        self.segment_entity = XX_Segment.objects.create(
            segment_type=self.segment_type_entity,
            code='001',
            alias='Main Entity',
            node_type='child'
        )
        self.segment_account = XX_Segment.objects.create(
            segment_type=self.segment_type_account,
            code='50000',
            alias='Accounts Payable',
            node_type='child'
        )
        
        # Create segment combination
        self.combination = XX_Segment_combination.objects.create(
            description='Test combination',
            is_active=True
        )
        segment_combination_detials.objects.create(
            segment_combination=self.combination,
            segment_type=self.segment_type_entity,
            segment=self.segment_entity
        )
        segment_combination_detials.objects.create(
            segment_combination=self.combination,
            segment_type=self.segment_type_account,
            segment=self.segment_account
        )
        
        # Base URL
        self.base_url = '/finance/default-combinations/'
    
    def test_list_defaults(self):
        """Test listing all defaults"""
        # Create test defaults
        set_default_combinations.objects.create(
            transaction_type='AP_INVOICE',
            segment_combination=self.combination,
            is_active=True,
            created_by=self.user
        )
        
        url = self.base_url
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 1)
    
    def test_list_defaults_with_filters(self):
        """Test listing with query parameters"""
        # Create active and inactive defaults
        set_default_combinations.objects.create(
            transaction_type='AP_INVOICE',
            segment_combination=self.combination,
            is_active=True,
            created_by=self.user
        )
        set_default_combinations.objects.create(
            transaction_type='AR_INVOICE',
            segment_combination=self.combination,
            is_active=False,
            created_by=self.user
        )
        
        # Filter by active
        url = f'{self.base_url}?is_active=true'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        
        # Filter by transaction type
        url = f'{self.base_url}?transaction_type=AP_INVOICE'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_create_default(self):
        """Test creating a new default"""
        url = self.base_url
        data = {
            'transaction_type': 'AP_INVOICE',
            'segments': [
                {
                    'segment_type_id': self.segment_type_entity.id,
                    'segment_code': self.segment_entity.code
                },
                {
                    'segment_type_id': self.segment_type_account.id,
                    'segment_code': self.segment_account.code
                }
            ]
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['transaction_type'], 'AP_INVOICE')
        self.assertTrue(response.data['is_active'])
    
    def test_create_or_update_default(self):
        """Test that creating duplicate updates existing"""
        url = self.base_url
        data = {
            'transaction_type': 'AP_INVOICE',
            'segments': [
                {
                    'segment_type_id': self.segment_type_entity.id,
                    'segment_code': self.segment_entity.code
                },
                {
                    'segment_type_id': self.segment_type_account.id,
                    'segment_code': self.segment_account.code
                }
            ]
        }
        
        # Create first
        response1 = self.client.post(url, data, format='json')
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        first_id = response1.data['id']
        
        # Create again (should update)
        response2 = self.client.post(url, data, format='json')
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        second_id = response2.data['id']
        
        # Should be same ID
        self.assertEqual(first_id, second_id)
    
    def test_retrieve_default(self):
        """Test retrieving a specific default"""
        default = set_default_combinations.objects.create(
            transaction_type='AP_INVOICE',
            segment_combination=self.combination,
            is_active=True,
            created_by=self.user
        )
        
        url = f'{self.base_url}{default.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], default.id)
        self.assertIn('segment_details', response.data)
    
    def test_update_default(self):
        """Test updating a default"""
        default = set_default_combinations.objects.create(
            transaction_type='AP_INVOICE',
            segment_combination=self.combination,
            is_active=True,
            created_by=self.user
        )
        
        url = f'{self.base_url}{default.id}/'
        data = {
            'segments': [
                {
                    'segment_type_id': self.segment_type_entity.id,
                    'segment_code': self.segment_entity.code
                },
                {
                    'segment_type_id': self.segment_type_account.id,
                    'segment_code': self.segment_account.code
                }
            ]
        }
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_delete_default(self):
        """Test deleting a default"""
        default = set_default_combinations.objects.create(
            transaction_type='AP_INVOICE',
            segment_combination=self.combination,
            is_active=True,
            created_by=self.user
        )
        
        url = f'{self.base_url}{default.id}/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify deletion
        exists = set_default_combinations.objects.filter(id=default.id).exists()
        self.assertFalse(exists)
    
    def test_get_by_transaction_type(self):
        """Test getting default by transaction type"""
        default = set_default_combinations.objects.create(
            transaction_type='AP_INVOICE',
            segment_combination=self.combination,
            is_active=True,
            created_by=self.user
        )
        
        url = f'{self.base_url}by-transaction-type/AP_INVOICE/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], default.id)
    
    def test_get_by_invalid_transaction_type(self):
        """Test getting by invalid transaction type"""
        url = f'{self.base_url}by-transaction-type/INVALID/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_get_ap_invoice_default(self):
        """Test AP invoice default endpoint"""
        default = set_default_combinations.objects.create(
            transaction_type='AP_INVOICE',
            segment_combination=self.combination,
            is_active=True,
            created_by=self.user
        )
        
        url = f'{self.base_url}ap-invoice-default/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], default.id)
    
    def test_get_ar_invoice_default(self):
        """Test AR invoice default endpoint"""
        default = set_default_combinations.objects.create(
            transaction_type='AR_INVOICE',
            segment_combination=self.combination,
            is_active=True,
            created_by=self.user
        )
        
        url = f'{self.base_url}ar-invoice-default/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], default.id)
    
    def test_get_default_not_found(self):
        """Test getting non-existent default"""
        url = f'{self.base_url}ap-invoice-default/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_validate_default(self):
        """Test validate action"""
        default = set_default_combinations.objects.create(
            transaction_type='AP_INVOICE',
            segment_combination=self.combination,
            is_active=True,
            created_by=self.user
        )
        
        url = f'{self.base_url}{default.id}/validate/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('is_valid', response.data)
        self.assertIn('error_message', response.data)
    
    def test_check_all_validity(self):
        """Test check all validity action"""
        set_default_combinations.objects.create(
            transaction_type='AP_INVOICE',
            segment_combination=self.combination,
            is_active=True,
            created_by=self.user
        )
        
        url = f'{self.base_url}check-all-validity/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('defaults', response.data)
    
    def test_activate_valid_default(self):
        """Test activating a valid default"""
        default = set_default_combinations.objects.create(
            transaction_type='AP_INVOICE',
            segment_combination=self.combination,
            is_active=False,
            created_by=self.user
        )
        
        url = f'{self.base_url}{default.id}/activate/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['data']['is_active'])
    
    def test_activate_invalid_default(self):
        """Test activating an invalid default"""
        # Create combination with missing required segment
        incomplete_combo = XX_Segment_combination.objects.create(
            description='Incomplete',
            is_active=True
        )
        segment_combination_detials.objects.create(
            segment_combination=incomplete_combo,
            segment_type=self.segment_type_entity,
            segment=self.segment_entity
        )
        
        default = set_default_combinations.objects.create(
            transaction_type='AP_INVOICE',
            segment_combination=incomplete_combo,
            is_active=False,
            created_by=self.user
        )
        
        url = f'{self.base_url}{default.id}/activate/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_deactivate_default(self):
        """Test deactivating a default"""
        default = set_default_combinations.objects.create(
            transaction_type='AP_INVOICE',
            segment_combination=self.combination,
            is_active=True,
            created_by=self.user
        )
        
        url = f'{self.base_url}{default.id}/deactivate/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['data']['is_active'])
    
    def test_get_transaction_types(self):
        """Test getting list of transaction types"""
        url = f'{self.base_url}transaction-types/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertGreater(len(response.data), 0)
        
        # Check structure
        first_type = response.data[0]
        self.assertIn('value', first_type)
        self.assertIn('label', first_type)
    
    def test_unauthenticated_access(self):
        """Test that unauthenticated users cannot access endpoints"""
        # Create unauthenticated client
        unauth_client = APIClient()
        
        url = self.base_url
        response = unauth_client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_create_with_invalid_data(self):
        """Test creating with invalid data"""
        url = self.base_url
        data = {
            'transaction_type': 'INVALID_TYPE',
            'segment_combination': self.combination.id,
            'is_active': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_with_missing_combination(self):
        """Test creating with non-existent combination"""
        url = self.base_url
        data = {
            'transaction_type': 'AP_INVOICE',
            'segment_combination': 99999,  # Non-existent
            'is_active': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
