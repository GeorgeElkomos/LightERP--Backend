"""
API Views Tests for Approval Workflow endpoints.
Tests all CRUD operations for workflow templates and stage templates.
"""

from django.test import TestCase
from django.urls import reverse
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

from core.approval.models import (
    ApprovalWorkflowTemplate,
    ApprovalWorkflowStageTemplate,
    ApprovalWorkflowInstance,
    TestInvoice,
    TestPurchaseOrder,
)
from core.job_roles.models import JobRole

User = get_user_model()


class WorkflowTemplateAPITest(TestCase):
    """Test ApprovalWorkflowTemplate API endpoints."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create test user
        self.user = User.objects.create_user(
            email="testuser@test.com",
            name="Test User",
            phone_number="1234567890",
            password="testpass123",
        )

        # Create job role
        self.role = JobRole.objects.create(name="Manager")

        # Get content types
        self.invoice_ct = ContentType.objects.get_for_model(TestInvoice)
        self.po_ct = ContentType.objects.get_for_model(TestPurchaseOrder)

        # Create test templates
        self.template1 = ApprovalWorkflowTemplate.objects.create(
            code="TEST_INVOICE_APPROVAL",
            name="Test Invoice Approval",
            description="Test template for invoices",
            content_type=self.invoice_ct,
            is_active=True,
            version=1,
        )

        self.template2 = ApprovalWorkflowTemplate.objects.create(
            code="TEST_PO_APPROVAL",
            name="Test PO Approval",
            description="Test template for purchase orders",
            content_type=self.po_ct,
            is_active=False,
            version=1,
        )

        # Create stages for template1
        self.stage1 = ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=self.template1,
            order_index=1,
            name="Manager Review",
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY,
            allow_reject=True,
            allow_delegate=False,
        )

        self.stage2 = ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=self.template1,
            order_index=2,
            name="Director Approval",
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ALL,
            required_role=self.role,
            allow_reject=True,
            allow_delegate=True,
            sla_hours=24,
        )

    def test_list_workflow_templates(self):
        """Test GET /workflow-templates/"""
        url = reverse("core:approval:workflow-template-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["data"]["results"]
        self.assertEqual(len(results), 2)

        # Check structure
        template_data = results[0]
        self.assertIn("id", template_data)
        self.assertIn("code", template_data)
        self.assertIn("name", template_data)
        self.assertIn("content_type_details", template_data)
        self.assertIn("stage_count", template_data)

    def test_filter_workflow_templates_by_active(self):
        """Test filtering templates by is_active."""
        url = reverse("core:approval:workflow-template-list")

        # Filter active
        response = self.client.get(url, {"is_active": "true"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["data"]["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["code"], "TEST_INVOICE_APPROVAL")

        # Filter inactive
        response = self.client.get(url, {"is_active": "false"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["data"]["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["code"], "TEST_PO_APPROVAL")

    def test_filter_workflow_templates_by_content_type(self):
        """Test filtering templates by content_type."""
        url = reverse("core:approval:workflow-template-list")
        response = self.client.get(url, {"content_type": self.invoice_ct.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["data"]["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["code"], "TEST_INVOICE_APPROVAL")

    def test_filter_workflow_templates_by_code(self):
        """Test filtering templates by code."""
        url = reverse("core:approval:workflow-template-list")
        response = self.client.get(url, {"code": "TEST_INVOICE_APPROVAL"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["data"]["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Test Invoice Approval")

    def test_create_workflow_template(self):
        """Test POST /workflow-templates/"""
        url = reverse("core:approval:workflow-template-list")
        data = {
            "code": "NEW_TEMPLATE",
            "name": "New Template",
            "description": "A new test template",
            "content_type": self.invoice_ct.id,
            "is_active": True,
            "version": 1,
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["code"], "NEW_TEMPLATE")
        self.assertEqual(response.data["name"], "New Template")

        # Verify in database
        template = ApprovalWorkflowTemplate.objects.get(code="NEW_TEMPLATE")
        self.assertEqual(template.name, "New Template")

    def test_create_workflow_template_with_stages(self):
        """Test creating template with nested stages."""
        url = reverse("core:approval:workflow-template-list")
        data = {
            "code": "TEMPLATE_WITH_STAGES",
            "name": "Template with Stages",
            "content_type": self.invoice_ct.id,
            "is_active": True,
            "version": 1,
            "stages": [
                {
                    "order_index": 1,
                    "name": "First Stage",
                    "decision_policy": "ANY",
                    "allow_reject": True,
                    "allow_delegate": False,
                },
                {
                    "order_index": 2,
                    "name": "Second Stage",
                    "decision_policy": "ALL",
                    "allow_reject": True,
                    "allow_delegate": True,
                },
            ],
        }

        response = self.client.post(url, data, format="json")

        # Debug: print error if any
        if response.status_code != status.HTTP_201_CREATED:
            print(f"Error: {response.data}")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify stages created
        template = ApprovalWorkflowTemplate.objects.get(code="TEMPLATE_WITH_STAGES")
        self.assertEqual(template.stages.count(), 2)
        self.assertEqual(template.stages.get(order_index=1).name, "First Stage")

    def test_create_workflow_template_duplicate_code(self):
        """Test creating template with duplicate code fails."""
        url = reverse("core:approval:workflow-template-list")
        data = {
            "code": "TEST_INVOICE_APPROVAL",  # Already exists
            "name": "Duplicate Template",
            "content_type": self.invoice_ct.id,
            "is_active": True,
            "version": 1,
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("code", response.data)

    def test_get_workflow_template_detail(self):
        """Test GET /workflow-templates/{id}/"""
        url = reverse(
            "core:approval:workflow-template-detail", args=[self.template1.id]
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "TEST_INVOICE_APPROVAL")
        self.assertEqual(response.data["stage_count"], 2)
        self.assertEqual(len(response.data["stages"]), 2)

    def test_update_workflow_template(self):
        """Test PUT /workflow-templates/{id}/"""
        url = reverse(
            "core:approval:workflow-template-detail", args=[self.template1.id]
        )
        data = {
            "code": "TEST_INVOICE_APPROVAL",
            "name": "Updated Invoice Approval",
            "description": "Updated description",
            "content_type": self.invoice_ct.id,
            "is_active": False,
            "version": 2,
        }

        response = self.client.put(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Invoice Approval")
        self.assertEqual(response.data["version"], 2)

        # Verify in database
        self.template1.refresh_from_db()
        self.assertEqual(self.template1.name, "Updated Invoice Approval")

    def test_partial_update_workflow_template(self):
        """Test PATCH /workflow-templates/{id}/"""
        url = reverse(
            "core:approval:workflow-template-detail", args=[self.template1.id]
        )
        data = {"is_active": False}

        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["is_active"], False)
        self.assertEqual(response.data["name"], "Test Invoice Approval")  # Unchanged

    def test_delete_workflow_template(self):
        """Test DELETE /workflow-templates/{id}/"""
        url = reverse(
            "core:approval:workflow-template-detail", args=[self.template2.id]
        )
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("deleted successfully", response.data["message"])

        # Verify deleted
        self.assertFalse(
            ApprovalWorkflowTemplate.objects.filter(id=self.template2.id).exists()
        )

    def test_delete_workflow_template_with_active_instances(self):
        """Test that deleting template with active instances fails."""
        # Create an invoice and start workflow
        invoice = TestInvoice.objects.create(
            invoice_number="INV-001",
            vendor_name="Test Vendor",
            total_amount=1000.00,
            description="Test",
        )

        from core.approval.managers import ApprovalManager

        ApprovalManager.start_workflow(invoice)

        # Try to delete template
        url = reverse(
            "core:approval:workflow-template-detail", args=[self.template1.id]
        )
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("active workflow instance", response.data["error"])

    def test_get_workflow_template_stages(self):
        """Test GET /workflow-templates/{id}/stages/"""
        url = reverse(
            "core:approval:workflow-template-stages", args=[self.template1.id]
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["data"]["results"]
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["order_index"], 1)
        self.assertEqual(results[1]["order_index"], 2)


class StageTemplateAPITest(TestCase):
    """Test ApprovalWorkflowStageTemplate API endpoints."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create job role
        self.role = JobRole.objects.create(name="Approver")

        # Get content type
        self.invoice_ct = ContentType.objects.get_for_model(TestInvoice)

        # Create template
        self.template = ApprovalWorkflowTemplate.objects.create(
            code="TEST_STAGES",
            name="Test Stages Template",
            content_type=self.invoice_ct,
            is_active=True,
            version=1,
        )

        # Create stages
        self.stage1 = ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=self.template,
            order_index=1,
            name="Stage 1",
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY,
        )

        self.stage2 = ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=self.template,
            order_index=2,
            name="Stage 2",
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ALL,
            required_role=self.role,
        )

    def test_list_stage_templates(self):
        """Test GET /stage-templates/"""
        url = reverse("core:approval:stage-template-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["data"]["results"]
        self.assertEqual(len(results), 2)

    def test_filter_stage_templates_by_workflow(self):
        """Test filtering stages by workflow_template."""
        # Create another template with stages
        template2 = ApprovalWorkflowTemplate.objects.create(
            code="ANOTHER_TEMPLATE",
            name="Another Template",
            content_type=self.invoice_ct,
            is_active=True,
            version=1,
        )
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=template2,
            order_index=1,
            name="Other Stage",
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY,
        )

        url = reverse("core:approval:stage-template-list")
        response = self.client.get(url, {"workflow_template": self.template.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["data"]["results"]
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["name"], "Stage 1")

    def test_filter_stage_templates_by_policy(self):
        """Test filtering stages by decision_policy."""
        url = reverse("core:approval:stage-template-list")
        response = self.client.get(url, {"decision_policy": "ANY"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["data"]["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Stage 1")

    def test_filter_stage_templates_by_delegation(self):
        """Test filtering stages by allow_delegate."""
        self.stage1.allow_delegate = True
        self.stage1.save()

        url = reverse("core:approval:stage-template-list")
        response = self.client.get(url, {"allow_delegate": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["data"]["results"]
        self.assertEqual(len(results), 1)

    def test_create_stage_template(self):
        """Test POST /stage-templates/"""
        url = reverse("core:approval:stage-template-list")
        data = {
            "workflow_template": self.template.id,
            "order_index": 3,
            "name": "New Stage",
            "decision_policy": "QUORUM",
            "quorum_count": 2,
            "allow_reject": True,
            "allow_delegate": False,
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "New Stage")
        self.assertEqual(response.data["quorum_count"], 2)

    def test_create_stage_template_duplicate_order(self):
        """Test creating stage with duplicate order_index fails."""
        url = reverse("core:approval:stage-template-list")
        data = {
            "workflow_template": self.template.id,
            "order_index": 1,  # Already exists
            "name": "Duplicate Order",
            "decision_policy": "ANY",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Error message should be in response.data, not response.data['error']
        self.assertIn("order_index", str(response.data))

    def test_create_stage_template_quorum_validation(self):
        """Test QUORUM policy requires quorum_count."""
        url = reverse("core:approval:stage-template-list")
        data = {
            "workflow_template": self.template.id,
            "order_index": 3,
            "name": "Quorum Stage",
            "decision_policy": "QUORUM",
            # Missing quorum_count
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("quorum_count", response.data)

    def test_get_stage_template_detail(self):
        """Test GET /stage-templates/{id}/"""
        url = reverse("core:approval:stage-template-detail", args=[self.stage1.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Stage 1")
        self.assertEqual(response.data["order_index"], 1)

    def test_update_stage_template(self):
        """Test PUT /stage-templates/{id}/"""
        url = reverse("core:approval:stage-template-detail", args=[self.stage1.id])
        data = {
            "workflow_template": self.template.id,
            "order_index": 1,
            "name": "Updated Stage 1",
            "decision_policy": "ALL",
            "allow_reject": False,
            "allow_delegate": True,
            "sla_hours": 48,
        }

        response = self.client.put(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Stage 1")
        self.assertEqual(response.data["decision_policy"], "ALL")

    def test_partial_update_stage_template(self):
        """Test PATCH /stage-templates/{id}/"""
        url = reverse("core:approval:stage-template-detail", args=[self.stage1.id])
        data = {"sla_hours": 12}

        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["sla_hours"], 12)
        self.assertEqual(response.data["name"], "Stage 1")  # Unchanged

    def test_update_stage_template_order_conflict(self):
        """Test updating order_index to existing value fails."""
        url = reverse("core:approval:stage-template-detail", args=[self.stage1.id])
        data = {"order_index": 2}  # Already used by stage2

        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Error message should be in response.data, not response.data['error']
        self.assertIn("order_index", str(response.data))

    def test_delete_stage_template(self):
        """Test DELETE /stage-templates/{id}/"""
        url = reverse("core:approval:stage-template-detail", args=[self.stage2.id])
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("deleted successfully", response.data["message"])

        # Verify deleted
        self.assertFalse(
            ApprovalWorkflowStageTemplate.objects.filter(id=self.stage2.id).exists()
        )


class UtilityViewsAPITest(TestCase):
    """Test utility API endpoints."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create user
        self.user = User.objects.create_user(
            email="testuser@test.com",
            name="Test User",
            phone_number="1234567890",
            password="testpass123",
        )

        # Get content type
        self.invoice_ct = ContentType.objects.get_for_model(TestInvoice)

        # Create template
        self.template = ApprovalWorkflowTemplate.objects.create(
            code="TEST_UTIL",
            name="Test Utility",
            content_type=self.invoice_ct,
            is_active=True,
            version=1,
        )

        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=self.template,
            order_index=1,
            name="Test Stage",
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY,
        )

    def test_list_content_types(self):
        """Test GET /content-types/ - should only return content types with approval templates."""
        url = reverse("core:approval:content-types-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return 1 content type (TestInvoice) since only it has a template
        results = response.data["data"]["results"]
        self.assertEqual(len(results), 1)

        # Check structure
        ct_data = results[0]
        self.assertIn("id", ct_data)
        self.assertIn("app_label", ct_data)
        self.assertIn("model_name", ct_data)

        # Verify it's the TestInvoice content type
        self.assertEqual(ct_data["id"], self.invoice_ct.id)

    def test_list_content_types_only_linked_modules(self):
        """Test that content_types endpoint only returns modules linked to approval workflows."""
        # Initially has TEST_UTIL template for TestInvoice
        url = reverse("core:approval:content-types-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["data"]["results"]
        initial_count = len(results)

        # Create a template for TestPurchaseOrder
        po_ct = ContentType.objects.get_for_model(TestPurchaseOrder)
        ApprovalWorkflowTemplate.objects.create(
            code="TEST_PO",
            name="Test PO Template",
            content_type=po_ct,
            is_active=True,
            version=1,
        )

        # Now should return 2 content types
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["data"]["results"]
        self.assertEqual(len(results), initial_count + 1)

        # Verify both content types are present
        returned_ids = [ct["id"] for ct in results]
        self.assertIn(self.invoice_ct.id, returned_ids)
        self.assertIn(po_ct.id, returned_ids)


class EdgeCasesAPITest(TestCase):
    """Test edge cases and error handling."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.invoice_ct = ContentType.objects.get_for_model(TestInvoice)

    def test_get_nonexistent_template(self):
        """Test getting non-existent template returns 404."""
        url = reverse("core:approval:workflow-template-detail", args=[99999])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_nonexistent_stage(self):
        """Test getting non-existent stage returns 404."""
        url = reverse("core:approval:stage-template-detail", args=[99999])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_template_missing_required_fields(self):
        """Test creating template without required fields fails."""
        url = reverse("core:approval:workflow-template-list")
        data = {
            "name": "Incomplete Template"
            # Missing code and content_type
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("code", response.data)
        self.assertIn("content_type", response.data)

    def test_create_stage_missing_workflow_template(self):
        """Test creating stage without workflow_template fails."""
        url = reverse("core:approval:stage-template-list")
        data = {"order_index": 1, "name": "Orphan Stage", "decision_policy": "ANY"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_content_type(self):
        """Test creating template with invalid content_type fails."""
        url = reverse("core:approval:workflow-template-list")
        data = {
            "code": "INVALID_CT",
            "name": "Invalid CT Template",
            "content_type": 99999,  # Non-existent
            "is_active": True,
            "version": 1,
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
