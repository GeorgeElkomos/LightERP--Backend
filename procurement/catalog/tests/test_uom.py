"""
Comprehensive tests for Unit of Measure API endpoints.
Tests all CRUD operations, filtering, search, and edge cases.
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from procurement.catalog.models import UnitOfMeasure
from .fixtures import get_or_create_test_user, create_unit_of_measure, create_valid_uom_data


class UoMCreateTests(TestCase):
    """Test cases for creating Units of Measure"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        self.url = '/procurement/catalog/uom/'
    
    def test_create_uom_success(self):
        """Test successful UoM creation"""
        data = create_valid_uom_data()
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['code'], 'MTR')
        self.assertEqual(response.data['data']['name'], 'Meters')
        self.assertEqual(response.data['data']['uom_type'], 'LENGTH')
        
        # Verify in database
        self.assertTrue(UnitOfMeasure.objects.filter(code='MTR').exists())
    
    def test_create_uom_code_auto_uppercase(self):
        """Test that code is automatically converted to uppercase"""
        data = create_valid_uom_data(code='kg', name='Kilograms', uom_type='WEIGHT')
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['data']['code'], 'KG')
    
    def test_create_uom_duplicate_code_fails(self):
        """Test creating UoM with duplicate code fails"""
        create_unit_of_measure(code='PCS')
        
        data = create_valid_uom_data(code='PCS', name='Pieces')
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'error')
        self.assertIn('code', response.data['data'])
    
    def test_create_uom_without_code_fails(self):
        """Test creating UoM without code fails"""
        data = create_valid_uom_data()
        del data['code']
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('code', response.data['data'])
    
    def test_create_uom_without_name_fails(self):
        """Test creating UoM without name fails"""
        data = create_valid_uom_data()
        del data['name']
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data['data'])
    
    def test_create_uom_invalid_uom_type(self):
        """Test creating UoM with invalid type fails"""
        data = create_valid_uom_data(uom_type='INVALID')
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('uom_type', response.data['data'])
    
    def test_create_uom_optional_fields(self):
        """Test creating UoM with optional fields"""
        data = {
            'code': 'L',
            'name': 'Liters',
            'uom_type': 'VOLUME',
            'description': 'Volume measurement in liters',
            'is_active': False
        }
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['data']['description'], 'Volume measurement in liters')
        self.assertFalse(response.data['data']['is_active'])


class UoMListTests(TestCase):
    """Test cases for listing Units of Measure"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        self.url = '/procurement/catalog/uom/'
        
        # Create test data
        create_unit_of_measure(code='PCS', name='Pieces', uom_type='QUANTITY', is_active=True)
        create_unit_of_measure(code='KG', name='Kilograms', uom_type='WEIGHT', is_active=True)
        create_unit_of_measure(code='M', name='Meters', uom_type='LENGTH', is_active=False)
        create_unit_of_measure(code='L', name='Liters', uom_type='VOLUME', is_active=True)
    
    def test_list_all_uoms(self):
        """Test listing all Units of Measure"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(len(response.data['data']), 4)
    
    def test_filter_by_active_status(self):
        """Test filtering UoMs by active status"""
        response = self.client.get(self.url, {'is_active': 'true'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 3)
        
        response = self.client.get(self.url, {'is_active': 'false'})
        self.assertEqual(len(response.data['data']), 1)
    
    def test_filter_by_uom_type(self):
        """Test filtering UoMs by type"""
        response = self.client.get(self.url, {'uom_type': 'WEIGHT'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 1)
        self.assertEqual(response.data['data'][0]['code'], 'KG')
    
    def test_search_uoms(self):
        """Test searching UoMs by code or name"""
        response = self.client.get(self.url, {'search': 'KG'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 1)
        
        response = self.client.get(self.url, {'search': 'Meters'})
        self.assertEqual(len(response.data['data']), 1)
    
    def test_list_empty_result(self):
        """Test listing with no matching results"""
        response = self.client.get(self.url, {'search': 'NONEXISTENT'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 0)


class UoMDetailTests(TestCase):
    """Test cases for retrieving UoM details"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        self.uom = create_unit_of_measure()
    
    def test_get_uom_detail(self):
        """Test getting UoM detail"""
        url = f'/procurement/catalog/uom/{self.uom.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['code'], 'PCS')
        self.assertEqual(response.data['data']['name'], 'Pieces')
        self.assertIn('created_at', response.data['data'])
        self.assertIn('updated_at', response.data['data'])
    
    def test_get_nonexistent_uom(self):
        """Test getting nonexistent UoM returns 404"""
        url = '/procurement/catalog/uom/99999/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class UoMUpdateTests(TestCase):
    """Test cases for updating Units of Measure"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        self.uom = create_unit_of_measure()
    
    def test_update_uom_success(self):
        """Test successful UoM update"""
        url = f'/procurement/catalog/uom/{self.uom.id}/'
        data = {
            'name': 'Updated Pieces',
            'description': 'Updated description'
        }
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['name'], 'Updated Pieces')
        self.assertEqual(response.data['data']['description'], 'Updated description')
        
        # Verify in database
        self.uom.refresh_from_db()
        self.assertEqual(self.uom.name, 'Updated Pieces')
    
    def test_update_uom_partial(self):
        """Test partial UoM update"""
        url = f'/procurement/catalog/uom/{self.uom.id}/'
        data = {'is_active': False}
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['data']['is_active'])
        self.assertEqual(response.data['data']['code'], 'PCS')
    
    def test_update_uom_duplicate_code_fails(self):
        """Test updating to duplicate code fails"""
        other_uom = create_unit_of_measure(code='KG', name='Kilograms', uom_type='WEIGHT')
        
        url = f'/procurement/catalog/uom/{self.uom.id}/'
        data = {'code': 'KG'}
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('code', response.data['data'])
    
    def test_update_uom_change_type(self):
        """Test changing UoM type"""
        url = f'/procurement/catalog/uom/{self.uom.id}/'
        data = {'uom_type': 'WEIGHT'}
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['uom_type'], 'WEIGHT')


class UoMDeleteTests(TestCase):
    """Test cases for deleting Units of Measure"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        self.uom = create_unit_of_measure()
    
    def test_delete_uom_success(self):
        """Test deleting a UoM"""
        url = f'/procurement/catalog/uom/{self.uom.id}/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify deleted from database
        self.assertFalse(UnitOfMeasure.objects.filter(id=self.uom.id).exists())
    
    def test_delete_nonexistent_uom(self):
        """Test deleting nonexistent UoM returns 404"""
        url = '/procurement/catalog/uom/99999/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class UoMEdgeCaseTests(TestCase):
    """Test edge cases and boundary conditions"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        self.url = '/procurement/catalog/uom/'
    
    def test_create_uom_with_max_length_code(self):
        """Test creating UoM with maximum code length"""
        data = create_valid_uom_data(code='X' * 10)
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_create_uom_with_max_length_name(self):
        """Test creating UoM with maximum name length"""
        data = create_valid_uom_data(name='X' * 50)
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_create_uom_with_long_description(self):
        """Test creating UoM with long description"""
        data = create_valid_uom_data()
        data['description'] = 'X' * 1000
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_uom_code_case_insensitive_uniqueness(self):
        """Test that code uniqueness is case-insensitive"""
        create_unit_of_measure(code='MTR')
        
        data = create_valid_uom_data(code='mtr')
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('code', response.data['data'])
    
    def test_uom_special_characters_in_code(self):
        """Test UoM with special characters in code"""
        data = create_valid_uom_data(code='M/S')
        response = self.client.post(self.url, data, format='json')
        
        # Should succeed - no validation against special chars
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

