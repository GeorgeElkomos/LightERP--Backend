"""
Integration tests for complete procurement workflow: PR → PO → Receiving
Tests the full end-to-end process with all scenarios.
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from Finance.BusinessPartner.models import BusinessPartner, Supplier
from procurement.catalog.models import catalogItem, UnitOfMeasure
from procurement.PR.models import PRHeader, PRLineItem
from procurement.po.models import POHeader, POLineItem
from procurement.receiving.models import GoodsReceipt, GoodsReceiptLine
from core.user_accounts.models import UserType

User = get_user_model()


class ProcurementIntegrationTestCase(TestCase):
    """Base class for integration tests with common setup."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create user type
        self.user_type = UserType.objects.create(
            type_name='employee',
            description='Regular employee'
        )
        
        # Create users
        self.requester = User.objects.create_user(
            email='requester@test.com',
            password='testpass123',
            name='Requester User',
            phone_number='1234567890',
            user_type=self.user_type
        )
        self.approver = User.objects.create_user(
            email='approver@test.com',
            password='testpass123',
            name='Approver User',
            phone_number='0987654321',
            user_type=self.user_type
        )
        self.receiver = User.objects.create_user(
            email='receiver@test.com',
            password='testpass123',
            name='Receiver User',
            phone_number='5555555555',
            user_type=self.user_type
        )
        
        # Create business partner and supplier
        self.business_partner = BusinessPartner.objects.create(
            name='Test Supplier Co',
            code='SUP001',
            bp_type='SUPPLIER'
        )
        self.supplier = Supplier.objects.create(
            business_partner=self.business_partner,
            supplier_code='SUP001',
            payment_terms='Net 30',
            credit_limit=Decimal('100000.00')
        )
        
        # Create UOM
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
        
        # Create catalog items
        self.item1 = catalogItem.objects.create(
            code='ITEM001',
            name='Test Item 1',
            description='Test Description 1'
        )
        self.item2 = catalogItem.objects.create(
            code='ITEM002',
            name='Test Item 2',
            description='Test Description 2'
        )


