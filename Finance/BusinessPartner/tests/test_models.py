"""
Model Tests for BusinessPartner DRY Architecture

Tests verify:
- Property proxies work correctly
- Manager's create() method extracts fields properly
- Updates propagate from child to parent
- Deletion handles BusinessPartner cleanup
- BusinessPartner protection mechanisms work
"""

from django.test import TestCase
from django.core.exceptions import PermissionDenied, ValidationError
from Finance.BusinessPartner.models import BusinessPartner, Customer, Supplier
from Finance.core.models import Country


class BusinessPartnerModelTests(TestCase):
    """Test the DRY architecture at model level"""
    
    def setUp(self):
        """Set up test data"""
        self.country_us = Country.objects.create(code='US', name='United States')
        self.country_uk = Country.objects.create(code='UK', name='United Kingdom')
    
    def test_cannot_create_business_partner_directly(self):
        """Verify BusinessPartner.objects.create() raises PermissionDenied"""
        with self.assertRaises(PermissionDenied) as context:
            BusinessPartner.objects.create(
                name="Test Partner",
                email="test@example.com"
            )
        
        self.assertIn("Cannot create BusinessPartner directly", str(context.exception))
    
    def test_customer_create_with_manager(self):
        """Create customer using Customer.objects.create()"""
        customer = Customer.objects.create(
            name="Acme Corp",
            email="contact@acme.com",
            phone="+1-555-0123",
            country=self.country_us,
            address="123 Main St",
            notes="Important customer",
            is_active=True,
            address_in_details="Suite 100, Building A"
        )
        
        # Verify Customer created
        self.assertIsNotNone(customer.id)
        self.assertEqual(customer.address_in_details, "Suite 100, Building A")
        
        # Verify BusinessPartner created
        self.assertIsNotNone(customer.business_partner)
        self.assertIsNotNone(customer.business_partner.id)
        
        # Verify all fields set correctly
        self.assertEqual(customer.business_partner.name, "Acme Corp")
        self.assertEqual(customer.business_partner.email, "contact@acme.com")
        self.assertEqual(customer.business_partner.phone, "+1-555-0123")
        self.assertEqual(customer.business_partner.country, self.country_us)
        self.assertEqual(customer.business_partner.address, "123 Main St")
        self.assertEqual(customer.business_partner.notes, "Important customer")
        self.assertTrue(customer.business_partner.is_active)
    
    def test_supplier_create_with_manager(self):
        """Create supplier using Supplier.objects.create()"""
        supplier = Supplier.objects.create(
            name="Tech Supplies Inc",
            email="sales@techsupplies.com",
            phone="+1-555-9999",
            country=self.country_uk,
            address="456 Oak Ave",
            vat_number="VAT123456",
            tax_id="TAX789",
            website="https://techsupplies.com"
        )
        
        # Verify Supplier created
        self.assertIsNotNone(supplier.id)
        self.assertEqual(supplier.vat_number, "VAT123456")
        self.assertEqual(supplier.tax_id, "TAX789")
        self.assertEqual(supplier.website, "https://techsupplies.com")
        
        # Verify BusinessPartner created
        self.assertIsNotNone(supplier.business_partner)
        self.assertEqual(supplier.business_partner.name, "Tech Supplies Inc")
        self.assertEqual(supplier.business_partner.country, self.country_uk)
    
    def test_property_proxies_read(self):
        """Access BusinessPartner fields through customer properties"""
        customer = Customer.objects.create(
            name="Test Customer",
            email="test@customer.com",
            phone="+1-555-1111",
            country=self.country_us,
            address="789 Elm St",
            notes="Test notes",
            is_active=True,
            address_in_details="Floor 2"
        )
        
        # Access through properties (should work via proxies)
        self.assertEqual(customer.name, "Test Customer")
        self.assertEqual(customer.email, "test@customer.com")
        self.assertEqual(customer.phone, "+1-555-1111")
        self.assertEqual(customer.country, self.country_us)
        self.assertEqual(customer.address, "789 Elm St")
        self.assertEqual(customer.notes, "Test notes")
        self.assertTrue(customer.is_active)
        
        # Verify they match BusinessPartner fields
        self.assertEqual(customer.name, customer.business_partner.name)
        self.assertEqual(customer.email, customer.business_partner.email)
        self.assertEqual(customer.phone, customer.business_partner.phone)
    
    def test_property_proxies_write(self):
        """Update BusinessPartner fields through customer properties"""
        customer = Customer.objects.create(
            name="Original Name",
            email="original@email.com",
            address_in_details="Original Address"
        )
        
        # Update through properties
        customer.name = "Updated Name"
        customer.email = "updated@email.com"
        customer.phone = "+1-555-2222"
        customer.address = "Updated Address"
        customer.notes = "Updated notes"
        customer.is_active = False
        customer.save()
        
        # Refresh from database
        customer.refresh_from_db()
        
        # Verify updates persisted
        self.assertEqual(customer.name, "Updated Name")
        self.assertEqual(customer.email, "updated@email.com")
        self.assertEqual(customer.phone, "+1-555-2222")
        self.assertEqual(customer.address, "Updated Address")
        self.assertEqual(customer.notes, "Updated notes")
        self.assertFalse(customer.is_active)
        
        # Verify BusinessPartner was updated
        self.assertEqual(customer.business_partner.name, "Updated Name")
        self.assertEqual(customer.business_partner.email, "updated@email.com")
        self.assertFalse(customer.business_partner.is_active)
    
    def test_customer_update(self):
        """Update multiple fields (BP + Customer-specific)"""
        customer = Customer.objects.create(
            name="Test Corp",
            email="test@corp.com",
            country=self.country_us,
            address_in_details="Suite 1"
        )
        
        # Update both BusinessPartner and Customer fields
        customer.name = "Test Corporation"
        customer.email = "info@corp.com"
        customer.country = self.country_uk
        customer.address_in_details = "Suite 2"
        customer.save()
        
        # Refresh and verify
        customer.refresh_from_db()
        self.assertEqual(customer.name, "Test Corporation")
        self.assertEqual(customer.email, "info@corp.com")
        self.assertEqual(customer.country, self.country_uk)
        self.assertEqual(customer.address_in_details, "Suite 2")
    
    def test_supplier_update(self):
        """Update multiple fields (BP + Supplier-specific)"""
        supplier = Supplier.objects.create(
            name="Original Supplier",
            email="original@supplier.com",
            vat_number="VAT111",
            website="https://original.com"
        )
        
        # Update both types of fields
        supplier.name = "Updated Supplier"
        supplier.email = "updated@supplier.com"
        supplier.vat_number = "VAT222"
        supplier.website = "https://updated.com"
        supplier.save()
        
        # Refresh and verify
        supplier.refresh_from_db()
        self.assertEqual(supplier.name, "Updated Supplier")
        self.assertEqual(supplier.email, "updated@supplier.com")
        self.assertEqual(supplier.vat_number, "VAT222")
        self.assertEqual(supplier.website, "https://updated.com")
    
    def test_customer_delete(self):
        """Delete customer and verify BusinessPartner is also deleted"""
        customer = Customer.objects.create(
            name="To Delete",
            email="delete@test.com",
            address_in_details="Delete me"
        )
        
        bp_id = customer.business_partner.id
        customer_id = customer.id
        
        # Delete customer
        customer.delete()
        
        # Verify customer deleted
        self.assertFalse(Customer.objects.filter(id=customer_id).exists())
        
        # Verify BusinessPartner also deleted
        self.assertFalse(BusinessPartner.objects.filter(id=bp_id).exists())
    
    def test_supplier_delete(self):
        """Delete supplier and verify BusinessPartner is also deleted"""
        supplier = Supplier.objects.create(
            name="To Delete",
            email="delete@supplier.com",
            vat_number="DELETE123"
        )
        
        bp_id = supplier.business_partner.id
        supplier_id = supplier.id
        
        # Delete supplier
        supplier.delete()
        
        # Verify supplier deleted
        self.assertFalse(Supplier.objects.filter(id=supplier_id).exists())
        
        # Verify BusinessPartner also deleted
        self.assertFalse(BusinessPartner.objects.filter(id=bp_id).exists())
    
    def test_cannot_save_business_partner_directly(self):
        """Get BusinessPartner and try to save it directly"""
        customer = Customer.objects.create(
            name="Test Customer",
            email="test@customer.com"
        )
        
        bp = customer.business_partner
        bp.name = "Changed Name"
        
        # Try to save directly - should raise PermissionDenied
        with self.assertRaises(PermissionDenied) as context:
            bp.save()
        
        self.assertIn("Cannot save BusinessPartner directly", str(context.exception))
    
    def test_cannot_delete_business_partner_directly(self):
        """Get BusinessPartner and try to delete it directly"""
        customer = Customer.objects.create(
            name="Test Customer",
            email="test@customer.com"
        )
        
        bp = customer.business_partner
        
        # Try to delete directly - should raise PermissionDenied
        with self.assertRaises(PermissionDenied) as context:
            bp.delete()
        
        self.assertIn("Cannot delete BusinessPartner directly", str(context.exception))
    
    def test_customer_manager_active_method(self):
        """Test Customer.objects.active() method"""
        # Create active and inactive customers
        active1 = Customer.objects.create(name="Active 1", is_active=True)
        active2 = Customer.objects.create(name="Active 2", is_active=True)
        inactive = Customer.objects.create(name="Inactive", is_active=False)
        
        # Get active customers
        active_customers = Customer.objects.active()
        
        # Verify only active returned
        self.assertEqual(active_customers.count(), 2)
        self.assertIn(active1, active_customers)
        self.assertIn(active2, active_customers)
        self.assertNotIn(inactive, active_customers)
    
    def test_supplier_manager_active_method(self):
        """Test Supplier.objects.active() method"""
        # Create active and inactive suppliers
        active1 = Supplier.objects.create(name="Active 1", is_active=True)
        active2 = Supplier.objects.create(name="Active 2", is_active=True)
        inactive = Supplier.objects.create(name="Inactive", is_active=False)
        
        # Get active suppliers
        active_suppliers = Supplier.objects.active()
        
        # Verify only active returned
        self.assertEqual(active_suppliers.count(), 2)
        self.assertIn(active1, active_suppliers)
        self.assertIn(active2, active_suppliers)
        self.assertNotIn(inactive, active_suppliers)
