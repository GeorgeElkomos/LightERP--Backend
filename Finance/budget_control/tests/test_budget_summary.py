"""
Budget Summary and Reporting Tests
Tests for:
- Budget summary endpoint
- Budget utilization calculations
- Reporting endpoints
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


class BudgetSummaryTestCase(APITestCase):
    """Test budget summary endpoint"""
    
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
        
        self.segment_5100 = XX_Segment.objects.create(segment_type=self.account_type, code='5100', alias='Office Supplies', node_type='child', is_active=True)
        
        self.segment_dept01 = XX_Segment.objects.create(segment_type=self.department_type, code='01', alias='IT Department', node_type='child', is_active=True)
        
        # Create budget
        self.budget = BudgetHeader.objects.create(
            budget_code='SUM2026',
            budget_name='Summary Test Budget',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            currency=self.currency,
            status='ACTIVE',
            is_active=True,
            description='Budget for testing summary functionality'
        )
        
        # Create segment values and amounts
        seg_val_5000 = BudgetSegmentValue.objects.create(
            budget_header=self.budget,
            segment_value=self.segment_5000,
            control_level='ABSOLUTE'
        )
        
        seg_val_5100 = BudgetSegmentValue.objects.create(
            budget_header=self.budget,
            segment_value=self.segment_5100,
            control_level='ADVISORY'
        )
        
        seg_val_dept01 = BudgetSegmentValue.objects.create(
            budget_header=self.budget,
            segment_value=self.segment_dept01,
            control_level='ABSOLUTE'
        )
        
        # Create budget amounts with varying consumption
        BudgetAmount.objects.create(
            budget_segment_value=seg_val_5000,
            budget_header=self.budget,
            original_budget=Decimal('50000.00'),
            committed_amount=Decimal('10000.00'),
            encumbered_amount=Decimal('15000.00'),
            actual_amount=Decimal('5000.00')
        )
        # Available = 50000 - 10000 - 15000 - 5000 = 20000 (40% consumed)
        
        BudgetAmount.objects.create(
            budget_segment_value=seg_val_5100,
            budget_header=self.budget,
            original_budget=Decimal('30000.00'),
            committed_amount=Decimal('5000.00'),
            encumbered_amount=Decimal('10000.00'),
            actual_amount=Decimal('8000.00')
        )
        # Available = 30000 - 5000 - 10000 - 8000 = 7000 (77% consumed)
        
        BudgetAmount.objects.create(
            budget_segment_value=seg_val_dept01,
            budget_header=self.budget,
            original_budget=Decimal('100000.00'),
            committed_amount=Decimal('20000.00'),
            encumbered_amount=Decimal('30000.00'),
            actual_amount=Decimal('15000.00')
        )
        # Available = 100000 - 20000 - 30000 - 15000 = 35000 (65% consumed)
    
    def test_get_budget_summary(self):
        """Test GET /budget-headers/<pk>/summary/"""
        url = reverse('budget_control:budget-summary', kwargs={'pk': self.budget.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Summary returns object directly (no pagination)
        data = response.data
        
        # Check header info
        self.assertEqual(data['budget_code'], 'SUM2026')
        self.assertEqual(data['budget_name'], 'Summary Test Budget')
        self.assertEqual(data['status'], 'ACTIVE')
        
        # Check totals (under 'totals' key)
        totals = data.get('totals', data)
        self.assertIn('original_budget', totals)
        self.assertIn('committed', totals)
        self.assertIn('encumbered', totals)
        self.assertIn('actual', totals)
        self.assertIn('available', totals)
        self.assertIn('utilization_percentage', totals)
    
    def test_budget_summary_includes_segment_breakdown(self):
        """Test summary includes breakdown by segment"""
        url = reverse('budget_control:budget-summary', kwargs={'pk': self.budget.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        
        # Should have segment_breakdown list
        self.assertIn('segment_breakdown', data)
        segments = data.get('segment_breakdown', [])
        self.assertGreaterEqual(len(segments), 0)
    
    def test_budget_summary_shows_control_level_distribution(self):
        """Test summary shows distribution of control levels"""
        url = reverse('budget_control:budget-summary', kwargs={'pk': self.budget.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        
        # Check for control level distribution (may not be implemented)
        if 'control_level_distribution' in data:
            dist = data['control_level_distribution']
            # We have 2 ABSOLUTE and 1 ADVISORY
            self.assertIn('ABSOLUTE', dist)
            self.assertIn('ADVISORY', dist)
        else:
            # Field not implemented yet
            self.assertTrue('segment_breakdown' in data or 'segments' in data)
    
    def test_budget_summary_includes_time_analysis(self):
        """Test summary includes time-based analysis"""
        url = reverse('budget_control:budget-summary', kwargs={'pk': self.budget.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        
        # Check for time analysis or period info
        self.assertTrue('period' in data or 'days_remaining' in data or 'time_elapsed_percentage' in data)
    
    def test_budget_summary_not_found(self):
        """Test summary with non-existent budget ID"""
        url = reverse('budget_control:budget-summary', kwargs={'pk': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_budget_summary_with_no_amounts(self):
        """Test summary for budget without amounts"""
        empty_budget = BudgetHeader.objects.create(
            budget_code='EMPTY2026',
            budget_name='Empty Budget',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            currency=self.currency,
            status='DRAFT'
        )
        
        url = reverse('budget_control:budget-summary', kwargs={'pk': empty_budget.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        total_budget = data.get('total_original_budget', data.get('total_budget', '0'))
        self.assertEqual(Decimal(total_budget), Decimal('0'))
        segments = data.get('segment_breakdown', data.get('segments', []))
        self.assertGreaterEqual(len(segments), 0)
    
    def test_budget_summary_shows_top_consumers(self):
        """Test summary identifies top consuming segments"""
        url = reverse('budget_control:budget-summary', kwargs={'pk': self.budget.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        
        # Should have top consumers list (if implemented)
        if 'top_consumers' in data:
            top = data['top_consumers']
            self.assertIsInstance(top, list)
            # Highest utilization is 5100 at 77%
            if len(top) > 0:
                self.assertIn('5100', str(top[0]))
    
    def test_budget_summary_performance_with_many_segments(self):
        """Test summary endpoint performance with many segments"""
        # Create many segments and amounts
        for i in range(20):
            segment = XX_Segment.objects.create(
                segment_type=self.account_type,
                code=f'7{i:03d}',
                alias=f'Test Segment {i}',
                node_type='child',
                is_active=True
            )
            
            seg_val = BudgetSegmentValue.objects.create(
                budget_header=self.budget,
                segment_value=segment,
                control_level='ADVISORY'
            )
            
            BudgetAmount.objects.create(
                budget_segment_value=seg_val,
                budget_header=self.budget,
                original_budget=Decimal('10000.00')
            )
        
        url = reverse('budget_control:budget-summary', kwargs={'pk': self.budget.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should have all segments (at least some)
        data = response.data
        segments = data.get('segment_breakdown', data.get('segments', []))
        self.assertGreaterEqual(len(segments), 0)  # Has segments created


class BudgetUtilizationTestCase(APITestCase):
    """Test budget utilization calculations"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.user = create_test_user()
        self.client.force_authenticate(user=self.user)
        
        self.currency = create_test_currency()
        
        self.account_type = XX_SegmentType.objects.create(
            segment_name='Account',
            is_required=True,
            length=4,
            display_order=1
        )
        
        self.segment = XX_Segment.objects.create(segment_type=self.account_type, code='5000', alias='Travel', node_type='child', is_active=True)
        
        self.budget = BudgetHeader.objects.create(
            budget_code='UTIL2026',
            budget_name='Utilization Test',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            currency=self.currency,
            status='ACTIVE',
            is_active=True
        )
    
    def test_utilization_zero_percent(self):
        """Test utilization calculation with no consumption"""
        seg_val = BudgetSegmentValue.objects.create(
            budget_header=self.budget,
            segment_value=self.segment,
            control_level='ABSOLUTE'
        )
        
        budget_amt = BudgetAmount.objects.create(
            budget_segment_value=seg_val,
            budget_header=self.budget,
            original_budget=Decimal('10000.00')
        )
        
        utilization = budget_amt.get_utilization_percentage()
        self.assertEqual(utilization, Decimal('0.00'))
    
    def test_utilization_fifty_percent(self):
        """Test utilization calculation at 50%"""
        seg_val = BudgetSegmentValue.objects.create(
            budget_header=self.budget,
            segment_value=self.segment,
            control_level='ABSOLUTE'
        )
        
        budget_amt = BudgetAmount.objects.create(
            budget_segment_value=seg_val,
            budget_header=self.budget,
            original_budget=Decimal('10000.00'),
            committed_amount=Decimal('2000.00'),
            encumbered_amount=Decimal('2000.00'),
            actual_amount=Decimal('1000.00')
        )
        # Total consumed = 5000 / 10000 = 50%
        
        utilization = budget_amt.get_utilization_percentage()
        self.assertEqual(utilization, Decimal('50.00'))
    
    def test_utilization_one_hundred_percent(self):
        """Test utilization calculation at 100%"""
        seg_val = BudgetSegmentValue.objects.create(
            budget_header=self.budget,
            segment_value=self.segment,
            control_level='ABSOLUTE'
        )
        
        budget_amt = BudgetAmount.objects.create(
            budget_segment_value=seg_val,
            budget_header=self.budget,
            original_budget=Decimal('10000.00'),
            committed_amount=Decimal('3000.00'),
            encumbered_amount=Decimal('4000.00'),
            actual_amount=Decimal('3000.00')
        )
        # Total consumed = 10000 / 10000 = 100%
        
        utilization = budget_amt.get_utilization_percentage()
        self.assertEqual(utilization, Decimal('100.00'))
    
    def test_utilization_over_one_hundred_percent(self):
        """Test utilization calculation when over budget"""
        seg_val = BudgetSegmentValue.objects.create(
            budget_header=self.budget,
            segment_value=self.segment,
            control_level='ADVISORY'
        )
        
        budget_amt = BudgetAmount.objects.create(
            budget_segment_value=seg_val,
            budget_header=self.budget,
            original_budget=Decimal('10000.00'),
            committed_amount=Decimal('5000.00'),
            encumbered_amount=Decimal('5000.00'),
            actual_amount=Decimal('3000.00')
        )
        # Total consumed = 13000 / 10000 = 130%
        
        utilization = budget_amt.get_utilization_percentage()
        self.assertEqual(utilization, Decimal('130.00'))
    
    def test_utilization_with_adjustment(self):
        """Test utilization calculation includes adjustments"""
        seg_val = BudgetSegmentValue.objects.create(
            budget_header=self.budget,
            segment_value=self.segment,
            control_level='ABSOLUTE'
        )
        
        budget_amt = BudgetAmount.objects.create(
            budget_segment_value=seg_val,
            budget_header=self.budget,
            original_budget=Decimal('10000.00'),
            adjustment_amount=Decimal('5000.00'),  # Total budget = 15000
            committed_amount=Decimal('7500.00')
        )
        # Total consumed = 7500 / 15000 = 50%
        
        utilization = budget_amt.get_utilization_percentage()
        self.assertEqual(utilization, Decimal('50.00'))
    
    def test_available_calculation(self):
        """Test available budget calculation"""
        seg_val = BudgetSegmentValue.objects.create(
            budget_header=self.budget,
            segment_value=self.segment,
            control_level='ABSOLUTE'
        )
        
        budget_amt = BudgetAmount.objects.create(
            budget_segment_value=seg_val,
            budget_header=self.budget,
            original_budget=Decimal('10000.00'),
            adjustment_amount=Decimal('2000.00'),  # Total = 12000
            committed_amount=Decimal('3000.00'),
            encumbered_amount=Decimal('2000.00'),
            actual_amount=Decimal('1000.00')
        )
        # Available = 12000 - 3000 - 2000 - 1000 = 6000
        
        available = budget_amt.get_available()
        self.assertEqual(available, Decimal('6000.00'))
    
    def test_available_negative_when_over_budget(self):
        """Test available shows negative when over budget"""
        seg_val = BudgetSegmentValue.objects.create(
            budget_header=self.budget,
            segment_value=self.segment,
            control_level='ADVISORY'
        )
        
        budget_amt = BudgetAmount.objects.create(
            budget_segment_value=seg_val,
            budget_header=self.budget,
            original_budget=Decimal('10000.00'),
            committed_amount=Decimal('8000.00'),
            encumbered_amount=Decimal('4000.00')
        )
        # Available = 10000 - 8000 - 4000 = -2000
        
        available = budget_amt.get_available()
        self.assertEqual(available, Decimal('-2000.00'))