class FullProcurementWorkflowTests(ProcurementIntegrationTestCase):
    """Test complete procurement workflow from PR to PO to Receiving."""
    
    def test_complete_workflow_catalog_items_full_receipt(self):
        """Test: PR (catalog) → PO → Full Receiving."""
        # Step 1: Create PR with catalog items
        self.client.force_authenticate(user=self.requester)
        pr_data = {
            'pr_type': 'CATALOG',
            'justification': 'Need items for project',
            'requested_by': self.requester.id,
            'lines': [
                {
                    'line_number': 1,
                    'catalog_item_id': self.item1.id,
                    'quantity': '10.000',
                    'unit_of_measure_id': self.uom_ea.id,
                    'estimated_unit_price': '100.00'
                },
                {
                    'line_number': 2,
                    'catalog_item_id': self.item2.id,
                    'quantity': '5.000',
                    'unit_of_measure_id': self.uom_kg,
                    'estimated_unit_price': '50.00'
                }
            ]
        }
        pr_response = self.client.post('/procurement/pr/', pr_data, format='json')
        self.assertEqual(pr_response.status_code, status.HTTP_201_CREATED)
        pr_id = pr_response.data['id']
        
        # Step 2: Submit PR
        submit_response = self.client.post(f'/procurement/pr/{pr_id}/submit/')
        self.assertEqual(submit_response.status_code, status.HTTP_200_OK)
        
        # Step 3: Approve PR
        self.client.force_authenticate(user=self.approver)
        approve_response = self.client.post(
            f'/procurement/pr/{pr_id}/approve/',
            {'approver_comments': 'Approved for purchase'}
        )
        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        
        # Step 4: Convert PR to PO
        convert_response = self.client.post(
            f'/procurement/pr/{pr_id}/convert-to-po/',
            {'supplier_id': self.business_partner.id}
        )
        self.assertEqual(convert_response.status_code, status.HTTP_201_CREATED)
        po_id = convert_response.data['id']
        
        # Verify PO created correctly
        po = POHeader.objects.get(id=po_id)
        self.assertEqual(po.po_lines.count(), 2)
        self.assertEqual(po.status, 'DRAFT')
        
        # Step 5: Submit PO
        submit_po_response = self.client.post(f'/procurement/po/{po_id}/submit/')
        self.assertEqual(submit_po_response.status_code, status.HTTP_200_OK)
        
        # Step 6: Approve PO
        approve_po_response = self.client.post(f'/procurement/po/{po_id}/approve/')
        self.assertEqual(approve_po_response.status_code, status.HTTP_200_OK)
        
        # Step 7: Confirm PO
        confirm_po_response = self.client.post(f'/procurement/po/{po_id}/confirm/')
        self.assertEqual(confirm_po_response.status_code, status.HTTP_200_OK)
        
        po.refresh_from_db()
        self.assertEqual(po.status, 'CONFIRMED')
        
        # Step 8: Receive full quantity
        self.client.force_authenticate(user=self.receiver)
        grn_data = {
            'po_header_id': po_id,
            'receipt_date': '2025-12-23',
            'grn_type': 'STANDARD',
            'received_by': self.receiver.id,
            'notes': 'Full delivery received',
            'lines_from_po': [
                {'po_line_item_id': po.po_lines.first().id},
                {'po_line_item_id': po.po_lines.last().id}
            ]
        }
        grn_response = self.client.post('/procurement/receiving/', grn_data, format='json')
        self.assertEqual(grn_response.status_code, status.HTTP_201_CREATED)
        
        # Verify GRN created
        grn_id = grn_response.data['id']
        grn = GoodsReceipt.objects.get(id=grn_id)
        self.assertEqual(grn.grn_lines.count(), 2)
        
        # Verify PO line quantities updated
        for po_line in po.po_lines.all():
            po_line.refresh_from_db()
            self.assertEqual(po_line.quantity_received, po_line.quantity_ordered)
            self.assertEqual(po_line.get_receiving_percentage(), 100.0)
        
        # Verify PO status changed to RECEIVED
        po.refresh_from_db()
        self.assertEqual(po.status, 'RECEIVED')
    
    def test_complete_workflow_partial_receipts(self):
        """Test: PR → PO → Multiple Partial Receipts → Full Receipt."""
        # Step 1: Create and approve PR
        self.client.force_authenticate(user=self.requester)
        pr_data = {
            'pr_type': 'CATALOG',
            'justification': 'Large order for project',
            'requested_by': self.requester.id,
            'lines': [
                {
                    'line_number': 1,
                    'catalog_item_id': self.item1.id,
                    'quantity': '100.000',
                    'unit_of_measure_id': self.uom_ea.id,
                    'estimated_unit_price': '100.00'
                }
            ]
        }
        pr_response = self.client.post('/procurement/pr/', pr_data, format='json')
        pr_id = pr_response.data['id']
        
        self.client.post(f'/procurement/pr/{pr_id}/submit/')
        self.client.force_authenticate(user=self.approver)
        self.client.post(f'/procurement/pr/{pr_id}/approve/')
        
        # Step 2: Convert to PO and confirm
        convert_response = self.client.post(
            f'/procurement/pr/{pr_id}/convert-to-po/',
            {'supplier_id': self.business_partner.id}
        )
        po_id = convert_response.data['id']
        
        self.client.post(f'/procurement/po/{po_id}/submit/')
        self.client.post(f'/procurement/po/{po_id}/approve/')
        self.client.post(f'/procurement/po/{po_id}/confirm/')
        
        po = POHeader.objects.get(id=po_id)
        po_line = po.po_lines.first()
        
        # Step 3: First partial receipt - 30 units
        self.client.force_authenticate(user=self.receiver)
        grn_data1 = {
            'po_header_id': po_id,
            'receipt_date': '2025-12-20',
            'grn_type': 'STANDARD',
            'received_by': self.receiver.id,
            'notes': 'First delivery',
            'lines_from_po': [
                {
                    'po_line_item_id': po_line.id,
                    'quantity_to_receive': '30.000'
                }
            ]
        }
        grn1_response = self.client.post('/procurement/receiving/', grn_data1, format='json')
        self.assertEqual(grn1_response.status_code, status.HTTP_201_CREATED)
        
        # Verify partial receipt
        po_line.refresh_from_db()
        self.assertEqual(po_line.quantity_received, Decimal('30.000'))
        self.assertEqual(po_line.get_receiving_percentage(), 30.0)
        
        po.refresh_from_db()
        self.assertEqual(po.status, 'PARTIALLY_RECEIVED')
        
        # Step 4: Second partial receipt - 40 units
        grn_data2 = {
            'po_header_id': po_id,
            'receipt_date': '2025-12-22',
            'grn_type': 'STANDARD',
            'received_by': self.receiver.id,
            'notes': 'Second delivery',
            'lines_from_po': [
                {
                    'po_line_item_id': po_line.id,
                    'quantity_to_receive': '40.000'
                }
            ]
        }
        grn2_response = self.client.post('/procurement/receiving/', grn_data2, format='json')
        self.assertEqual(grn2_response.status_code, status.HTTP_201_CREATED)
        
        # Verify second partial receipt
        po_line.refresh_from_db()
        self.assertEqual(po_line.quantity_received, Decimal('70.000'))
        self.assertEqual(po_line.get_receiving_percentage(), 70.0)
        
        po.refresh_from_db()
        self.assertEqual(po.status, 'PARTIALLY_RECEIVED')
        
        # Step 5: Final receipt - remaining 30 units
        grn_data3 = {
            'po_header_id': po_id,
            'receipt_date': '2025-12-23',
            'grn_type': 'STANDARD',
            'received_by': self.receiver.id,
            'notes': 'Final delivery',
            'lines_from_po': [
                {
                    'po_line_item_id': po_line.id,
                    'quantity_to_receive': '30.000'
                }
            ]
        }
        grn3_response = self.client.post('/procurement/receiving/', grn_data3, format='json')
        self.assertEqual(grn3_response.status_code, status.HTTP_201_CREATED)
        
        # Verify full receipt
        po_line.refresh_from_db()
        self.assertEqual(po_line.quantity_received, Decimal('100.000'))
        self.assertEqual(po_line.get_receiving_percentage(), 100.0)
        
        po.refresh_from_db()
        self.assertEqual(po.status, 'RECEIVED')
        
        # Verify 3 GRNs created
        grns = GoodsReceipt.objects.filter(po_header=po)
        self.assertEqual(grns.count(), 3)
    
    def test_complete_workflow_with_gift_items(self):
        """Test: PR → PO → Receiving with bonus/gift items."""
        # Create and approve PR
        self.client.force_authenticate(user=self.requester)
        pr_data = {
            'pr_type': 'CATALOG',
            'justification': 'Need items',
            'requested_by': self.requester.id,
            'lines': [
                {
                    'line_number': 1,
                    'catalog_item_id': self.item1.id,
                    'quantity': '50.000',
                    'unit_of_measure_id': self.uom_ea.id,
                    'estimated_unit_price': '100.00'
                }
            ]
        }
        pr_response = self.client.post('/procurement/pr/', pr_data, format='json')
        pr_id = pr_response.data['id']
        
        self.client.post(f'/procurement/pr/{pr_id}/submit/')
        self.client.force_authenticate(user=self.approver)
        self.client.post(f'/procurement/pr/{pr_id}/approve/')
        
        # Convert to PO and confirm
        convert_response = self.client.post(
            f'/procurement/pr/{pr_id}/convert-to-po/',
            {'supplier_id': self.business_partner.id}
        )
        po_id = convert_response.data['id']
        
        self.client.post(f'/procurement/po/{po_id}/submit/')
        self.client.post(f'/procurement/po/{po_id}/approve/')
        self.client.post(f'/procurement/po/{po_id}/confirm/')
        
        po = POHeader.objects.get(id=po_id)
        po_line = po.po_lines.first()
        
        # Receive ordered items + gift items
        self.client.force_authenticate(user=self.receiver)
        grn_data = {
            'po_header_id': po_id,
            'receipt_date': '2025-12-23',
            'grn_type': 'STANDARD',
            'received_by': self.receiver.id,
            'notes': 'Received with bonus items',
            'lines_from_po': [
                {'po_line_item_id': po_line.id}
            ],
            'lines': [
                {
                    'line_number': 2,
                    'item_code': 'GIFT001',
                    'item_description': 'Bonus item from supplier',
                    'quantity_received': '5.000',
                    'unit_of_measure_id': self.uom_ea.id,
                    'unit_price': '0.00',
                    'is_gift': True,
                    'line_notes': 'Free bonus items'
                }
            ]
        }
        grn_response = self.client.post('/procurement/receiving/', grn_data, format='json')
        self.assertEqual(grn_response.status_code, status.HTTP_201_CREATED)
        
        # Verify GRN has 2 lines: 1 from PO, 1 gift
        grn = GoodsReceipt.objects.get(id=grn_response.data['id'])
        self.assertEqual(grn.grn_lines.count(), 2)
        
        # Verify gift line
        gift_line = grn.grn_lines.filter(is_gift=True).first()
        self.assertIsNotNone(gift_line)
        self.assertIsNone(gift_line.po_line_item)
        self.assertEqual(gift_line.quantity_ordered, Decimal('0.000'))
        self.assertEqual(gift_line.quantity_received, Decimal('5.000'))
        self.assertEqual(gift_line.unit_price, Decimal('0.00'))
    
    def test_complete_workflow_non_catalog_items(self):
        """Test: PR (non-catalog) → PO → Receiving."""
        # Create non-catalog PR
        self.client.force_authenticate(user=self.requester)
        pr_data = {
            'pr_type': 'NON_CATALOG',
            'justification': 'Special item not in catalog',
            'requested_by': self.requester.id,
            'lines': [
                {
                    'line_number': 1,
                    'item_description': 'Custom fabricated part',
                    'quantity': '10.000',
                    'unit_of_measure_id': self.uom_ea.id,
                    'estimated_unit_price': '500.00'
                }
            ]
        }
        pr_response = self.client.post('/procurement/pr/', pr_data, format='json')
        pr_id = pr_response.data['id']
        
        # Approve and convert to PO
        self.client.post(f'/procurement/pr/{pr_id}/submit/')
        self.client.force_authenticate(user=self.approver)
        self.client.post(f'/procurement/pr/{pr_id}/approve/')
        
        convert_response = self.client.post(
            f'/procurement/pr/{pr_id}/convert-to-po/',
            {'supplier_id': self.business_partner.id}
        )
        po_id = convert_response.data['id']
        
        # Confirm PO
        self.client.post(f'/procurement/po/{po_id}/submit/')
        self.client.post(f'/procurement/po/{po_id}/approve/')
        self.client.post(f'/procurement/po/{po_id}/confirm/')
        
        # Receive items
        self.client.force_authenticate(user=self.receiver)
        po = POHeader.objects.get(id=po_id)
        grn_data = {
            'po_header_id': po_id,
            'receipt_date': '2025-12-23',
            'grn_type': 'STANDARD',
            'received_by': self.receiver.id,
            'lines_from_po': [
                {'po_line_item_id': po.po_lines.first().id}
            ]
        }
        grn_response = self.client.post('/procurement/receiving/', grn_data, format='json')
        self.assertEqual(grn_response.status_code, status.HTTP_201_CREATED)
        
        # Verify receiving
        grn = GoodsReceipt.objects.get(id=grn_response.data['id'])
        self.assertEqual(grn.grn_lines.count(), 1)
        
        po.refresh_from_db()
        self.assertEqual(po.status, 'RECEIVED')


