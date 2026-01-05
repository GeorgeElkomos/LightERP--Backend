"""
Tests for Period models, views, and period validation integration.
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, timedelta
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

from Finance.period.models import Period, ar_period, ap_period, gl_period
from Finance.period.validators import PeriodValidator


User = get_user_model()


class PeriodModelTest(TestCase):
    """Test Period model creation and automatic child creation."""
    
    def setUp(self):
        """Set up test data."""
        self.period_data = {
            'name': 'January 2026',
            'start_date': date(2026, 1, 1),
            'end_date': date(2026, 1, 31),
            'fiscal_year': 2026,
            'period_number': 1,
            'is_adjustment_period': False,
            'description': 'First period of fiscal year 2026'
        }
    
    def test_create_period_creates_children(self):
        """Test that creating a Period automatically creates AR, AP, GL child records."""
        period = Period.objects.create(**self.period_data)
        
        # Check parent period exists
        self.assertIsNotNone(period.pk)
        self.assertEqual(period.name, 'January 2026')
        
        # Check AR period child was created
        self.assertTrue(hasattr(period, 'ar_period'))
        self.assertEqual(period.ar_period.state, 'closed')
        self.assertEqual(period.ar_period.period, period)
        
        # Check AP period child was created
        self.assertTrue(hasattr(period, 'ap_period'))
        self.assertEqual(period.ap_period.state, 'closed')
        self.assertEqual(period.ap_period.period, period)
        
        # Check GL period child was created
        self.assertTrue(hasattr(period, 'gl_period'))
        self.assertEqual(period.gl_period.state, 'closed')
        self.assertEqual(period.gl_period.period, period)
    
    def test_update_period_ensures_children_exist(self):
        """Test that updating a Period ensures children exist."""
        period = Period.objects.create(**self.period_data)
        
        # Update the period
        period.name = 'January 2026 - Updated'
        period.save()
        
        # Children should still exist
        self.assertTrue(hasattr(period, 'ar_period'))
        self.assertTrue(hasattr(period, 'ap_period'))
        self.assertTrue(hasattr(period, 'gl_period'))
    
    def test_delete_period_cascades_to_children(self):
        """Test that deleting a Period deletes all child records."""
        period = Period.objects.create(**self.period_data)
        ar_id = period.ar_period.id
        ap_id = period.ap_period.id
        gl_id = period.gl_period.id
        
        period.delete()
        
        # Check children were deleted
        self.assertFalse(ar_period.objects.filter(id=ar_id).exists())
        self.assertFalse(ap_period.objects.filter(id=ap_id).exists())
        self.assertFalse(gl_period.objects.filter(id=gl_id).exists())
    
    def test_parent_changes_reflect_in_children(self):
        """Test that changes to parent Period are visible in children."""
        period = Period.objects.create(**self.period_data)
        
        # Update parent
        period.name = 'January 2026 - Modified'
        period.start_date = date(2026, 1, 2)
        period.save()
        
        # Refresh child records
        period.ar_period.refresh_from_db()
        
        # Child should see updated parent data
        self.assertEqual(period.ar_period.period.name, 'January 2026 - Modified')
        self.assertEqual(period.ar_period.period.start_date, date(2026, 1, 2))


class PeriodValidatorTest(TestCase):
    """Test PeriodValidator utility functions."""
    
    def setUp(self):
        """Set up test periods."""
        # Create January 2026 period with all modules open
        self.jan_period = Period.objects.create(
            name='January 2026',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            fiscal_year=2026,
            period_number=1
        )
        self.jan_period.ar_period.state = 'open'
        self.jan_period.ar_period.save()
        self.jan_period.ap_period.state = 'open'
        self.jan_period.ap_period.save()
        self.jan_period.gl_period.state = 'open'
        self.jan_period.gl_period.save()
        
        # Create February 2026 period with all modules closed
        self.feb_period = Period.objects.create(
            name='February 2026',
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 28),
            fiscal_year=2026,
            period_number=2
        )
        # February stays closed (default)
        
        # Create adjustment period
        self.adj_period = Period.objects.create(
            name='Adjustment Period 1',
            start_date=date(2026, 12, 27),
            end_date=date(2026, 12, 31),
            fiscal_year=2026,
            period_number=13,
            is_adjustment_period=True
        )
        self.adj_period.gl_period.state = 'open'
        self.adj_period.gl_period.save()
    
    def test_validate_ar_period_open_success(self):
        """Test AR period validation passes for open period."""
        try:
            period = PeriodValidator.validate_ar_period_open(date(2026, 1, 15))
            self.assertEqual(period.id, self.jan_period.id)
        except ValidationError:
            self.fail("validate_ar_period_open raised ValidationError unexpectedly")
    
    def test_validate_ar_period_closed_fails(self):
        """Test AR period validation fails for closed period."""
        with self.assertRaises(ValidationError) as context:
            PeriodValidator.validate_ar_period_open(date(2026, 2, 15))
        
        self.assertIn('closed', str(context.exception))
    
    def test_validate_ar_period_no_period_fails(self):
        """Test AR period validation fails when no period exists."""
        with self.assertRaises(ValidationError) as context:
            PeriodValidator.validate_ar_period_open(date(2025, 12, 15))
        
        self.assertIn('No accounting period found', str(context.exception))
    
    def test_validate_ap_period_open_success(self):
        """Test AP period validation passes for open period."""
        try:
            period = PeriodValidator.validate_ap_period_open(date(2026, 1, 15))
            self.assertEqual(period.id, self.jan_period.id)
        except ValidationError:
            self.fail("validate_ap_period_open raised ValidationError unexpectedly")
    
    def test_validate_ap_period_closed_fails(self):
        """Test AP period validation fails for closed period."""
        with self.assertRaises(ValidationError) as context:
            PeriodValidator.validate_ap_period_open(date(2026, 2, 15))
        
        self.assertIn('closed', str(context.exception))
    
    def test_validate_gl_period_open_success(self):
        """Test GL period validation passes for open period."""
        try:
            period = PeriodValidator.validate_gl_period_open(date(2026, 1, 15))
            self.assertEqual(period.id, self.jan_period.id)
        except ValidationError:
            self.fail("validate_gl_period_open raised ValidationError unexpectedly")
    
    def test_validate_gl_period_closed_fails(self):
        """Test GL period validation fails for closed period."""
        with self.assertRaises(ValidationError) as context:
            PeriodValidator.validate_gl_period_open(date(2026, 2, 15))
        
        self.assertIn('closed', str(context.exception))
    
    def test_validate_gl_period_adjustment_allowed(self):
        """Test GL period validation allows posting to adjustment periods."""
        try:
            period = PeriodValidator.validate_gl_period_open(
                date(2026, 12, 30),
                allow_adjustment=True
            )
            self.assertEqual(period.id, self.adj_period.id)
        except ValidationError:
            self.fail("validate_gl_period_open raised ValidationError for adjustment period")
    
    def test_validate_period_boundary_dates(self):
        """Test validation on period start and end dates."""
        # Start date
        try:
            PeriodValidator.validate_ar_period_open(date(2026, 1, 1))
        except ValidationError:
            self.fail("Validation failed on period start date")
        
        # End date
        try:
            PeriodValidator.validate_ar_period_open(date(2026, 1, 31))
        except ValidationError:
            self.fail("Validation failed on period end date")
    
    def test_get_open_periods(self):
        """Test get_open_periods helper method."""
        # Get open AR periods
        ar_periods = PeriodValidator.get_open_periods('ar', fiscal_year=2026)
        self.assertEqual(ar_periods.count(), 1)
        self.assertEqual(ar_periods.first().id, self.jan_period.id)
        
        # Get open GL periods
        gl_periods = PeriodValidator.get_open_periods('gl', fiscal_year=2026)
        self.assertEqual(gl_periods.count(), 2)  # January + adjustment period
    
    def test_get_period_for_date(self):
        """Test get_period_for_date helper method."""
        period = PeriodValidator.get_period_for_date(date(2026, 1, 15))
        self.assertEqual(period.id, self.jan_period.id)
        
        period = PeriodValidator.get_period_for_date(date(2026, 2, 15))
        self.assertEqual(period.id, self.feb_period.id)
        
        period = PeriodValidator.get_period_for_date(date(2025, 12, 15))
        self.assertIsNone(period)


class PeriodAPITest(APITestCase):
    """Test Period API endpoints."""
    
    def setUp(self):
        """Set up test user and authentication."""
        self.user = User.objects.create_user(
            email='test@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    def test_create_period_via_api(self):
        """Test creating a period via API creates children."""
        data = {
            'name': 'March 2026',
            'start_date': '2026-03-01',
            'end_date': '2026-03-31',
            'fiscal_year': 2026,
            'period_number': 3,
            'is_adjustment_period': False
        }
        
        response = self.client.post('/finance/period/periods/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        period_id = response.data['data']['id']
        period = Period.objects.get(id=period_id)
        
        # Check children were created
        self.assertTrue(hasattr(period, 'ar_period'))
        self.assertTrue(hasattr(period, 'ap_period'))
        self.assertTrue(hasattr(period, 'gl_period'))
    
    def test_generate_preview_periods(self):
        """Test generate-preview endpoint."""
        data = {
            'start_date': '2026-01-01',
            'fiscal_year': 2026,
            'num_periods': 12,
            'num_adjustment_periods': 1,
            'adjustment_period_days': 5
        }
        
        response = self.client.post(
            '/finance/period/periods/generate-preview/',
            data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['total_periods'], 13)  # 12 + 1 adjustment
        self.assertEqual(len(response.data['data']['periods']), 13)
    
    def test_open_close_ar_period(self):
        """Test opening and closing AR period."""
        period = Period.objects.create(
            name='April 2026',
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 30),
            fiscal_year=2026,
            period_number=4
        )
        
        # Open AR period
        response = self.client.post(
            f'/finance/period/ar-periods/{period.ar_period.id}/open/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        period.ar_period.refresh_from_db()
        self.assertEqual(period.ar_period.state, 'open')
        
        # Close AR period
        response = self.client.post(
            f'/finance/period/ar-periods/{period.ar_period.id}/close/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        period.ar_period.refresh_from_db()
        self.assertEqual(period.ar_period.state, 'closed')
