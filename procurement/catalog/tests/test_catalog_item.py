"""
Comprehensive tests for Catalog Item API endpoints.
Tests all CRUD operations, filtering, search, and edge cases.
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from procurement.catalog.models import catalogItem
from .fixtures import get_or_create_test_user, create_catalog_item, create_valid_catalog_item_data


class CatalogItemCreateTests(TestCase):
    """Test cases for creating catalog items"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        self.url = '/procurement/catalog/items/'
    
    def test_create_catalog_item_success(self):
        """Test successful catalog item creation"""
        data = create_valid_catalog_item_data()
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['code'], 'LAPTOP01')
        self.assertEqual(response.data['data']['name'], 'Laptop Computer')
        self.assertIn('short_description', response.data['data'])
        
        # Verify in database
        self.assertTrue(catalogItem.objects.filter(code='LAPTOP01').exists())
    
    def test_create_catalog_item_code_auto_uppercase(self):
        """Test that code is automatically converted to uppercase"""
        data = create_valid_catalog_item_data(code='mouse01', name='Computer Mouse')
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['data']['code'], 'MOUSE01')
    
    def test_create_catalog_item_duplicate_code_fails(self):
        """Test creating item with duplicate code fails"""
        create_catalog_item(code='ITEM001')
        
        data = create_valid_catalog_item_data(code='ITEM001')
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'error')
        self.assertIn('code', response.data['data'])
    
    def test_create_catalog_item_without_code_fails(self):
        """Test creating item without code fails"""
        data = create_valid_catalog_item_data()
        del data['code']
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('code', response.data['data'])
    
    def test_create_catalog_item_without_name_fails(self):
        """Test creating item without name fails"""
        data = create_valid_catalog_item_data()
        del data['name']
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data['data'])
    
    def test_create_catalog_item_without_description_fails(self):
        """Test creating item without description fails"""
        data = create_valid_catalog_item_data()
        del data['description']
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('description', response.data['data'])
    
    def test_create_catalog_item_with_empty_description_fails(self):
        """Test creating item with empty description fails"""
        data = create_valid_catalog_item_data()
        data['description'] = ''
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('description', response.data['data'])
    
    def test_short_description_generation(self):
        """Test that short description is generated correctly"""
        data = create_valid_catalog_item_data()
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        short_desc = response.data['data']['short_description']
        full_desc = response.data['data']['description']
        
        # Short description should be <= 100 chars
        self.assertLessEqual(len(short_desc), 103)  # 100 + "..."