class MultiPOFromSinglePRTests(ProcurementIntegrationTestCase):
    """Test scenarios where one PR can create multiple POs."""
    
    def test_split_pr_to_multiple_pos(self):
        """Test: Single PR with multiple lines → Split into separate POs."""
        # Create PR with multiple items
        self.client.force_authenticate(user=self.requester)
        pr_data = {
            'pr_type': 'CATALOG',
            'justification': 'Multiple items needed',
            'requested_by': self.requester.id,
            'lines': [
                {
                    'line_number': 1,
                    'catalog_item_id': self.item1.id,
                    'quantity': '10.000',
                    'unit_of_measure_id': self.uom_ea.id,
                    'estimated_unit_price': '100.00'
                },
                {
                    'line_number': 2,
                    'catalog_item_id': self.item2.id,
                    'quantity': '5.000',
                    'unit_of_measure_id': self.uom_kg.id,
                    'estimated_unit_price': '50.00'
                }
            ]
        }
        pr_response = self.client.post('/procurement/pr/', pr_data, format='json')
        pr_id = pr_response.data['id']
        
        # Approve PR
        self.client.post(f'/procurement/pr/{pr_id}/submit/')
        self.client.force_authenticate(user=self.approver)
        self.client.post(f'/procurement/pr/{pr_id}/approve/')
        
        # Create first PO for line 1
        pr = PRHeader.objects.get(id=pr_id)
        pr_line1 = pr.pr_lines.get(line_number=1)
        
        convert_response1 = self.client.post(
            f'/procurement/pr/{pr_id}/convert-to-po/',
            {
                'supplier_id': self.business_partner.id,
                'line_ids': [pr_line1.id]
            }
        )
        self.assertEqual(convert_response1.status_code, status.HTTP_201_CREATED)
        po1_id = convert_response1.data['id']
        
        # Verify first PO
        po1 = POHeader.objects.get(id=po1_id)
        self.assertEqual(po1.po_lines.count(), 1)
        
        # PR should still be APPROVED (partially converted)
        pr.refresh_from_db()
        self.assertEqual(pr.status, 'APPROVED')


