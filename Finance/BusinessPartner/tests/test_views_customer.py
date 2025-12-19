"""
Customer API View Tests

Tests all Customer API endpoints with the new DRY architecture.
"""

from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from Finance.BusinessPartner.models import Customer, BusinessPartner
from Finance.core.models import Country


class CustomerAPITests(APITestCase):
    """Test Customer API endpoints"""

    def setUp(self):
        """Set up test data"""
        self.country_us = Country.objects.create(code="US", name="United States")
        self.country_uk = Country.objects.create(code="UK", name="United Kingdom")
        self.country_de = Country.objects.create(code="DE", name="Germany")

    def test_customer_list_get(self):
        """GET /api/customers/ - List all customers"""
        # Create test customers
        Customer.objects.create(
            name="Customer 1", email="customer1@test.com", country=self.country_us
        )
        Customer.objects.create(
            name="Customer 2", email="customer2@test.com", country=self.country_uk
        )

        response = self.client.get("/finance/bp/customers/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["data"]["results"]
        self.assertEqual(len(results), 2)

    def test_customer_list_post(self):
        """POST /api/customers/ - Create new customer"""
        data = {
            "name": "New Customer",
            "email": "new@customer.com",
            "phone": "+1-555-1234",
            "country": self.country_us.id,
            "address": "123 Main St",
            "notes": "Test customer",
            "is_active": True,
            "address_in_details": "Suite 100",
        }

        response = self.client.post("/finance/bp/customers/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "New Customer")
        self.assertEqual(response.data["email"], "new@customer.com")

        # Verify customer created in database
        customer = Customer.objects.get(id=response.data["id"])
        self.assertEqual(customer.name, "New Customer")
        self.assertEqual(customer.email, "new@customer.com")

        # Verify BusinessPartner created
        self.assertIsNotNone(customer.business_partner)
        self.assertEqual(customer.business_partner.name, "New Customer")

    def test_customer_detail_get(self):
        """GET /api/customers/{id}/ - Get customer details"""
        customer = Customer.objects.create(
            name="Test Customer",
            email="test@customer.com",
            phone="+1-555-9999",
            country=self.country_us,
            address="456 Oak Ave",
            address_in_details="Floor 2",
        )

        response = self.client.get(f"/finance/bp/customers/{customer.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Test Customer")
        self.assertEqual(response.data["email"], "test@customer.com")
        self.assertEqual(response.data["phone"], "+1-555-9999")
        self.assertEqual(response.data["address_in_details"], "Floor 2")

    def test_customer_detail_put(self):
        """PUT /finance/bp/customers/{id}/ - Update customer"""
        customer = Customer.objects.create(
            name="Original Name",
            email="original@email.com",
            country=self.country_us,
            address_in_details="Original",
        )

        update_data = {
            "name": "Updated Name",
            "email": "updated@email.com",
            "phone": "+1-555-0000",
            "country": self.country_uk.id,
            "address": "Updated Address",
            "address_in_details": "Updated Details",
        }

        response = self.client.put(
            f"/finance/bp/customers/{customer.id}/", update_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Name")
        self.assertEqual(response.data["email"], "updated@email.com")

        # Verify database updated
        customer.refresh_from_db()
        self.assertEqual(customer.name, "Updated Name")
        self.assertEqual(customer.country, self.country_uk)

        # Verify BusinessPartner updated
        self.assertEqual(customer.business_partner.name, "Updated Name")
        self.assertEqual(customer.business_partner.country, self.country_uk)

    def test_customer_detail_patch(self):
        """PATCH /finance/bp/customers/{id}/ - Partial update"""
        customer = Customer.objects.create(
            name="Test Customer",
            email="test@customer.com",
            country=self.country_us,
            address_in_details="Original",
        )

        patch_data = {"email": "patched@email.com", "phone": "+1-555-PATCH"}

        response = self.client.patch(
            f"/finance/bp/customers/{customer.id}/", patch_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "patched@email.com")
        self.assertEqual(response.data["phone"], "+1-555-PATCH")

        # Verify name unchanged
        customer.refresh_from_db()
        self.assertEqual(customer.name, "Test Customer")
        self.assertEqual(customer.email, "patched@email.com")

    def test_customer_detail_delete(self):
        """DELETE /finance/bp/customers/{id}/ - Delete customer"""
        customer = Customer.objects.create(name="To Delete", email="delete@test.com")

        customer_id = customer.id
        bp_id = customer.business_partner.id

        response = self.client.delete(f"/finance/bp/customers/{customer_id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify customer deleted
        self.assertFalse(Customer.objects.filter(id=customer_id).exists())

        # Verify BusinessPartner deleted
        self.assertFalse(BusinessPartner.objects.filter(id=bp_id).exists())

    def test_customer_toggle_active(self):
        """POST /finance/bp/customers/{id}/toggle-active/ - Toggle active status"""
        customer = Customer.objects.create(
            name="Test Customer", email="test@customer.com", is_active=True
        )

        # Toggle to inactive
        response = self.client.post(
            f"/finance/bp/customers/{customer.id}/toggle-active/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_active"])

        # Verify in database
        customer.refresh_from_db()
        self.assertFalse(customer.is_active)

        # Toggle back to active
        response = self.client.post(
            f"/finance/bp/customers/{customer.id}/toggle-active/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_active"])

    def test_customer_active_list(self):
        """GET /finance/bp/customers/active/ - Get only active customers"""
        # Create active and inactive customers
        Customer.objects.create(name="Active 1", is_active=True)
        Customer.objects.create(name="Active 2", is_active=True)
        Customer.objects.create(name="Inactive", is_active=False)

        response = self.client.get("/finance/bp/customers/active/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Response is wrapped in pagination format
        results = response.data["data"]["results"]
        self.assertEqual(len(results), 2)

        # Verify only active returned
        names = [customer["name"] for customer in results]
        self.assertIn("Active 1", names)
        self.assertIn("Active 2", names)
        self.assertNotIn("Inactive", names)

    def test_customer_filter_by_is_active(self):
        """GET /finance/bp/customers/?is_active=true - Filter by active status"""
        Customer.objects.create(name="Active", is_active=True)
        Customer.objects.create(name="Inactive", is_active=False)

        # Filter for active
        response = self.client.get("/finance/bp/customers/?is_active=true")
        results = response.data["data"]["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Active")

        # Filter for inactive
        response = self.client.get("/finance/bp/customers/?is_active=false")
        results = response.data["data"]["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Inactive")

    def test_customer_filter_by_country(self):
        """GET /finance/bp/customers/?country={id} - Filter by country ID"""
        Customer.objects.create(name="US Customer", country=self.country_us)
        Customer.objects.create(name="UK Customer", country=self.country_uk)

        response = self.client.get(
            f"/finance/bp/customers/?country={self.country_us.id}"
        )

        results = response.data["data"]["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "US Customer")

    def test_customer_filter_by_country_code(self):
        """GET /finance/bp/customers/?country_code=US - Filter by country code"""
        Customer.objects.create(name="US Customer", country=self.country_us)
        Customer.objects.create(name="UK Customer", country=self.country_uk)
        Customer.objects.create(name="DE Customer", country=self.country_de)

        response = self.client.get("/finance/bp/customers/?country_code=UK")

        results = response.data["data"]["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "UK Customer")

    def test_customer_filter_by_name(self):
        """GET /finance/bp/customers/?name=Acme - Filter by name"""
        Customer.objects.create(name="Acme Corp")
        Customer.objects.create(name="Acme Industries")
        Customer.objects.create(name="Tech Corp")

        response = self.client.get("/finance/bp/customers/?name=Acme")

        results = response.data["data"]["results"]
        self.assertEqual(len(results), 2)
        names = [c["name"] for c in results]
        self.assertIn("Acme Corp", names)
        self.assertIn("Acme Industries", names)

    def test_customer_filter_by_email(self):
        """GET /finance/bp/customers/?email=@acme.com - Filter by email"""
        Customer.objects.create(name="Customer 1", email="contact@acme.com")
        Customer.objects.create(name="Customer 2", email="sales@acme.com")
        Customer.objects.create(name="Customer 3", email="info@other.com")

        response = self.client.get("/finance/bp/customers/?email=@acme.com")

        results = response.data["data"]["results"]
        self.assertEqual(len(results), 2)

    def test_customer_filter_by_phone(self):
        """GET /finance/bp/customers/?phone=555 - Filter by phone"""
        Customer.objects.create(name="Customer 1", phone="+1-555-0001")
        Customer.objects.create(name="Customer 2", phone="+1-555-0002")
        Customer.objects.create(name="Customer 3", phone="+1-999-0003")

        response = self.client.get("/finance/bp/customers/?phone=555")

        results = response.data["data"]["results"]
        self.assertEqual(len(results), 2)

    def test_customer_search(self):
        """GET /finance/bp/customers/?search=Acme - Search across multiple fields"""
        Customer.objects.create(
            name="Acme Corp", email="contact@acme.com", phone="+1-555-ACME"
        )
        Customer.objects.create(
            name="Tech Corp", email="info@tech.com", phone="+1-555-TECH"
        )

        response = self.client.get("/finance/bp/customers/?search=Acme")

        results = response.data["data"]["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Acme Corp")

    def test_customer_create_validation_error(self):
        """POST /finance/bp/customers/ with invalid data - Missing required name"""
        data = {
            "email": "test@test.com"
            # Missing 'name' field
        }

        response = self.client.post("/finance/bp/customers/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data or response.data.get("error", ""))

    def test_customer_update_validation_error(self):
        """PUT /finance/bp/customers/{id}/ with invalid data"""
        customer = Customer.objects.create(name="Test Customer")

        # Try to update with empty name
        data = {"name": "", "email": "test@test.com"}  # Invalid - empty name

        response = self.client.put(
            f"/finance/bp/customers/{customer.id}/", data, format="json"
        )

        # Should fail validation
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_customer_create_with_country(self):
        """Create customer with country and verify it's set correctly"""
        data = {
            "name": "Test Customer",
            "email": "test@customer.com",
            "country": self.country_de.id,
        }

        response = self.client.post("/finance/bp/customers/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["country"], self.country_de.id)
        self.assertEqual(response.data["country_code"], "DE")

        # Verify BusinessPartner country set
        customer = Customer.objects.get(id=response.data["id"])
        self.assertEqual(customer.business_partner.country, self.country_de)

    def test_customer_update_country(self):
        """Update customer country and verify BusinessPartner updated"""
        customer = Customer.objects.create(
            name="Test Customer", country=self.country_us
        )

        data = {"name": "Test Customer", "country": self.country_uk.id}

        response = self.client.put(
            f"/finance/bp/customers/{customer.id}/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["country"], self.country_uk.id)

        # Verify BusinessPartner updated
        customer.refresh_from_db()
        self.assertEqual(customer.business_partner.country, self.country_uk)
