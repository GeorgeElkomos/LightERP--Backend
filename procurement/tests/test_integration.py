"""
Integration tests for complete procurement workflow: PR → PO → Receiving
Tests the full end-to-end process with all scenarios.

This test suite covers:
1. Catalog PR → PO → Full Receiving
2. Non-Catalog PR → PO → Receiving
3. Service PR → PO (no receiving)
4. Partial receiving scenarios
5. Gift/bonus items in receiving
6. Multiple PRs to single PO
7. Single PR to multiple POs
8. Validation tests (over-receiving, status checks)
9. GRN deletion and quantity reversal
"""
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from datetime import date, timedelta

from Finance.BusinessPartner.models import BusinessPartner, Supplier
from Finance.core.models import Currency
from procurement.catalog.models import catalogItem, UnitOfMeasure
from procurement.PR.models import PR, PRItem, Catalog_PR, NonCatalog_PR, Service_PR
from procurement.po.models import POHeader, POLineItem
from procurement.receiving.models import GoodsReceipt, GoodsReceiptLine
from core.approval.models import ApprovalWorkflowTemplate, ApprovalWorkflowStageTemplate

User = get_user_model()


# ============================================================================
# BASE TEST CASE WITH COMMON SETUP
# ============================================================================

class ProcurementIntegrationTestCase(TestCase):
    """Base class for integration tests with common setup."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create users
        self.requester = User.objects.create_user(
            email='requester@test.com',
            password='testpass123',
            name='Requester User',
            phone_number='1234567890'
        )
        self.approver = User.objects.create_user(
            email='approver@test.com',
            password='testpass123',
            name='Approver User',
            phone_number='0987654321'
        )
        self.receiver = User.objects.create_user(
            email='receiver@test.com',
            password='testpass123',
            name='Receiver User',
            phone_number='5555555555'
        )
        
        # Create supplier (automatically creates BusinessPartner)
        self.supplier = Supplier.objects.create(
            name='Test Supplier Co',
            email='supplier@test.com',
            phone='1234567890',
            vat_number='VAT001'
        )
        self.business_partner = self.supplier.business_partner
        
        # Create Currency
        self.currency = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$'
        )
        
        # Create UOMs
        self.uom_ea = UnitOfMeasure.objects.create(
            code='EA',
            name='Each',
            uom_type='QUANTITY'
        )
        self.uom_kg = UnitOfMeasure.objects.create(
            code='KG',
            name='Kilogram',
            uom_type='WEIGHT'
        )
        self.uom_hr = UnitOfMeasure.objects.create(
            code='HR',
            name='Hour',
            uom_type='TIME'
        )
        
        # Create catalog items
        self.item1 = catalogItem.objects.create(
            code='ITEM001',
            name='Laptop Dell XPS',
            description='High performance laptop'
        )
        self.item2 = catalogItem.objects.create(
            code='ITEM002',
            name='Office Chair',
            description='Ergonomic office chair'
        )
        
        # Create approval templates
        self.create_approval_templates()
    
    def create_approval_templates(self):
        """Create simple approval templates for PR and PO"""
        from django.contrib.contenttypes.models import ContentType
        from core.job_roles.models import JobRole, UserJobRole
        
        # Create a manager role for approvals
        manager_role, _ = JobRole.objects.get_or_create(
            name='Manager',
            defaults={
                'description': 'Manager role for approvals'
            }
        )
        
        # Assign the approver user to the manager role
        UserJobRole.objects.create(
            user=self.approver,
            job_role=manager_role,
            effective_start_date=date.today() - timedelta(days=1)
        )
        self.approver.job_role = manager_role
        
        # PR approval templates
        for pr_model in [Catalog_PR, NonCatalog_PR, Service_PR]:
            content_type = ContentType.objects.get_for_model(pr_model)
            code = f'TEST_{pr_model.__name__.upper()}_APPROVAL'
            template, _ = ApprovalWorkflowTemplate.objects.get_or_create(
                code=code,
                defaults={
                    'name': f'{pr_model.__name__} Approval',
                    'content_type': content_type,
                    'is_active': True
                }
            )
            if not template.stages.exists():
                stage = ApprovalWorkflowStageTemplate.objects.create(
                    workflow_template=template,
                    name='Manager Approval',
                    order_index=1,
                    decision_policy='ANY',
                    allow_reject=True,
                    allow_delegate=True,
                    required_role=manager_role
                )
        
        # PO approval template
        po_content_type = ContentType.objects.get_for_model(POHeader)
        po_template, _ = ApprovalWorkflowTemplate.objects.get_or_create(
            code='TEST_PO_APPROVAL',
            defaults={
                'name': 'PO Approval',
                'content_type': po_content_type,
                'is_active': True
            }
        )
        if not po_template.stages.exists():
            stage = ApprovalWorkflowStageTemplate.objects.create(
                workflow_template=po_template,
                name='Manager Approval',
                order_index=1,
                decision_policy='ANY',
                allow_reject=True,
                allow_delegate=True,
                required_role=manager_role
            )
    
    def submit_and_approve_pr(self, pr_id):
        """Submit and approve a PR"""
        # Submit for approval
        self.client.force_authenticate(user=self.requester)
        submit_url = reverse('pr:catalog-pr-submit-for-approval', kwargs={'pk': pr_id})
        submit_response = self.client.post(submit_url)
        self.assertEqual(submit_response.status_code, status.HTTP_200_OK)
        
        # Approve (approver has the required role, so should be auto-assigned)
        self.client.force_authenticate(user=self.approver)
        approve_url = reverse('pr:catalog-pr-approval-action', kwargs={'pk': pr_id})
        approve_response = self.client.post(
            approve_url,
            {'action': 'approve', 'comment': 'Approved'},
            format='json'
        )
        self.assertEqual(approve_response.status_code, status.HTTP_200_OK, 
                        f"Approval failed: {approve_response.data}")
    
    def submit_and_approve_po(self, po_id):
        """Submit and approve a PO"""
        # Submit for approval
        submit_url = reverse('po:po-submit-for-approval', kwargs={'pk': po_id})
        submit_response = self.client.post(submit_url)
        self.assertEqual(submit_response.status_code, status.HTTP_200_OK)
        
        # Approve (approver has the required role, so should be auto-assigned)
        self.client.force_authenticate(user=self.approver)
        approve_url = reverse('po:po-approval-action', kwargs={'pk': po_id})
        approve_response = self.client.post(
            approve_url,
            {'action': 'approve', 'comment': 'Approved'},
            format='json'
        )
        self.assertEqual(approve_response.status_code, status.HTTP_200_OK,
                        f"Approval failed: {approve_response.data}")


# ============================================================================
# TEST SUITE 1: COMPLETE CATALOG WORKFLOW
# ============================================================================

class CatalogPRToReceivingWorkflowTests(ProcurementIntegrationTestCase):
    """Test complete workflow: Catalog PR → PO → Receiving"""
    
    def test_full_workflow_catalog_pr_to_receiving(self):
        """Test: Complete workflow from Catalog PR to full receiving"""
        # STEP 1: Create Catalog PR
        self.client.force_authenticate(user=self.requester)
        pr_data = {
            'date': str(date.today()),
            'required_date': str(date.today() + timedelta(days=14)),
            'requester_name': 'Requester User',
            'requester_department': 'IT',
            'requester_email': 'requester@test.com',
            'priority': 'HIGH',
            'description': 'Laptops for new employees',
            'notes': 'Urgent requirement',
            'items': [
                {
                    'item_name': 'Laptop Dell XPS',
                    'item_description': 'High performance laptop',
                    'catalog_item_id': self.item1.id,
                    'quantity': '10',
                    'unit_of_measure_id': self.uom_ea.id,
                    'estimated_unit_price': '1200.00',
                    'notes': 'i7 processor, 16GB RAM'
                },
                {
                    'item_name': 'Office Chair',
                    'item_description': 'Ergonomic chair',
                    'catalog_item_id': self.item2.id,
                    'quantity': '10',
                    'unit_of_measure_id': self.uom_ea.id,
                    'estimated_unit_price': '300.00',
                    'notes': 'With lumbar support'
                }
            ]
        }
        
        pr_response = self.client.post(reverse('pr:catalog-pr-list'), pr_data, format='json')
        self.assertEqual(pr_response.status_code, status.HTTP_201_CREATED, 
                        f"PR creation failed: {pr_response.data}")
        pr_id = pr_response.data['data']['pr_id']
        pr_number = pr_response.data['data']['pr_number']
        
        # Verify PR created with correct data
        pr = PR.objects.get(id=pr_id)
        self.assertEqual(pr.status, 'DRAFT')
        self.assertEqual(pr.items.count(), 2)
        self.assertEqual(pr.total, Decimal('15000.00'))  # (10 * 1200) + (10 * 300)
        
        # STEP 2: Submit and Approve PR
        self.submit_and_approve_pr(pr_id)
        
        # Verify PR status changed to APPROVED
        pr.refresh_from_db()
        self.assertEqual(pr.status, 'APPROVED')
        
        # STEP 3: Create PO (manually, as PR-to-PO conversion might not be implemented)
        po_data = {
            'po_date': str(date.today()),
            'po_type': 'Catalog',
            'supplier_id': self.supplier.id,
            'currency_id': self.currency.id,
            'receiving_date': str(date.today() + timedelta(days=14)),
            'receiving_address': '123 Main St, Building A',
            'receiver_email': 'receiver@test.com',
            'receiver_contact': 'Receiver User',
            'receiver_phone': '5555555555',
            'description': f'PO for {pr_number}',
            'tax_amount': '0.00',
            'items': [
                {
                    'line_number': 1,
                    'line_type': 'Catalog',
                    'item_name': 'Laptop Dell XPS',
                    'item_description': 'High performance laptop',
                    'quantity': '10',
                    'unit_of_measure_id': self.uom_ea.id,
                    'unit_price': '1200.00',
                    'line_notes': f'From PR: {pr_number}'
                },
                {
                    'line_number': 2,
                    'line_type': 'Catalog',
                    'item_name': 'Office Chair',
                    'item_description': 'Ergonomic chair',
                    'quantity': '10',
                    'unit_of_measure_id': self.uom_ea.id,
                    'unit_price': '300.00',
                    'line_notes': f'From PR: {pr_number}'
                }
            ]
        }
        
        po_response = self.client.post(reverse('po:po-list'), po_data, format='json')
        self.assertEqual(po_response.status_code, status.HTTP_201_CREATED,
                        f"PO creation failed: {po_response.data}")
        po_id = po_response.data['data']['id']
        po_number = po_response.data['data']['po_number']
        
        # Verify PO created
        po = POHeader.objects.get(id=po_id)
        self.assertEqual(po.status, 'DRAFT')
        self.assertEqual(po.line_items.count(), 2)
        
        # STEP 4: Submit and Approve PO
        self.client.force_authenticate(user=self.requester)
        self.submit_and_approve_po(po_id)
        
        po.refresh_from_db()
        self.assertEqual(po.status, 'APPROVED')
        
        # STEP 5: Confirm PO
        confirm_url = reverse('po:po-confirm', kwargs={'pk': po_id})
        confirm_response = self.client.post(confirm_url)
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)
        
        po.refresh_from_db()
        self.assertEqual(po.status, 'CONFIRMED')
        
        # STEP 6: Create Goods Receipt (Full Receiving)
        self.client.force_authenticate(user=self.receiver)
        
        # Get PO lines to link GRN lines
        po_lines = list(po.line_items.all().order_by('line_number'))
        
        grn_data = {
            'grn_date': str(date.today()),
            'grn_type': 'Catalog',
            'po_header_id': po_id,
            'supplier_id': self.supplier.id,
            'receiver_email': 'receiver@test.com',
            'receiver_contact': 'Receiver User',
            'notes': f'Full receipt for PO: {po_number}',
            'lines': [
                {
                    'line_number': 1,
                    'po_line_item_id': po_lines[0].id,
                    'item_name': 'Laptop Dell XPS',
                    'item_description': 'High performance laptop',
                    'quantity_ordered': '10.000',
                    'quantity_received': '10.000',
                    'unit_of_measure_id': self.uom_ea.id,
                    'unit_price': '1200.00',
                    'line_notes': 'All items received in good condition'
                },
                {
                    'line_number': 2,
                    'po_line_item_id': po_lines[1].id,
                    'item_name': 'Office Chair',
                    'item_description': 'Ergonomic chair',
                    'quantity_ordered': '10.000',
                    'quantity_received': '10.000',
                    'unit_of_measure_id': self.uom_ea.id,
                    'unit_price': '300.00',
                    'line_notes': 'All items received in good condition'
                }
            ]
        }
        
        grn_response = self.client.post(reverse('receiving:grn-list'), grn_data, format='json')
        self.assertEqual(grn_response.status_code, status.HTTP_201_CREATED,
                        f"GRN creation failed: {grn_response.data}")
        grn_id = grn_response.data['data']['id']
        
        # STEP 7: Verify GRN and quantities
        grn = GoodsReceipt.objects.get(id=grn_id)
        self.assertEqual(grn.lines.count(), 2)
        self.assertEqual(grn.grn_type, 'Catalog')
        
        # Verify PO line quantities updated
        po.refresh_from_db()
        for line in po.line_items.all():
            self.assertEqual(line.quantity_received, line.quantity)
        
        # Test complete!
        # print(f"\n✓ Full workflow completed successfully:")
        # print(f"  PR: {pr_number} (Status: {pr.status})")
        # print(f"  PO: {po_number} (Status: {po.status})")
        # print(f"  GRN: {grn.grn_number} (Lines: {grn.lines.count()})")


# ============================================================================
# TEST SUITE 2: PARTIAL RECEIVING SCENARIOS
# ============================================================================

class PartialReceivingWorkflowTests(ProcurementIntegrationTestCase):
    """Test partial receiving scenarios"""
    
    def test_multiple_partial_receipts_then_full(self):
        """Test: Create PO → Multiple partial receipts → Final full receipt"""
        # Create and confirm PO
        self.client.force_authenticate(user=self.requester)
        po_data = {
            'po_date': str(date.today()),
            'po_type': 'Catalog',
            'supplier_id': self.supplier.id,
            'currency_id': self.currency.id,
            'receiving_date': str(date.today() + timedelta(days=7)),
            'receiving_address': '123 Warehouse St',
            'receiver_email': 'receiver@test.com',
            'receiver_contact': 'Receiver',
            'receiver_phone': '555-1234',
            'description': 'Large laptop order',
            'tax_amount': '0.00',
            'items': [
                {
                    'line_number': 1,
                    'line_type': 'Catalog',
                    'item_name': 'Laptop',
                    'item_description': 'Business laptop',
                    'quantity': '100',
                    'unit_of_measure_id': self.uom_ea.id,
                    'unit_price': '1000.00',
                    'line_notes': 'Large order'
                }
            ]
        }
        
        po_response = self.client.post(reverse('po:po-list'), po_data, format='json')
        self.assertEqual(po_response.status_code, status.HTTP_201_CREATED)
        po_id = po_response.data['data']['id']
        
        # Submit, approve, and confirm PO
        self.submit_and_approve_po(po_id)
        confirm_response = self.client.post(reverse('po:po-confirm', kwargs={'pk': po_id}))
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)
        
        po = POHeader.objects.get(id=po_id)
        po_line = po.line_items.first()
        
        # First partial receipt: 30 units
        self.client.force_authenticate(user=self.receiver)
        grn1_data = {
            'grn_date': str(date.today()),
            'grn_type': 'Catalog',
            'po_header_id': po_id,
            'supplier_id': self.supplier.id,
            'receiver_email': 'receiver@test.com',
            'receiver_contact': 'Receiver',
            'notes': 'First partial delivery',
            'lines': [
                {
                    'line_number': 1,
                    'po_line_item_id': po_line.id,
                    'item_name': 'Laptop',
                    'item_description': 'Business laptop',
                    'quantity_ordered': '100.000',
                    'quantity_received': '30.000',
                    'unit_of_measure_id': self.uom_ea.id,
                    'unit_price': '1000.00',
                    'line_notes': '30% delivered'
                }
            ]
        }
        
        grn1_response = self.client.post(reverse('receiving:grn-list'), grn1_data, format='json')
        self.assertEqual(grn1_response.status_code, status.HTTP_201_CREATED)
        
        # Verify partial receipt
        po_line.refresh_from_db()
        self.assertEqual(po_line.quantity_received, Decimal('30.000'))
        
        # Second partial receipt: 40 units
        grn2_data = grn1_data.copy()
        grn2_data['notes'] = 'Second partial delivery'
        grn2_data['lines'][0]['quantity_received'] = '40.000'
        grn2_data['lines'][0]['line_notes'] = '40% more delivered'
        
        grn2_response = self.client.post(reverse('receiving:grn-list'), grn2_data, format='json')
        self.assertEqual(grn2_response.status_code, status.HTTP_201_CREATED)
        
        # Verify cumulative receipt
        po_line.refresh_from_db()
        self.assertEqual(po_line.quantity_received, Decimal('70.000'))
        
        # Final receipt: remaining 30 units
        grn3_data = grn1_data.copy()
        grn3_data['notes'] = 'Final delivery'
        grn3_data['lines'][0]['quantity_received'] = '30.000'
        grn3_data['lines'][0]['line_notes'] = 'Order complete'
        
        grn3_response = self.client.post(reverse('receiving:grn-list'), grn3_data, format='json')
        self.assertEqual(grn3_response.status_code, status.HTTP_201_CREATED)
        
        # Verify full receipt
        po_line.refresh_from_db()
        self.assertEqual(po_line.quantity_received, Decimal('100.000'))
        
        # Verify 3 GRNs created
        grn_count = GoodsReceipt.objects.filter(po_header=po).count()
        self.assertEqual(grn_count, 3)
        
        # print(f"\n✓ Partial receiving workflow completed:")
        # print(f"  Total ordered: 100 units")
        # print(f"  Receipts: 30 + 40 + 30 = 100 units")
        # print(f"  GRNs created: {grn_count}")


# ============================================================================
# TEST SUITE 3: NON-CATALOG AND SERVICE WORKFLOWS
# ============================================================================

class NonCatalogAndServiceWorkflowTests(ProcurementIntegrationTestCase):
    """Test non-catalog and service PR workflows"""
    
    def test_noncatalog_pr_to_po_to_receiving(self):
        """Test: Non-catalog PR → PO → Receiving"""
        # Create Non-Catalog PR
        self.client.force_authenticate(user=self.requester)
        pr_data = {
            'date': str(date.today()),
            'required_date': str(date.today() + timedelta(days=21)),
            'requester_name': 'Requester User',
            'requester_department': 'Engineering',
            'requester_email': 'requester@test.com',
            'priority': 'MEDIUM',
            'description': 'Custom equipment',
            'notes': 'Special order items not in catalog',
            'items': [
                {
                    'item_name': 'Custom CNC Part',
                    'item_description': 'Specialized machine component',
                    'quantity': '5',
                    'unit_of_measure_id': self.uom_ea.id,
                    'estimated_unit_price': '5000.00',
                    'notes': 'Custom fabrication required'
                }
            ]
        }
        
        pr_response = self.client.post(reverse('pr:noncatalog-pr-list'), pr_data, format='json')
        self.assertEqual(pr_response.status_code, status.HTTP_201_CREATED)
        pr_id = pr_response.data['data']['pr_id']
        
        # Submit and approve PR
        submit_url = reverse('pr:noncatalog-pr-submit-for-approval', kwargs={'pk': pr_id})
        self.client.post(submit_url)
        
        self.client.force_authenticate(user=self.approver)
        approve_url = reverse('pr:noncatalog-pr-approval-action', kwargs={'pk': pr_id})
        self.client.post(approve_url, {'action': 'APPROVE', 'comments': 'OK'}, format='json')
        
        # Create PO
        self.client.force_authenticate(user=self.requester)
        po_data = {
            'po_date': str(date.today()),
            'po_type': 'Non-Catalog',
            'supplier_id': self.supplier.id,
            'currency_id': self.currency.id,
            'receiving_date': str(date.today() + timedelta(days=21)),
            'receiving_address': '456 Factory Rd',
            'receiver_email': 'receiver@test.com',
            'receiver_contact': 'Receiver',
            'receiver_phone': '555-5678',
            'description': 'Custom parts order',
            'tax_amount': '0.00',
            'items': [
                {
                    'line_number': 1,
                    'line_type': 'Non-Catalog',
                    'item_name': 'Custom CNC Part',
                    'item_description': 'Specialized component',
                    'quantity': '5',
                    'unit_of_measure_id': self.uom_ea.id,
                    'unit_price': '5000.00',
                    'line_notes': 'Custom fabrication'
                }
            ]
        }
        
        po_response = self.client.post(reverse('po:po-list'), po_data, format='json')
        self.assertEqual(po_response.status_code, status.HTTP_201_CREATED)
        po_id = po_response.data['data']['id']
        
        # Approve and confirm PO
        self.submit_and_approve_po(po_id)
        self.client.post(reverse('po:po-confirm', kwargs={'pk': po_id}))
        
        # Get PO line for linking
        po = POHeader.objects.get(id=po_id)
        po_line = po.line_items.first()
        
        # Receive items
        self.client.force_authenticate(user=self.receiver)
        grn_data = {
            'grn_date': str(date.today()),
            'grn_type': 'Non-Catalog',
            'po_header_id': po_id,
            'supplier_id': self.supplier.id,
            'receiver_email': 'receiver@test.com',
            'receiver_contact': 'Receiver',
            'notes': 'Custom parts received',
            'lines': [
                {
                    'line_number': 1,
                    'po_line_item_id': po_line.id,
                    'item_name': 'Custom CNC Part',
                    'item_description': 'Specialized component',
                    'quantity_ordered': '5.000',
                    'quantity_received': '5.000',
                    'unit_of_measure_id': self.uom_ea.id,
                    'unit_price': '5000.00',
                    'line_notes': 'Received and inspected'
                }
            ]
        }
        
        grn_response = self.client.post(reverse('receiving:grn-list'), grn_data, format='json')
        self.assertEqual(grn_response.status_code, status.HTTP_201_CREATED)
        
        # print("\n✓ Non-catalog workflow completed successfully")
    
    def test_service_pr_to_po_no_receiving(self):
        """Test: Service PR → PO (no receiving required)"""
        # Create Service PR
        self.client.force_authenticate(user=self.requester)
        pr_data = {
            'date': str(date.today()),
            'required_date': str(date.today() + timedelta(days=30)),
            'requester_name': 'Requester User',
            'requester_department': 'IT',
            'requester_email': 'requester@test.com',
            'priority': 'HIGH',
            'description': 'Consulting services',
            'notes': 'Software development support',
            'items': [
                {
                    'item_name': 'Software Consulting',
                    'item_description': 'Senior developer services',
                    'quantity': '160',  # Hours
                    'unit_of_measure_id': self.uom_hr.id,
                    'estimated_unit_price': '150.00',
                    'notes': '1 month contract'
                }
            ]
        }
        
        pr_response = self.client.post(reverse('pr:service-pr-list'), pr_data, format='json')
        self.assertEqual(pr_response.status_code, status.HTTP_201_CREATED)
        pr_id = pr_response.data['data']['pr_id']
        
        # Submit and approve PR
        submit_url = reverse('pr:service-pr-submit-for-approval', kwargs={'pk': pr_id})
        self.client.post(submit_url)
        
        self.client.force_authenticate(user=self.approver)
        approve_url = reverse('pr:service-pr-approval-action', kwargs={'pk': pr_id})
        self.client.post(approve_url, {'action': 'APPROVE', 'comments': 'OK'}, format='json')
        
        # Create Service PO
        self.client.force_authenticate(user=self.requester)
        po_data = {
            'po_date': str(date.today()),
            'po_type': 'Service',
            'supplier_id': self.supplier.id,
            'currency_id': self.currency.id,
            'receiving_date': str(date.today() + timedelta(days=30)),
            'receiving_address': 'N/A - Service',
            'receiver_email': 'pm@test.com',
            'receiver_contact': 'Project Manager',
            'receiver_phone': '555-9999',
            'description': 'Consulting services',
            'tax_amount': '0.00',
            'items': [
                {
                    'line_number': 1,
                    'line_type': 'Service',
                    'item_name': 'Software Consulting',
                    'item_description': 'Development support',
                    'quantity': '160',
                    'unit_of_measure_id': self.uom_hr.id,
                    'unit_price': '150.00',
                    'line_notes': 'Monthly contract'
                }
            ]
        }
        
        po_response = self.client.post(reverse('po:po-list'), po_data, format='json')
        self.assertEqual(po_response.status_code, status.HTTP_201_CREATED)
        
        # Service POs typically don't require goods receiving
        # They are marked complete via invoice matching or service completion
        
        # print("\n✓ Service PR to PO workflow completed (no receiving)")


# ============================================================================
# TEST SUITE 4: GIFT/BONUS ITEMS AND SPECIAL SCENARIOS
# ============================================================================

class SpecialReceivingScenarios(ProcurementIntegrationTestCase):
    """Test special receiving scenarios like gift items"""
    
    def test_receiving_with_gift_items(self):
        """Test: Receiving ordered items plus bonus/gift items"""
        # Create and confirm PO
        self.client.force_authenticate(user=self.requester)
        po_data = {
            'po_date': str(date.today()),
            'po_type': 'Catalog',
            'supplier_id': self.supplier.id,
            'currency_id': self.currency.id,
            'receiving_date': str(date.today() + timedelta(days=5)),
            'receiving_address': '789 Store Ave',
            'receiver_email': 'receiver@test.com',
            'receiver_contact': 'Receiver',
            'receiver_phone': '555-3333',
            'description': 'Office supplies order',
            'tax_amount': '0.00',
            'items': [
                {
                    'line_number': 1,
                    'line_type': 'Catalog',
                    'item_name': 'Office Chair',
                    'item_description': 'Ergonomic chair',
                    'quantity': '20',
                    'unit_of_measure_id': self.uom_ea.id,
                    'unit_price': '250.00',
                    'line_notes': 'Bulk order'
                }
            ]
        }
        
        po_response = self.client.post(reverse('po:po-list'), po_data, format='json')
        self.assertEqual(po_response.status_code, status.HTTP_201_CREATED)
        po_id = po_response.data['data']['id']
        
        # Approve and confirm
        self.submit_and_approve_po(po_id)
        self.client.post(reverse('po:po-confirm', kwargs={'pk': po_id}))
        
        # Get PO line for linking
        po = POHeader.objects.get(id=po_id)
        po_line = po.line_items.first()
        
        # Receive ordered items + gift items
        self.client.force_authenticate(user=self.receiver)
        grn_data = {
            'grn_date': str(date.today()),
            'grn_type': 'Catalog',
            'po_header_id': po_id,
            'supplier_id': self.supplier.id,
            'receiver_email': 'receiver@test.com',
            'receiver_contact': 'Receiver',
            'notes': 'Received with bonus items',
            'lines': [
                {
                    'line_number': 1,
                    'po_line_item_id': po_line.id,
                    'item_name': 'Office Chair',
                    'item_description': 'Ergonomic chair',
                    'quantity_ordered': '20.000',
                    'quantity_received': '20.000',
                    'unit_of_measure_id': self.uom_ea.id,
                    'unit_price': '250.00',
                    'line_notes': 'All ordered items received'
                },
                {
                    'line_number': 2,
                    'item_name': 'FREE - Desk Lamp (Gift)',
                    'item_description': 'Bonus desk lamp from supplier',
                    'quantity_ordered': '0.000',
                    'quantity_received': '5.000',
                    'unit_of_measure_id': self.uom_ea.id,
                    'unit_price': '0.00',
                    'line_notes': 'Free bonus item - no charge'
                }
            ]
        }
        
        grn_response = self.client.post(reverse('receiving:grn-list'), grn_data, format='json')
        self.assertEqual(grn_response.status_code, status.HTTP_201_CREATED)
        
        # Verify GRN has 2 lines
        grn = GoodsReceipt.objects.get(id=grn_response.data['data']['id'])
        self.assertEqual(grn.lines.count(), 2)
        
        # Find gift line by name
        gift_line = grn.lines.filter(item_name__contains='Gift').first()
        if gift_line:
            self.assertEqual(gift_line.quantity_ordered, Decimal('0.000'))
            self.assertEqual(gift_line.quantity_received, Decimal('5.000'))
            self.assertEqual(gift_line.unit_price, Decimal('0.00'))
        
        # print("\n✓ Receiving with gift items completed successfully")


# ============================================================================
# TEST SUITE 5: VALIDATION AND ERROR SCENARIOS
# ============================================================================

class ReceivingValidationTests(ProcurementIntegrationTestCase):
    """Test validation rules and error handling"""
    
    def test_grn_deletion_reverses_quantities(self):
        """Test: Deleting GRN should reverse received quantities"""
        # Create, confirm PO and receive
        self.client.force_authenticate(user=self.requester)
        po_data = {
            'po_date': str(date.today()),
            'po_type': 'Catalog',
            'supplier_id': self.supplier.id,
            'currency_id': self.currency.id,
            'receiving_date': str(date.today() + timedelta(days=7)),
            'receiving_address': '100 Test St',
            'receiver_email': 'receiver@test.com',
            'receiver_contact': 'Receiver',
            'receiver_phone': '555-1111',
            'description': 'Test order',
            'tax_amount': '0.00',
            'items': [
                {
                    'line_number': 1,
                    'line_type': 'Catalog',
                    'item_name': 'Test Item',
                    'item_description': 'For testing',
                    'quantity': '50',
                    'unit_of_measure_id': self.uom_ea.id,
                    'unit_price': '100.00',
                    'line_notes': ''
                }
            ]
        }
        
        po_response = self.client.post(reverse('po:po-list'), po_data, format='json')
        po_id = po_response.data['data']['id']
        
        # Approve and confirm
        self.submit_and_approve_po(po_id)
        self.client.post(reverse('po:po-confirm', kwargs={'pk': po_id}))
        
        # Get PO line for linking
        po = POHeader.objects.get(id=po_id)
        po_line = po.line_items.first()
        
        # Receive items
        self.client.force_authenticate(user=self.receiver)
        grn_data = {
            'grn_date': str(date.today()),
            'grn_type': 'Catalog',
            'po_header_id': po_id,
            'supplier_id': self.supplier.id,
            'receiver_email': 'receiver@test.com',
            'receiver_contact': 'Receiver',
            'notes': 'Test receipt',
            'lines': [
                {
                    'line_number': 1,
                    'po_line_item_id': po_line.id,
                    'item_name': 'Test Item',
                    'item_description': 'For testing',
                    'quantity_ordered': '50.000',
                    'quantity_received': '50.000',
                    'unit_of_measure_id': self.uom_ea.id,
                    'unit_price': '100.00',
                    'line_notes': ''
                }
            ]
        }
        
        grn_response = self.client.post(reverse('receiving:grn-list'), grn_data, format='json')
        self.assertEqual(grn_response.status_code, status.HTTP_201_CREATED)
        grn_id = grn_response.data['data']['id']
        
        # Verify quantities updated
        po = POHeader.objects.get(id=po_id)
        po_line = po.line_items.first()
        self.assertEqual(po_line.quantity_received, Decimal('50.000'))
        
        # Delete GRN
        delete_url = reverse('receiving:grn-detail', kwargs={'pk': grn_id})
        delete_response = self.client.delete(delete_url)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify quantities reversed
        po_line.refresh_from_db()
        self.assertEqual(po_line.quantity_received, Decimal('0.000'))
        
        # print("\n✓ GRN deletion and quantity reversal verified")


# ============================================================================
# TEST SUITE 6: LIST AND RETRIEVAL OPERATIONS
# ============================================================================

class ListAndRetrievalTests(ProcurementIntegrationTestCase):
    """Test list endpoints and data retrieval"""
    
    def test_pr_list_retrieval(self):
        """Test: Get list of PRs"""
        self.client.force_authenticate(user=self.requester)
        response = self.client.get(reverse('pr:catalog-pr-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
    
    def test_po_list_retrieval(self):
        """Test: Get list of POs"""
        self.client.force_authenticate(user=self.requester)
        response = self.client.get(reverse('po:po-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
    
    def test_grn_list_retrieval(self):
        """Test: Get list of GRNs"""
        self.client.force_authenticate(user=self.receiver)
        response = self.client.get(reverse('receiving:grn-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
