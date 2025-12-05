"""
Supplier API View Tests

Tests all Supplier API endpoints with the new DRY architecture.
"""

from rest_framework.test import APITestCase
from rest_framework import status
from Finance.BusinessPartner.models import Supplier, BusinessPartner
from Finance.core.models import Country


class SupplierAPITests(APITestCase):
    """Test Supplier API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.country_us = Country.objects.create(code='US', name='United States')
        self.country_uk = Country.objects.create(code='UK', name='United Kingdom')
        self.country_de = Country.objects.create(code='DE', name='Germany')
    
    def test_supplier_list_get(self):
        """GET /finance/bp/suppliers/ - List all suppliers"""
        Supplier.objects.create(
            name="Supplier 1",
            email="supplier1@test.com",
            vat_number="VAT001"
        )
        Supplier.objects.create(
            name="Supplier 2",
            email="supplier2@test.com",
            vat_number="VAT002"
        )
        
        response = self.client.get('/finance/bp/suppliers/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
    
    def test_supplier_list_post(self):
        """POST /finance/bp/suppliers/ - Create new supplier"""
        data = {
            'name': 'New Supplier',
            'email': 'new@supplier.com',
            'phone': '+1-555-1234',
            'country': self.country_us.id,
            'address': '789 Tech Blvd',
            'vat_number': 'VAT123456',
            'tax_id': 'TAX789',
            'website': 'https://newsupplier.com'
        }
        
        response = self.client.post('/finance/bp/suppliers/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Supplier')
        self.assertEqual(response.data['vat_number'], 'VAT123456')
        
        # Verify supplier created
        supplier = Supplier.objects.get(id=response.data['id'])
        self.assertEqual(supplier.name, 'New Supplier')
        self.assertEqual(supplier.vat_number, 'VAT123456')
        
        # Verify BusinessPartner created
        self.assertIsNotNone(supplier.business_partner)
        self.assertEqual(supplier.business_partner.name, 'New Supplier')
    
    def test_supplier_detail_get(self):
        """GET /finance/bp/suppliers/{id}/ - Get supplier details"""
        supplier = Supplier.objects.create(
            name="Test Supplier",
            email="test@supplier.com",
            phone="+1-555-9999",
            country=self.country_uk,
            vat_number="UK123456",
            website="https://testsupplier.com"
        )
        
        response = self.client.get(f'/finance/bp/suppliers/{supplier.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Supplier')
        self.assertEqual(response.data['vat_number'], 'UK123456')
        self.assertEqual(response.data['website'], 'https://testsupplier.com')
    
    def test_supplier_detail_put(self):
        """PUT /finance/bp/suppliers/{id}/ - Update supplier"""
        supplier = Supplier.objects.create(
            name="Original Supplier",
            email="original@supplier.com",
            vat_number="VAT111",
            country=self.country_us
        )
        
        update_data = {
            'name': 'Updated Supplier',
            'email': 'updated@supplier.com',
            'phone': '+44-555-0000',
            'country': self.country_uk.id,
            'vat_number': 'VAT222',
            'website': 'https://updated.com'
        }
        
        response = self.client.put(
            f'/finance/bp/suppliers/{supplier.id}/',
            update_data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Supplier')
        self.assertEqual(response.data['vat_number'], 'VAT222')
        
        # Verify database updated
        supplier.refresh_from_db()
        self.assertEqual(supplier.name, 'Updated Supplier')
        self.assertEqual(supplier.country, self.country_uk)
        
        # Verify BusinessPartner updated
        self.assertEqual(supplier.business_partner.name, 'Updated Supplier')
        self.assertEqual(supplier.business_partner.country, self.country_uk)
    
    def test_supplier_detail_patch(self):
        """PATCH /finance/bp/suppliers/{id}/ - Partial update"""
        supplier = Supplier.objects.create(
            name="Test Supplier",
            email="test@supplier.com",
            vat_number="VAT123"
        )
        
        patch_data = {
            'vat_number': 'VAT999',
            'website': 'https://patched.com'
        }
        
        response = self.client.patch(
            f'/finance/bp/suppliers/{supplier.id}/',
            patch_data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['vat_number'], 'VAT999')
        self.assertEqual(response.data['website'], 'https://patched.com')
        
        # Verify name unchanged
        supplier.refresh_from_db()
        self.assertEqual(supplier.name, 'Test Supplier')
        self.assertEqual(supplier.vat_number, 'VAT999')
    
    def test_supplier_detail_delete(self):
        """DELETE /finance/bp/suppliers/{id}/ - Delete supplier"""
        supplier = Supplier.objects.create(
            name="To Delete",
            email="delete@supplier.com",
            vat_number="DELETE123"
        )
        
        supplier_id = supplier.id
        bp_id = supplier.business_partner.id
        
        response = self.client.delete(f'/finance/bp/suppliers/{supplier_id}/')
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify supplier deleted
        self.assertFalse(Supplier.objects.filter(id=supplier_id).exists())
        
        # Verify BusinessPartner deleted
        self.assertFalse(BusinessPartner.objects.filter(id=bp_id).exists())
    
    def test_supplier_toggle_active(self):
        """POST /finance/bp/suppliers/{id}/toggle-active/ - Toggle active status"""
        supplier = Supplier.objects.create(
            name="Test Supplier",
            email="test@supplier.com",
            is_active=True
        )
        
        # Toggle to inactive
        response = self.client.post(f'/finance/bp/suppliers/{supplier.id}/toggle-active/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_active'])
        
        # Verify in database
        supplier.refresh_from_db()
        self.assertFalse(supplier.is_active)
        
        # Toggle back to active
        response = self.client.post(f'/finance/bp/suppliers/{supplier.id}/toggle-active/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_active'])
    
    def test_supplier_active_list(self):
        """GET /finance/bp/suppliers/active/ - Get only active suppliers"""
        Supplier.objects.create(name="Active 1", is_active=True)
        Supplier.objects.create(name="Active 2", is_active=True)
        Supplier.objects.create(name="Inactive", is_active=False)
        
        response = self.client.get('/finance/bp/suppliers/active/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        
        # Verify only active returned
        names = [supplier['name'] for supplier in response.data]
        self.assertIn('Active 1', names)
        self.assertIn('Active 2', names)
        self.assertNotIn('Inactive', names)
    
    def test_supplier_filter_by_vat_number(self):
        """GET /finance/bp/suppliers/?vat_number=VAT123 - Filter by VAT number"""
        Supplier.objects.create(name="Supplier 1", vat_number="VAT123456")
        Supplier.objects.create(name="Supplier 2", vat_number="VAT789012")
        Supplier.objects.create(name="Supplier 3", vat_number="DE999999")
        
        response = self.client.get('/finance/bp/suppliers/?vat_number=VAT123')
        
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Supplier 1')
    
    def test_supplier_filter_by_tax_id(self):
        """GET /finance/bp/suppliers/?tax_id=TAX456 - Filter by tax ID"""
        Supplier.objects.create(name="Supplier 1", tax_id="TAX123")
        Supplier.objects.create(name="Supplier 2", tax_id="TAX456")
        Supplier.objects.create(name="Supplier 3", tax_id="TAX789")
        
        response = self.client.get('/finance/bp/suppliers/?tax_id=TAX456')
        
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Supplier 2')
    
    def test_supplier_search(self):
        """GET /finance/bp/suppliers/?search=Tech - Search across multiple fields"""
        Supplier.objects.create(
            name="Tech Supplies Inc",
            email="sales@techsupplies.com",
            vat_number="TECH123"
        )
        Supplier.objects.create(
            name="Office Supplies",
            email="info@office.com",
            vat_number="OFF456"
        )
        
        response = self.client.get('/finance/bp/suppliers/?search=Tech')
        
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Tech Supplies Inc')
    
    def test_supplier_create_with_all_fields(self):
        """Create supplier with all fields and verify they're set correctly"""
        data = {
            'name': 'Complete Supplier',
            'email': 'complete@supplier.com',
            'phone': '+49-555-1234',
            'country': self.country_de.id,
            'address': '123 Berlin St',
            'notes': 'Important supplier',
            'is_active': True,
            'vat_number': 'DE123456789',
            'tax_id': 'TAX999',
            'website': 'https://complete.de'
        }
        
        response = self.client.post('/finance/bp/suppliers/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify all fields
        self.assertEqual(response.data['name'], 'Complete Supplier')
        self.assertEqual(response.data['email'], 'complete@supplier.com')
        self.assertEqual(response.data['phone'], '+49-555-1234')
        self.assertEqual(response.data['country'], self.country_de.id)
        self.assertEqual(response.data['vat_number'], 'DE123456789')
        self.assertEqual(response.data['tax_id'], 'TAX999')
        self.assertEqual(response.data['website'], 'https://complete.de')
        
        # Verify BusinessPartner fields
        supplier = Supplier.objects.get(id=response.data['id'])
        self.assertEqual(supplier.business_partner.name, 'Complete Supplier')
        self.assertEqual(supplier.business_partner.country, self.country_de)
        self.assertEqual(supplier.business_partner.notes, 'Important supplier')
    
    def test_supplier_update_vat_number(self):
        """Update supplier VAT number and verify it persists"""
        supplier = Supplier.objects.create(
            name="Test Supplier",
            vat_number="VAT111"
        )
        
        data = {
            'name': 'Test Supplier',
            'vat_number': 'VAT222'
        }
        
        response = self.client.put(
            f'/finance/bp/suppliers/{supplier.id}/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['vat_number'], 'VAT222')
        
        # Verify persisted
        supplier.refresh_from_db()
        self.assertEqual(supplier.vat_number, 'VAT222')
    
    def test_supplier_update_website(self):
        """Update supplier website and verify it persists"""
        supplier = Supplier.objects.create(
            name="Test Supplier",
            website="https://old.com"
        )
        
        patch_data = {
            'website': 'https://new.com'
        }
        
        response = self.client.patch(
            f'/finance/bp/suppliers/{supplier.id}/',
            patch_data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['website'], 'https://new.com')
        
        # Verify persisted
        supplier.refresh_from_db()
        self.assertEqual(supplier.website, 'https://new.com')
    
    def test_supplier_filter_by_country_code(self):
        """GET /finance/bp/suppliers/?country_code=DE - Filter by country code"""
        Supplier.objects.create(name="US Supplier", country=self.country_us)
        Supplier.objects.create(name="UK Supplier", country=self.country_uk)
        Supplier.objects.create(name="DE Supplier", country=self.country_de)
        
        response = self.client.get('/finance/bp/suppliers/?country_code=DE')
        
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'DE Supplier')
    
    def test_supplier_filter_by_is_active(self):
        """GET /finance/bp/suppliers/?is_active=true - Filter by active status"""
        Supplier.objects.create(name="Active", is_active=True)
        Supplier.objects.create(name="Inactive", is_active=False)
        
        # Filter for active
        response = self.client.get('/finance/bp/suppliers/?is_active=true')
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Active')
        
        # Filter for inactive
        response = self.client.get('/finance/bp/suppliers/?is_active=false')
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Inactive')