class ReceivingValidationTests(ProcurementIntegrationTestCase):
    """Test validation rules in receiving process."""
    
    def test_cannot_receive_more_than_ordered(self):
        """Test: Cannot receive quantity greater than ordered."""
        # Create and approve PR → PO
        self.client.force_authenticate(user=self.requester)
        pr_data = {
            'pr_type': 'CATALOG',
            'justification': 'Test order',
            'requested_by': self.requester.id,
            'lines': [
                {
                    'line_number': 1,
                    'catalog_item_id': self.item1.id,
                    'quantity': '10.000',
                    'unit_of_measure_id': self.uom_ea.id,
                    'estimated_unit_price': '100.00'
                }
            ]
        }
        pr_response = self.client.post('/procurement/pr/', pr_data, format='json')
        pr_id = pr_response.data['id']
        
        self.client.post(f'/procurement/pr/{pr_id}/submit/')
        self.client.force_authenticate(user=self.approver)
        self.client.post(f'/procurement/pr/{pr_id}/approve/')
        
        convert_response = self.client.post(
            f'/procurement/pr/{pr_id}/convert-to-po/',
            {'supplier_id': self.business_partner.id}
        )
        po_id = convert_response.data['id']
        
        self.client.post(f'/procurement/po/{po_id}/submit/')
        self.client.post(f'/procurement/po/{po_id}/approve/')
        self.client.post(f'/procurement/po/{po_id}/confirm/')
        
        # Try to receive more than ordered
        self.client.force_authenticate(user=self.receiver)
        po = POHeader.objects.get(id=po_id)
        grn_data = {
            'po_header_id': po_id,
            'receipt_date': '2025-12-23',
            'grn_type': 'STANDARD',
            'received_by': self.receiver.id,
            'lines_from_po': [
                {
                    'po_line_item_id': po.po_lines.first().id,
                    'quantity_to_receive': '15.000'  # Ordered only 10
                }
            ]
        }
        grn_response = self.client.post('/procurement/receiving/', grn_data, format='json')
        self.assertEqual(grn_response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_cannot_receive_from_unconfirmed_po(self):
        """Test: Cannot receive from PO that is not CONFIRMED."""
        # Create PO but don't confirm
        self.client.force_authenticate(user=self.requester)
        pr_data = {
            'pr_type': 'CATALOG',
            'justification': 'Test order',
            'requested_by': self.requester.id,
            'lines': [
                {
                    'line_number': 1,
                    'catalog_item_id': self.item1.id,
                    'quantity': '10.000',
                    'unit_of_measure_id': self.uom_ea.id,
                    'estimated_unit_price': '100.00'
                }
            ]
        }
        pr_response = self.client.post('/procurement/pr/', pr_data, format='json')
        pr_id = pr_response.data['id']
        
        self.client.post(f'/procurement/pr/{pr_id}/submit/')
        self.client.force_authenticate(user=self.approver)
        self.client.post(f'/procurement/pr/{pr_id}/approve/')
        
        convert_response = self.client.post(
            f'/procurement/pr/{pr_id}/convert-to-po/',
            {'supplier_id': self.business_partner.id}
        )
        po_id = convert_response.data['id']
        
        # PO is still DRAFT - try to receive
        self.client.force_authenticate(user=self.receiver)
        po = POHeader.objects.get(id=po_id)
        grn_data = {
            'po_header_id': po_id,
            'receipt_date': '2025-12-23',
            'grn_type': 'STANDARD',
            'received_by': self.receiver.id,
            'lines_from_po': [
                {'po_line_item_id': po.po_lines.first().id}
            ]
        }
        grn_response = self.client.post('/procurement/receiving/', grn_data, format='json')
        self.assertEqual(grn_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('PO must be CONFIRMED', str(grn_response.data))
    
    def test_grn_deletion_reverses_quantities(self):
        """Test: Deleting GRN reverses received quantities in PO."""
        # Create complete workflow
        self.client.force_authenticate(user=self.requester)
        pr_data = {
            'pr_type': 'CATALOG',
            'justification': 'Test order',
            'requested_by': self.requester.id,
            'lines': [
                {
                    'line_number': 1,
                    'catalog_item_id': self.item1.id,
                    'quantity': '10.000',
                    'unit_of_measure_id': self.uom_ea.id,
                    'estimated_unit_price': '100.00'
                }
            ]
        }
        pr_response = self.client.post('/procurement/pr/', pr_data, format='json')
        pr_id = pr_response.data['id']
        
        self.client.post(f'/procurement/pr/{pr_id}/submit/')
        self.client.force_authenticate(user=self.approver)
        self.client.post(f'/procurement/pr/{pr_id}/approve/')
        
        convert_response = self.client.post(
            f'/procurement/pr/{pr_id}/convert-to-po/',
            {'supplier_id': self.business_partner.id}
        )
        po_id = convert_response.data['id']
        
        self.client.post(f'/procurement/po/{po_id}/submit/')
        self.client.post(f'/procurement/po/{po_id}/approve/')
        self.client.post(f'/procurement/po/{po_id}/confirm/')
        
        # Receive items
        self.client.force_authenticate(user=self.receiver)
        po = POHeader.objects.get(id=po_id)
        po_line = po.po_lines.first()
        
        grn_data = {
            'po_header_id': po_id,
            'receipt_date': '2025-12-23',
            'grn_type': 'STANDARD',
            'received_by': self.receiver.id,
            'lines_from_po': [
                {'po_line_item_id': po_line.id}
            ]
        }
        grn_response = self.client.post('/procurement/receiving/', grn_data, format='json')
        grn_id = grn_response.data['id']
        
        # Verify received
        po_line.refresh_from_db()
        self.assertEqual(po_line.quantity_received, Decimal('10.000'))
        
        po.refresh_from_db()
        self.assertEqual(po.status, 'RECEIVED')
        
        # Delete GRN
        delete_response = self.client.delete(f'/procurement/receiving/{grn_id}/')
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify quantities reversed
        po_line.refresh_from_db()
        self.assertEqual(po_line.quantity_received, Decimal('0.000'))
        
        po.refresh_from_db()
        self.assertEqual(po.status, 'CONFIRMED')


class ProcurementReportingTests(ProcurementIntegrationTestCase):
    """Test reporting and analytics across the procurement workflow."""
    
    def test_po_receiving_status_report(self):
        """Test: Get comprehensive receiving status for a PO."""
        # Create complete workflow with partial receipts
        self.client.force_authenticate(user=self.requester)
        pr_data = {
            'pr_type': 'CATALOG',
            'justification': 'Test order',
            'requested_by': self.requester.id,
            'lines': [
                {
                    'line_number': 1,
                    'catalog_item_id': self.item1.id,
                    'quantity': '100.000',
                    'unit_of_measure_id': self.uom_ea.id,
                    'estimated_unit_price': '100.00'
                }
            ]
        }
        pr_response = self.client.post('/procurement/pr/', pr_data, format='json')
        pr_id = pr_response.data['id']
        
        self.client.post(f'/procurement/pr/{pr_id}/submit/')
        self.client.force_authenticate(user=self.approver)
        self.client.post(f'/procurement/pr/{pr_id}/approve/')
        
        convert_response = self.client.post(
            f'/procurement/pr/{pr_id}/convert-to-po/',
            {'supplier_id': self.business_partner.id}
        )
        po_id = convert_response.data['id']
        
        self.client.post(f'/procurement/po/{po_id}/submit/')
        self.client.post(f'/procurement/po/{po_id}/approve/')
        self.client.post(f'/procurement/po/{po_id}/confirm/')
        
        # Partial receipt - 60 units
        self.client.force_authenticate(user=self.receiver)
        po = POHeader.objects.get(id=po_id)
        grn_data = {
            'po_header_id': po_id,
            'receipt_date': '2025-12-23',
            'grn_type': 'STANDARD',
            'received_by': self.receiver.id,
            'lines_from_po': [
                {
                    'po_line_item_id': po.po_lines.first().id,
                    'quantity_to_receive': '60.000'
                }
            ]
        }
        self.client.post('/procurement/receiving/', grn_data, format='json')
        
        # Get PO receiving status
        status_response = self.client.get(f'/procurement/receiving/po/{po_id}/status/')
        self.assertEqual(status_response.status_code, status.HTTP_200_OK)
        
        # Verify report data
        data = status_response.data
        self.assertEqual(data['po_number'], po.po_number)
        self.assertEqual(data['total_grns'], 1)
        self.assertEqual(len(data['lines']), 1)
        
        line_data = data['lines'][0]
        self.assertEqual(line_data['quantity_ordered'], '100.000')
        self.assertEqual(line_data['quantity_received'], '60.000')
        self.assertEqual(line_data['receipt_percentage'], 60.0)


class ServicePRWorkflowTests(ProcurementIntegrationTestCase):
    """Test procurement workflow for service-type PRs."""
    
    def test_service_pr_to_po_no_receiving(self):
        """Test: Service PR → PO (no receiving needed)."""
        # Create service PR
        self.client.force_authenticate(user=self.requester)
        pr_data = {
            'pr_type': 'SERVICE',
            'justification': 'Consulting services needed',
            'requested_by': self.requester.id,
            'lines': [
                {
                    'line_number': 1,
                    'item_description': 'Software consulting',
                    'quantity': '40.000',  # Hours
                    'unit_of_measure_id': self.uom_ea.id,  # Or create HOUR UOM
                    'estimated_unit_price': '150.00'
                }
            ]
        }
        pr_response = self.client.post('/procurement/pr/', pr_data, format='json')
        pr_id = pr_response.data['id']
        
        # Approve and convert to PO
        self.client.post(f'/procurement/pr/{pr_id}/submit/')
        self.client.force_authenticate(user=self.approver)
        self.client.post(f'/procurement/pr/{pr_id}/approve/')
        
        convert_response = self.client.post(
            f'/procurement/pr/{pr_id}/convert-to-po/',
            {'supplier_id': self.business_partner.id}
        )
        self.assertEqual(convert_response.status_code, status.HTTP_201_CREATED)
        
        po_id = convert_response.data['id']
        po = POHeader.objects.get(id=po_id)
        
        # Verify PO created for service
        self.assertEqual(po.po_lines.count(), 1)
        
        # Services typically don't go through receiving
        # They would be marked as received via invoice matching or completion confirmation
        # This test verifies the PO can be created successfully