class CatalogItemListTests(TestCase):
    """Test cases for listing catalog items"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        self.url = '/procurement/catalog/items/'
        
        # Create test data
        create_catalog_item(code='LAPTOP01', name='Dell Laptop', description='Business laptop')
        create_catalog_item(code='MOUSE01', name='Wireless Mouse', description='Ergonomic mouse')
        create_catalog_item(code='KEYBOARD01', name='Mechanical Keyboard', description='RGB keyboard')
        create_catalog_item(code='MONITOR01', name='4K Monitor', description='27-inch display')
    
    def test_list_all_items(self):
        """Test listing all catalog items"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(len(response.data['data']), 4)
    
    def test_filter_by_name(self):
        """Test filtering items by name"""
        response = self.client.get(self.url, {'name': 'Mouse'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 1)
        self.assertEqual(response.data['data'][0]['name'], 'Wireless Mouse')
    
    def test_filter_by_code(self):
        """Test filtering items by exact code"""
        response = self.client.get(self.url, {'code': 'LAPTOP01'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 1)
        self.assertEqual(response.data['data'][0]['code'], 'LAPTOP01')
    
    def test_search_items(self):
        """Test searching items by code, name, or description"""
        response = self.client.get(self.url, {'search': 'keyboard'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data['data']), 1)
        
        response = self.client.get(self.url, {'search': 'MONITOR01'})
        self.assertEqual(len(response.data['data']), 1)
        
        response = self.client.get(self.url, {'search': 'RGB'})
        self.assertEqual(len(response.data['data']), 1)
    
    def test_list_empty_result(self):
        """Test listing with no matching results"""
        response = self.client.get(self.url, {'search': 'NONEXISTENT'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 0)
    
    def test_list_shows_minimal_fields(self):
        """Test that list view shows only minimal fields"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        item = response.data['data'][0]
        self.assertIn('id', item)
        self.assertIn('code', item)
        self.assertIn('name', item)
        self.assertNotIn('description', item)
        self.assertNotIn('short_description', item)


class CatalogItemDetailTests(TestCase):
    """Test cases for retrieving catalog item details"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        self.item = create_catalog_item()
    
    def test_get_item_detail(self):
        """Test getting item detail"""
        url = f'/procurement/catalog/items/{self.item.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['code'], 'ITEM001')
        self.assertEqual(response.data['data']['name'], 'Test Item')
        self.assertIn('description', response.data['data'])
        self.assertIn('short_description', response.data['data'])
    
    def test_get_nonexistent_item(self):
        """Test getting nonexistent item returns 404"""
        url = '/procurement/catalog/items/99999/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CatalogItemUpdateTests(TestCase):
    """Test cases for updating catalog items"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        self.item = create_catalog_item()
    
    def test_update_item_success(self):
        """Test successful item update"""
        url = f'/procurement/catalog/items/{self.item.id}/'
        data = {
            'name': 'Updated Item Name',
            'description': 'Updated description'
        }
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['name'], 'Updated Item Name')
        self.assertEqual(response.data['data']['description'], 'Updated description')
        
        # Verify in database
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, 'Updated Item Name')
    
    def test_update_item_partial(self):
        """Test partial item update"""
        url = f'/procurement/catalog/items/{self.item.id}/'
        data = {'name': 'New Name Only'}
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['name'], 'New Name Only')
        self.assertEqual(response.data['data']['code'], 'ITEM001')
    
    def test_update_item_duplicate_code_fails(self):
        """Test updating to duplicate code fails"""
        other_item = create_catalog_item(code='OTHER01', name='Other Item', description='Other')
        
        url = f'/procurement/catalog/items/{self.item.id}/'
        data = {'code': 'OTHER01'}
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('code', response.data['data'])
    
    def test_update_item_code_to_uppercase(self):
        """Test updating code converts to uppercase"""
        url = f'/procurement/catalog/items/{self.item.id}/'
        data = {'code': 'newcode01'}
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['code'], 'NEWCODE01')


class CatalogItemDeleteTests(TestCase):
    """Test cases for deleting catalog items"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        self.item = create_catalog_item()
    
    def test_delete_item_success(self):
        """Test deleting an item"""
        url = f'/procurement/catalog/items/{self.item.id}/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify deleted from database
        self.assertFalse(catalogItem.objects.filter(id=self.item.id).exists())
    
    def test_delete_nonexistent_item(self):
        """Test deleting nonexistent item returns 404"""
        url = '/procurement/catalog/items/99999/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CatalogItemByCodeTests(TestCase):
    """Test cases for getting catalog items by code"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        self.item = create_catalog_item(code='TEST01')
    
    def test_get_item_by_code_success(self):
        """Test getting item by code"""
        url = '/procurement/catalog/items/by-code/TEST01/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['code'], 'TEST01')
    
    def test_get_item_by_code_case_insensitive(self):
        """Test getting item by code is case-insensitive"""
        url = '/procurement/catalog/items/by-code/test01/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['code'], 'TEST01')
    
    def test_get_item_by_nonexistent_code(self):
        """Test getting item by nonexistent code returns 404"""
        url = '/procurement/catalog/items/by-code/NONEXISTENT/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['status'], 'error')


class CatalogItemSearchTests(TestCase):
    """Test cases for searching catalog items"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        self.url = '/procurement/catalog/items/search/'
        
        # Create test data
        create_catalog_item(code='LAPTOP01', name='Dell Laptop', description='Business laptop')
        create_catalog_item(code='LAPTOP02', name='HP Laptop', description='Gaming laptop')
        create_catalog_item(code='MOUSE01', name='Wireless Mouse', description='Ergonomic')
    
    def test_search_items_by_name(self):
        """Test searching items by name"""
        response = self.client.get(self.url, {'q': 'Laptop'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(len(response.data['data']), 2)
    
    def test_search_items_case_insensitive(self):
        """Test search is case-insensitive"""
        response = self.client.get(self.url, {'q': 'laptop'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 2)
    
    def test_search_items_partial_match(self):
        """Test search with partial match"""
        response = self.client.get(self.url, {'q': 'Dell'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 1)
        self.assertEqual(response.data['data'][0]['name'], 'Dell Laptop')
    
    def test_search_without_query_fails(self):
        """Test search without query parameter fails"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'error')
    
    def test_search_no_results(self):
        """Test search with no matching results"""
        response = self.client.get(self.url, {'q': 'NONEXISTENT'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 0)
    
    def test_search_returns_short_description(self):
        """Test search results include short description"""
        response = self.client.get(self.url, {'q': 'Laptop'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        item = response.data['data'][0]
        self.assertIn('short_description', item)
        self.assertLessEqual(len(item['short_description']), 53)  # 50 + "..."


class CatalogItemEdgeCaseTests(TestCase):
    """Test edge cases and boundary conditions"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = get_or_create_test_user()
        self.client.force_authenticate(user=self.user)
        self.url = '/procurement/catalog/items/'
    
    def test_create_item_with_max_length_code(self):
        """Test creating item with maximum code length"""
        data = create_valid_catalog_item_data(code='X' * 50)
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_create_item_with_max_length_name(self):
        """Test creating item with maximum name length"""
        data = create_valid_catalog_item_data(name='X' * 255)
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_create_item_with_very_long_description(self):
        """Test creating item with very long description"""
        data = create_valid_catalog_item_data()
        data['description'] = 'X' * 5000
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_short_description_truncation(self):
        """Test short description is truncated for long descriptions"""
        long_desc = 'A' * 200
        data = create_valid_catalog_item_data()
        data['description'] = long_desc
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        short_desc = response.data['data']['short_description']
        self.assertLess(len(short_desc), len(long_desc))
        self.assertTrue(short_desc.endswith('...'))
    
    def test_code_case_insensitive_uniqueness(self):
        """Test that code uniqueness is case-insensitive"""
        create_catalog_item(code='TEST01')
        
        data = create_valid_catalog_item_data(code='test01')
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('code', response.data['data'])
    
    def test_special_characters_in_code(self):
        """Test item with special characters in code"""
        data = create_valid_catalog_item_data(code='ITEM-001-A')
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['data']['code'], 'ITEM-001-A')
    
    def test_unicode_in_name_and_description(self):
        """Test item with unicode characters"""
        data = create_valid_catalog_item_data(
            name='Café Equipment ☕',
            code='CAFE01'
        )
        data['description'] = 'High-quality café equipment with ☕ symbol'
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['data']['name'], 'Café Equipment ☕')

