"""
Serializer Tests for BusinessPartner

Tests verify that serializers work correctly with property proxies.
"""

from django.test import TestCase
from Finance.BusinessPartner.models import Customer, Supplier
from Finance.BusinessPartner.serializers import (
    CustomerSerializer,
    CustomerListSerializer,
    SupplierSerializer,
    SupplierListSerializer
)
from Finance.core.models import Country


class CustomerSerializerTests(TestCase):
    """Test CustomerSerializer with property proxies"""
    
    def setUp(self):
        """Set up test data"""
        self.country_us = Country.objects.create(code='US', name='United States')
        self.country_uk = Country.objects.create(code='UK', name='United Kingdom')
    
    def test_customer_serializer_create(self):
        """Use CustomerSerializer to create customer"""
        data = {
            'name': 'Acme Corp',
            'email': 'contact@acme.com',
            'phone': '+1-555-0123',
            'country': self.country_us.id,
            'address': '123 Main St',
            'notes': 'Important customer',
            'is_active': True,
            'address_in_details': 'Suite 100'
        }
        
        serializer = CustomerSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        
        customer = serializer.save()
        
        # Verify customer created
        self.assertIsNotNone(customer.id)
        self.assertEqual(customer.name, 'Acme Corp')
        self.assertEqual(customer.email, 'contact@acme.com')
        self.assertEqual(customer.phone, '+1-555-0123')
        self.assertEqual(customer.country, self.country_us)
        self.assertEqual(customer.address, '123 Main St')
        self.assertEqual(customer.address_in_details, 'Suite 100')
        
        # Verify BusinessPartner fields accessible
        self.assertEqual(customer.business_partner.name, 'Acme Corp')
        self.assertEqual(customer.business_partner.email, 'contact@acme.com')
    
    def test_customer_serializer_update(self):
        """Use serializer to update customer"""
        customer = Customer.objects.create(
            name="Original Name",
            email="original@email.com",
            country=self.country_us,
            address_in_details="Original Details"
        )
        
        update_data = {
            'name': 'Updated Name',
            'email': 'updated@email.com',
            'country': self.country_uk.id,
            'phone': '+44-555-9999',
            'address_in_details': 'Updated Details'
        }
        
        serializer = CustomerSerializer(customer, data=update_data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        
        updated_customer = serializer.save()
        
        # Verify updates
        self.assertEqual(updated_customer.name, 'Updated Name')
        self.assertEqual(updated_customer.email, 'updated@email.com')
        self.assertEqual(updated_customer.country, self.country_uk)
        self.assertEqual(updated_customer.phone, '+44-555-9999')
        self.assertEqual(updated_customer.address_in_details, 'Updated Details')
        
        # Verify BusinessPartner updated
        self.assertEqual(updated_customer.business_partner.name, 'Updated Name')
        self.assertEqual(updated_customer.business_partner.country, self.country_uk)
    
    def test_customer_serializer_read(self):
        """Serialize customer and verify all fields present"""
        customer = Customer.objects.create(
            name="Test Corp",
            email="test@corp.com",
            phone="+1-555-1234",
            country=self.country_us,
            address="456 Oak Ave",
            notes="Test notes",
            is_active=True,
            address_in_details="Floor 3"
        )
        
        serializer = CustomerSerializer(customer)
        data = serializer.data
        
        # Verify all fields present
        self.assertEqual(data['name'], 'Test Corp')
        self.assertEqual(data['email'], 'test@corp.com')
        self.assertEqual(data['phone'], '+1-555-1234')
        self.assertEqual(data['country'], self.country_us.id)
        self.assertEqual(data['country_name'], 'United States')
        self.assertEqual(data['country_code'], 'US')
        self.assertEqual(data['address'], '456 Oak Ave')
        self.assertEqual(data['notes'], 'Test notes')
        self.assertTrue(data['is_active'])
        self.assertEqual(data['address_in_details'], 'Floor 3')
        self.assertIn('id', data)
        self.assertIn('created_at', data)
        self.assertIn('updated_at', data)
    
    def test_customer_list_serializer(self):
        """Test CustomerListSerializer for lightweight serialization"""
        customer1 = Customer.objects.create(
            name="Customer 1",
            email="customer1@test.com",
            phone="+1-555-0001",
            country=self.country_us,
            is_active=True
        )
        customer2 = Customer.objects.create(
            name="Customer 2",
            email="customer2@test.com",
            phone="+1-555-0002",
            country=self.country_uk,
            is_active=False
        )
        
        customers = Customer.objects.all()
        serializer = CustomerListSerializer(customers, many=True)
        data = serializer.data
        
        # Verify lightweight serialization
        self.assertEqual(len(data), 2)
        
        # Check first customer
        self.assertEqual(data[0]['name'], 'Customer 1')
        self.assertEqual(data[0]['email'], 'customer1@test.com')
        self.assertEqual(data[0]['phone'], '+1-555-0001')
        self.assertEqual(data[0]['country_code'], 'US')
        self.assertTrue(data[0]['is_active'])
        
        # Verify only lightweight fields present
        self.assertIn('id', data[0])
        self.assertNotIn('address', data[0])
        self.assertNotIn('notes', data[0])


class SupplierSerializerTests(TestCase):
    """Test SupplierSerializer with property proxies"""
    
    def setUp(self):
        """Set up test data"""
        self.country_us = Country.objects.create(code='US', name='United States')
        self.country_de = Country.objects.create(code='DE', name='Germany')
    
    def test_supplier_serializer_create(self):
        """Use SupplierSerializer to create supplier"""
        data = {
            'name': 'Tech Supplies Inc',
            'email': 'sales@techsupplies.com',
            'phone': '+1-555-9999',
            'country': self.country_us.id,
            'address': '789 Tech Blvd',
            'vat_number': 'VAT123456',
            'tax_id': 'TAX789',
            'website': 'https://techsupplies.com'
        }
        
        serializer = SupplierSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        
        supplier = serializer.save()
        
        # Verify supplier created
        self.assertIsNotNone(supplier.id)
        self.assertEqual(supplier.name, 'Tech Supplies Inc')
        self.assertEqual(supplier.vat_number, 'VAT123456')
        self.assertEqual(supplier.tax_id, 'TAX789')
        self.assertEqual(supplier.website, 'https://techsupplies.com')
        
        # Verify BusinessPartner fields
        self.assertEqual(supplier.business_partner.name, 'Tech Supplies Inc')
        self.assertEqual(supplier.business_partner.email, 'sales@techsupplies.com')
    
    def test_supplier_serializer_update(self):
        """Use serializer to update supplier"""
        supplier = Supplier.objects.create(
            name="Original Supplier",
            email="original@supplier.com",
            vat_number="VAT111",
            website="https://original.com"
        )
        
        update_data = {
            'name': 'Updated Supplier',
            'email': 'updated@supplier.com',
            'vat_number': 'VAT222',
            'website': 'https://updated.com',
            'country': self.country_de.id
        }
        
        serializer = SupplierSerializer(supplier, data=update_data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        
        updated_supplier = serializer.save()
        
        # Verify updates
        self.assertEqual(updated_supplier.name, 'Updated Supplier')
        self.assertEqual(updated_supplier.email, 'updated@supplier.com')
        self.assertEqual(updated_supplier.vat_number, 'VAT222')
        self.assertEqual(updated_supplier.website, 'https://updated.com')
        self.assertEqual(updated_supplier.country, self.country_de)
    
    def test_supplier_serializer_read(self):
        """Serialize supplier and verify all fields present"""
        supplier = Supplier.objects.create(
            name="Test Supplier",
            email="test@supplier.com",
            phone="+49-555-1234",
            country=self.country_de,
            address="123 Berlin St",
            vat_number="DE123456789",
            tax_id="TAX999",
            website="https://testsupplier.de"
        )
        
        serializer = SupplierSerializer(supplier)
        data = serializer.data
        
        # Verify all fields present
        self.assertEqual(data['name'], 'Test Supplier')
        self.assertEqual(data['email'], 'test@supplier.com')
        self.assertEqual(data['phone'], '+49-555-1234')
        self.assertEqual(data['country'], self.country_de.id)
        self.assertEqual(data['country_name'], 'Germany')
        self.assertEqual(data['country_code'], 'DE')
        self.assertEqual(data['vat_number'], 'DE123456789')
        self.assertEqual(data['tax_id'], 'TAX999')
        self.assertEqual(data['website'], 'https://testsupplier.de')
        self.assertIn('id', data)
        self.assertIn('created_at', data)
        self.assertIn('updated_at', data)
    
    def test_supplier_list_serializer(self):
        """Test SupplierListSerializer for lightweight serialization"""
        supplier1 = Supplier.objects.create(
            name="Supplier 1",
            email="supplier1@test.com",
            phone="+1-555-0001",
            country=self.country_us,
            vat_number="VAT001",
            is_active=True
        )
        supplier2 = Supplier.objects.create(
            name="Supplier 2",
            email="supplier2@test.com",
            phone="+49-555-0002",
            country=self.country_de,
            vat_number="VAT002",
            is_active=False
        )
        
        suppliers = Supplier.objects.all()
        serializer = SupplierListSerializer(suppliers, many=True)
        data = serializer.data
        
        # Verify lightweight serialization
        self.assertEqual(len(data), 2)
        
        # Check first supplier
        self.assertEqual(data[0]['name'], 'Supplier 1')
        self.assertEqual(data[0]['email'], 'supplier1@test.com')
        self.assertEqual(data[0]['phone'], '+1-555-0001')
        self.assertEqual(data[0]['country_code'], 'US')
        self.assertEqual(data[0]['vat_number'], 'VAT001')
        self.assertTrue(data[0]['is_active'])
        
        # Verify only lightweight fields present
        self.assertIn('id', data[0])
        self.assertNotIn('address', data[0])
        self.assertNotIn('website', data[0])
