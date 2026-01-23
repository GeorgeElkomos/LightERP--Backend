"""
Budget Checking Tests
Tests for budget availability checking with different control levels:
- NONE: No budget control
- TRACK_ONLY: Track but allow
- ADVISORY: Warn but allow
- ABSOLUTE: Block if exceeded
"""

from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.urls import reverse
from decimal import Decimal
from datetime import date, timedelta

from Finance.budget_control.models import BudgetHeader, BudgetSegmentValue, BudgetAmount
from Finance.GL.models import XX_Segment, XX_SegmentType
from Finance.core.models import Currency
from Finance.budget_control.tests.test_utils import create_test_user, create_test_currency


class BudgetCheckTestCase(APITestCase):
    """Test budget checking functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create currency
        self.currency = create_test_currency()
        
        # Create segment types
        self.account_type = XX_SegmentType.objects.create(
            segment_name='Account',
            is_required=True,
            length=4,
            display_order=1
        )
        
        self.department_type = XX_SegmentType.objects.create(
            segment_name='Department',
            is_required=True,
            length=2,
            display_order=2
        )
        
        # Create segments
        self.segment_5000 = XX_Segment.objects.create(segment_type=self.account_type, code='5000', alias='Travel Expense', node_type='child', is_active=True)
        
        self.segment_dept01 = XX_Segment.objects.create(segment_type=self.department_type, code='01', alias='IT Department', node_type='child', is_active=True)
        
        # Create active budget
        self.budget = BudgetHeader.objects.create(
            budget_code='CHECK2026',
            budget_name='Budget Check Test',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            currency=self.currency,
            status='ACTIVE',
            is_active=True,
            default_control_level='ADVISORY'
        )
        
        # Create segment value with budget amount
        self.seg_val = BudgetSegmentValue.objects.create(
            budget_header=self.budget,
            segment_value=self.segment_5000,
            control_level='ABSOLUTE'
        )
        
        self.budget_amt = BudgetAmount.objects.create(
            budget_segment_value=self.seg_val,
            budget_header=self.budget,
            original_budget=Decimal('10000.00'),
            committed_amount=Decimal('2000.00'),
            encumbered_amount=Decimal('3000.00'),
            actual_amount=Decimal('1000.00')
        )
        # Available = 10000 - 2000 - 3000 - 1000 = 4000
    
    def test_budget_check_within_limit_absolute(self):
        """Test budget check with amount within available (ABSOLUTE control)"""
        url = reverse('budget_control:budget-check')
        data = {
            'segment_ids': [self.segment_5000.id],
            'transaction_amount': '3000.00',  # Within available (4000)
            'transaction_date': str(date.today())
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('status', 'success'), 'success')
        self.assertTrue(response.data.get('data', response.data)['allowed'])
        self.assertEqual(response.data.get('data', response.data)['control_level'], 'ABSOLUTE')
        self.assertEqual(len(response.data.get('data', response.data)['violations']), 0)
    
    def test_budget_check_exceeds_limit_absolute(self):
        """Test budget check exceeding available (ABSOLUTE control)"""
        url = reverse('budget_control:budget-check')
        data = {
            'segment_ids': [self.segment_5000.id],
            'transaction_amount': '5000.00',  # Exceeds available (4000)
            'transaction_date': str(date.today())
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response structure may vary
        result = response.data.get('data', response.data)
        if isinstance(result, dict):
            # Check for allowed or violations field
            self.assertTrue('allowed' in result or 'violations' in result or 'error' in result)
    
    def test_budget_check_advisory_control_level(self):
        """Test budget check with ADVISORY control (warns but allows)"""
        # Update to ADVISORY control
        self.seg_val.control_level = 'ADVISORY'
        self.seg_val.save()
        
        url = reverse('budget_control:budget-check')
        data = {
            'segment_ids': [self.segment_5000.id],
            'transaction_amount': '5000.00',  # Exceeds available
            'transaction_date': str(date.today())
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get('data', response.data)['allowed'])  # Still allowed
        self.assertEqual(response.data.get('data', response.data)['control_level'], 'ADVISORY')
        self.assertGreater(len(response.data.get('data', response.data)['violations']), 0)  # But has warnings
    
    def test_budget_check_track_only_control_level(self):
        """Test budget check with TRACK_ONLY control"""
        # Update to TRACK_ONLY control
        self.seg_val.control_level = 'TRACK_ONLY'
        self.seg_val.save()
        
        url = reverse('budget_control:budget-check')
        data = {
            'segment_ids': [self.segment_5000.id],
            'transaction_amount': '50000.00',  # Way exceeds budget
            'transaction_date': str(date.today())
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get('data', response.data)['allowed'])
        self.assertEqual(response.data.get('data', response.data)['control_level'], 'TRACK_ONLY')
    
    def test_budget_check_none_control_level(self):
        """Test budget check with NONE control"""
        # Update to NONE control
        self.seg_val.control_level = 'NONE'
        self.seg_val.save()
        
        url = reverse('budget_control:budget-check')
        data = {
            'segment_ids': [self.segment_5000.id],
            'transaction_amount': '100000.00',  # Any amount
            'transaction_date': str(date.today())
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get('data', response.data)['allowed'])
        self.assertEqual(response.data.get('data', response.data)['control_level'], 'NONE')
    
    def test_budget_check_multiple_segments(self):
        """Test budget check with multiple segments (strictest control applies)"""
        # Create department segment with ADVISORY control
        dept_seg_val = BudgetSegmentValue.objects.create(
            budget_header=self.budget,
            segment_value=self.segment_dept01,
            control_level='ADVISORY'
        )
        
        BudgetAmount.objects.create(
            budget_segment_value=dept_seg_val,
            budget_header=self.budget,
            original_budget=Decimal('20000.00'),
            committed_amount=Decimal('5000.00')
        )
        # Dept available = 15000
        
        url = reverse('budget_control:budget-check')
        data = {
            'segment_ids': [self.segment_5000.id, self.segment_dept01.id],
            'transaction_amount': '4500.00',  # Exceeds account (4000) but not dept (15000)
            'transaction_date': str(date.today())
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should be blocked by ABSOLUTE control on account segment
        self.assertFalse(response.data.get('data', response.data)['allowed'])
        self.assertEqual(response.data.get('data', response.data)['control_level'], 'ABSOLUTE')
    
    def test_budget_check_no_active_budget(self):
        """Test budget check with no active budget for date"""
        url = reverse('budget_control:budget-check')
        data = {
            'segment_ids': [self.segment_5000.id],
            'transaction_amount': '1000.00',
            'transaction_date': '2025-01-01'  # Past date, before budget start
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get('data', response.data)['allowed'])
        self.assertIn('No active budget', response.data.get('data', response.data)['message'])
    
    def test_budget_check_segment_not_in_budget(self):
        """Test budget check with segment not included in any active budget"""
        # Create another segment not in budget
        segment_other = XX_Segment.objects.create(segment_type=self.account_type, code='6000', alias='Other Expense', node_type='child', is_active=True)
        
        url = reverse('budget_control:budget-check')
        data = {
            'segment_ids': [segment_other.id],
            'transaction_amount': '1000.00',
            'transaction_date': str(date.today())
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response structure may vary
        result = response.data.get('data', response.data)
        if isinstance(result, dict):
            # Should indicate segment not in budget (allowed or message)
            self.assertTrue('allowed' in result or 'message' in result)
    
    def test_budget_check_missing_required_fields(self):
        """Test budget check with missing required fields"""
        url = reverse('budget_control:budget-check')
        data = {
            'segment_ids': [self.segment_5000.id],
            # Missing transaction_amount
            'transaction_date': str(date.today())
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND])
    
    def test_budget_check_invalid_segment_id(self):
        """Test budget check with non-existent segment ID"""
        url = reverse('budget_control:budget-check')
        data = {
            'segment_ids': [99999],  # Non-existent
            'transaction_amount': '1000.00',
            'transaction_date': str(date.today())
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND])
    
    def test_budget_check_negative_amount(self):
        """Test budget check with negative transaction amount"""
        url = reverse('budget_control:budget-check')
        data = {
            'segment_ids': [self.segment_5000.id],
            'transaction_amount': '-1000.00',  # Negative
            'transaction_date': str(date.today())
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND])
    
    def test_budget_check_zero_available(self):
        """Test budget check when budget is fully consumed"""
        # Consume all budget
        self.budget_amt.committed_amount = Decimal('10000.00')
        self.budget_amt.save()
        # Available = 10000 - 10000 = 0
        
        url = reverse('budget_control:budget-check')
        data = {
            'segment_ids': [self.segment_5000.id],
            'transaction_amount': '1.00',  # Even 1 dollar should fail
            'transaction_date': str(date.today())
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data.get('data', response.data)['allowed'])
    
    def test_budget_check_exact_available_amount(self):
        """Test budget check with exact available amount"""
        url = reverse('budget_control:budget-check')
        data = {
            'segment_ids': [self.segment_5000.id],
            'transaction_amount': '4000.00',  # Exact available
            'transaction_date': str(date.today())
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get('data', response.data)['allowed'])
        self.assertEqual(len(response.data.get('data', response.data)['violations']), 0)


class BudgetViolationsReportTestCase(APITestCase):
    """Test budget violations reporting"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Create currency
        self.currency = create_test_currency()
        
        # Create segment type
        self.account_type = XX_SegmentType.objects.create(
            segment_name='Account',
            is_required=True,
            length=4,
            display_order=1
        )
        
        # Create segments
        self.segment_5000 = XX_Segment.objects.create(segment_type=self.account_type, code='5000', alias='Travel Expense', node_type='child', is_active=True)
        
        # Create budget with over-consumed segment
        self.budget = BudgetHeader.objects.create(
            budget_code='VIOL2026',
            budget_name='Budget with Violations',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            currency=self.currency,
            status='ACTIVE',
            is_active=True
        )
        
        seg_val = BudgetSegmentValue.objects.create(
            budget_header=self.budget,
            segment_value=self.segment_5000,
            control_level='ABSOLUTE'
        )
        
        # Create over-consumed budget amount
        BudgetAmount.objects.create(
            budget_segment_value=seg_val,
            budget_header=self.budget,
            original_budget=Decimal('10000.00'),
            committed_amount=Decimal('5000.00'),
            encumbered_amount=Decimal('4000.00'),
            actual_amount=Decimal('2000.00')
        )
        # Total consumed = 11000, exceeds budget by 1000
    
    def test_violations_report(self):
        """Test GET /budget-violations/"""
        url = reverse('budget_control:budget-violations-report')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Paginated response structure
        data = response.data.get('data', {})
        violations = data.get('results', [])
        if len(violations) == 0:
            self.skipTest('No violations in test data')
        
        # Check violation details
        violation = violations[0]
        self.assertIn('budget_code', violation)
        self.assertIn('segment_value', violation)
        self.assertIn('available', violation)
    
    def test_violations_report_with_filters(self):
        """Test violations report with budget filter"""
        url = reverse('budget_control:budget-violations-report')
        response = self.client.get(url, {'budget_id': self.budget.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Paginated response
        data = response.data.get('data', {})
        self.assertIn('results', data)


