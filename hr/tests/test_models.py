"""
HR Models Tests

Comprehensive tests for all HR models including date tracking, validation, and relationships.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta, date
from django.contrib.auth import get_user_model

from hr.models import (
    Enterprise,
    BusinessGroup,
    Location,
    Department,
    DepartmentManager,
    Position,
    Grade,
    GradeRate,
    UserDataScope,
    StatusChoices
)

User = get_user_model()


class EnterpriseModelTests(TestCase):
    """Test Enterprise model"""
    
    def test_create_enterprise(self):
        """Test creating an enterprise"""
        enterprise = Enterprise.objects.create(
            code='ENT001',
            name='Test Enterprise',
            status=StatusChoices.ACTIVE
        )
        
        self.assertEqual(enterprise.code, 'ENT001')
        self.assertEqual(enterprise.name, 'Test Enterprise')
        self.assertEqual(enterprise.status, StatusChoices.ACTIVE)
        self.assertIsNotNone(enterprise.created_at)
    
    def test_enterprise_unique_code(self):
        """Test that enterprise code must be unique"""
        Enterprise.objects.create(code='ENT001', name='Enterprise 1')
        
        with self.assertRaises(Exception):
            Enterprise.objects.create(code='ENT001', name='Enterprise 2')
    
    def test_enterprise_deactivate(self):
        """Test deactivating an enterprise"""
        enterprise = Enterprise.objects.create(code='ENT001', name='Test Enterprise')
        enterprise.deactivate()
        
        self.assertEqual(enterprise.status, StatusChoices.INACTIVE)
    
    def test_enterprise_str(self):
        """Test string representation"""
        enterprise = Enterprise.objects.create(code='ENT001', name='Test Enterprise')
        self.assertEqual(str(enterprise), 'ENT001 - Test Enterprise')


class BusinessGroupModelTests(TestCase):
    """Test BusinessGroup model"""
    
    def setUp(self):
        self.enterprise = Enterprise.objects.create(
            code='ENT001',
            name='Test Enterprise'
        )
    
    def test_create_business_group(self):
        """Test creating a business group"""
        bg = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Egypt Operations',
            status=StatusChoices.ACTIVE
        )
        
        self.assertEqual(bg.code, 'BG001')
        self.assertEqual(bg.enterprise, self.enterprise)
        self.assertEqual(bg.status, StatusChoices.ACTIVE)
    
    def test_business_group_unique_code_per_enterprise(self):
        """Test that code must be unique within an enterprise"""
        BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Group 1'
        )
        
        with self.assertRaises(Exception):
            BusinessGroup.objects.create(
                enterprise=self.enterprise,
                code='BG001',
                name='Group 2'
            )
    
    def test_business_group_same_code_different_enterprise(self):
        """Test that same code is allowed for different enterprises"""
        enterprise2 = Enterprise.objects.create(code='ENT002', name='Enterprise 2')
        
        bg1 = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Group 1'
        )
        
        bg2 = BusinessGroup.objects.create(
            enterprise=enterprise2,
            code='BG001',
            name='Group 2'
        )
        
        self.assertIsNotNone(bg1)
        self.assertIsNotNone(bg2)
    
    def test_business_group_str(self):
        """Test string representation"""
        bg = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Egypt Operations'
        )
        self.assertEqual(str(bg), 'ENT001.BG001 - Egypt Operations')


class LocationModelTests(TestCase):
    """Test Location model"""
    
    def setUp(self):
        self.enterprise = Enterprise.objects.create(code='ENT001', name='Test Enterprise')
        self.business_group = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Egypt Operations'
        )
    
    def test_create_location(self):
        """Test creating a location"""
        location = Location.objects.create(
            enterprise=self.enterprise,
            business_group=self.business_group,
            code='LOC001',
            name='Cairo Office',
            address_line1='123 Main St',
            city='Cairo',
            country='Egypt',
            status=StatusChoices.ACTIVE
        )
        
        self.assertEqual(location.code, 'LOC001')
        self.assertEqual(location.city, 'Cairo')
        self.assertEqual(location.country, 'Egypt')
    
    def test_location_unique_code(self):
        """Test that location code must be unique"""
        Location.objects.create(
            code='LOC001',
            name='Location 1',
            country='Egypt'
        )
        
        with self.assertRaises(Exception):
            Location.objects.create(
                code='LOC001',
                name='Location 2',
                country='Egypt'
            )


class DepartmentModelTests(TestCase):
    """Test Department model with date tracking"""
    
    def setUp(self):
        self.enterprise = Enterprise.objects.create(code='ENT001', name='Test Enterprise')
        self.business_group = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Egypt Operations'
        )
        self.location = Location.objects.create(
            code='LOC001',
            name='Cairo Office',
            country='Egypt'
        )
    
    def test_department_managers_require_employee(self):
        """DepartmentManager creation should validate manager is an Employee if Employee model exists"""
        dept = Department.objects.create(
            code='DEPT001',
            business_group=self.business_group,
            name='IT Department',
            location=self.location,
            effective_start_date=date(2024, 1, 1)
        )
        # Create a user who is not an employee
        user = User.objects.create_user(
            email='nomemp@example.com',
            name='No Emp',
            phone_number='+201000000000',
            password='testpass'
        )
        data = {
            'department': dept.id,
            'manager': user.id,
            'effective_start_date': '2024-01-01'
        }
        
        from unittest.mock import patch, MagicMock
        from hr.serializers.department_serializers import DepartmentManagerSerializer
        with patch('django.apps.apps.get_model') as get_model_mock:
            # Simulate Employee model with no matching employee records
            EmployeeMock = MagicMock()
            qs_mock = MagicMock()
            qs_mock.exists.return_value = False
            EmployeeMock.objects.filter.return_value = qs_mock
            get_model_mock.return_value = EmployeeMock

            serializer = DepartmentManagerSerializer(data=data)
            self.assertFalse(serializer.is_valid())
            self.assertIn('manager', serializer.errors)

        # Now simulate Employee exists and is active
        with patch('django.apps.apps.get_model') as get_model_mock:
            EmployeeMock = MagicMock()
            qs_mock = MagicMock()
            # exists True
            qs_mock.exists.return_value = True
            emp = MagicMock()
            emp.is_active = True
            emp.effective_end_date = None
            qs_mock.order_by.return_value.first.return_value = emp
            EmployeeMock.objects.filter.return_value = qs_mock
            get_model_mock.return_value = EmployeeMock

            serializer = DepartmentManagerSerializer(data=data)
            self.assertTrue(serializer.is_valid())
    
    def test_create_department(self):
        """Test creating a department"""
        dept = Department.objects.create(
            code='DEPT001',
            business_group=self.business_group,
            name='IT Department',
            location=self.location,
            effective_start_date=date(2024, 1, 1),
            status=StatusChoices.ACTIVE
        )
        
        self.assertEqual(dept.code, 'DEPT001')
        self.assertEqual(dept.name, 'IT Department')
        self.assertIsNone(dept.effective_end_date)
    
    def test_department_date_tracking_unique_constraint(self):
        """Test unique constraint on BG + code + start_date"""
        Department.objects.create(
            code='DEPT001',
            business_group=self.business_group,
            name='IT Department',
            location=self.location,
            effective_start_date=date(2024, 1, 1)
        )
        
        # Should fail with same BG, code, and start date
        with self.assertRaises(Exception):
            Department.objects.create(
                code='DEPT001',
                business_group=self.business_group,
                name='IT Department Updated',
                location=self.location,
                effective_start_date=date(2024, 1, 1)
            )
    
    def test_department_currently_active(self):
        """Test currently_active() manager method"""
        # Create active department
        active_dept = Department.objects.create(
            code='DEPT001',
            business_group=self.business_group,
            name='Active Dept',
            location=self.location,
            effective_start_date=date(2024, 1, 1)
        )
        
        # Create inactive department (end-dated)
        inactive_dept = Department.objects.create(
            code='DEPT002',
            business_group=self.business_group,
            name='Inactive Dept',
            location=self.location,
            effective_start_date=date(2024, 1, 1),
            effective_end_date=date(2024, 6, 30)
        )
        
        currently_active = Department.objects.currently_active()
        
        self.assertIn(active_dept, currently_active)
        self.assertNotIn(inactive_dept, currently_active)
    
    def test_department_active_on_date(self):
        """Test active_on(date) manager method"""
        dept = Department.objects.create(
            code='DEPT001',
            business_group=self.business_group,
            name='IT Department',
            location=self.location,
            effective_start_date=date(2024, 1, 1),
            effective_end_date=date(2024, 12, 31)
        )
        
        # Should be active on dates within range
        active_in_range = Department.objects.active_on(date(2024, 6, 15))
        self.assertIn(dept, active_in_range)
        
        # Should not be active before start date
        active_before = Department.objects.active_on(date(2023, 12, 31))
        self.assertNotIn(dept, active_before)
        
        # Should not be active after end date
        active_after = Department.objects.active_on(date(2025, 1, 1))
        self.assertNotIn(dept, active_after)
    
    def test_department_hierarchy(self):
        """Test department parent-child relationship"""
        parent = Department.objects.create(
            code='PARENT',
            business_group=self.business_group,
            name='Parent Department',
            location=self.location,
            effective_start_date=date(2024, 1, 1)
        )
        
        child = Department.objects.create(
            code='CHILD',
            business_group=self.business_group,
            name='Child Department',
            location=self.location,
            parent=parent,
            effective_start_date=date(2024, 1, 1)
        )
        
        self.assertEqual(child.parent, parent)
        self.assertIn(child, parent.children.all())


class PositionModelTests(TestCase):
    """Test Position model with date tracking"""
    
    def setUp(self):
        self.enterprise = Enterprise.objects.create(code='ENT001', name='Test Enterprise')
        self.business_group = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Egypt Operations'
        )
        self.location = Location.objects.create(
            code='LOC001',
            name='Cairo Office',
            country='Egypt'
        )
        self.department = Department.objects.create(
            code='DEPT001',
            business_group=self.business_group,
            name='IT Department',
            location=self.location,
            effective_start_date=date(2024, 1, 1)
        )
        self.grade = Grade.objects.create(
            code='G1',
            name='Grade 1',
            business_group=self.business_group,
            effective_start_date=date(2024, 1, 1)
        )
    
    def test_create_position(self):
        """Test creating a position"""
        position = Position.objects.create(
            code='POS001',
            name='Software Engineer',
            department=self.department,
            location=self.location,
            grade=self.grade,
            effective_start_date=date(2024, 1, 1),
            status=StatusChoices.ACTIVE
        )
        
        self.assertEqual(position.code, 'POS001')
        self.assertEqual(position.name, 'Software Engineer')
        self.assertIsNone(position.effective_end_date)
    
    def test_position_reporting_hierarchy(self):
        """Test position reports_to relationship"""
        manager_pos = Position.objects.create(
            code='MGR001',
            name='Engineering Manager',
            department=self.department,
            location=self.location,
            grade=self.grade,
            effective_start_date=date(2024, 1, 1)
        )
        
        engineer_pos = Position.objects.create(
            code='ENG001',
            name='Software Engineer',
            department=self.department,
            location=self.location,
            grade=self.grade,
            reports_to=manager_pos,
            effective_start_date=date(2024, 1, 1)
        )
        
        self.assertEqual(engineer_pos.reports_to, manager_pos)
        self.assertIn(engineer_pos, manager_pos.direct_reports.all())


class GradeModelTests(TestCase):
    """Test Grade and GradeRate models"""
    
    def setUp(self):
        self.enterprise = Enterprise.objects.create(code='ENT001', name='Test Enterprise')
        self.business_group = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Egypt Operations'
        )
    
    def test_create_grade(self):
        """Test creating a grade"""
        grade = Grade.objects.create(
            code='G1',
            name='Grade 1',
            business_group=self.business_group,
            effective_start_date=date(2024, 1, 1)
        )
        
        self.assertEqual(grade.code, 'G1')
        self.assertEqual(grade.name, 'Grade 1')
    
    def test_create_grade_rate(self):
        """Test creating a grade rate"""
        grade = Grade.objects.create(
            code='G1',
            name='Grade 1',
            business_group=self.business_group,
            effective_start_date=date(2024, 1, 1)
        )
        
        rate = GradeRate.objects.create(
            grade=grade,
            rate_type='MIN_SALARY',
            amount=5000.00,
            currency='EGP',
            effective_start_date=date(2024, 1, 1)
        )
        
        self.assertEqual(rate.amount, 5000.00)
        self.assertEqual(rate.currency, 'EGP')
        self.assertEqual(rate.grade, grade)
    
    def test_grade_rate_positive_amount(self):
        """Test that grade rate amount must be positive"""
        grade = Grade.objects.create(
            code='G1',
            name='Grade 1',
            business_group=self.business_group,
            effective_start_date=date(2024, 1, 1)
        )
        
        rate = GradeRate(
            grade=grade,
            rate_type='MIN_SALARY',
            amount=-1000.00,
            currency='EGP',
            effective_start_date=date(2024, 1, 1)
        )
        
        with self.assertRaises(ValidationError):
            rate.clean()


class UserDataScopeModelTests(TestCase):
    """Test UserDataScope model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            name='Test User',
            phone_number='+201234567890',
            password='testpass123'
        )
        self.enterprise = Enterprise.objects.create(code='ENT001', name='Test Enterprise')
        self.business_group = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Egypt Operations'
        )
    
    def test_create_user_data_scope(self):
        """Test creating a user data scope"""
        scope = UserDataScope.objects.create(
            user=self.user,
            business_group=self.business_group,
            is_global=False
        )
        
        self.assertEqual(scope.user, self.user)
        self.assertEqual(scope.business_group, self.business_group)
        self.assertFalse(scope.is_global)
    
    def test_create_global_scope(self):
        """Test creating a global scope"""
        scope = UserDataScope.objects.create(
            user=self.user,
            is_global=True
        )
        
        self.assertTrue(scope.is_global)
        self.assertIsNone(scope.business_group)
    
    def test_unique_user_bg_scope(self):
        """Test that user + business_group combination must be unique"""
        UserDataScope.objects.create(
            user=self.user,
            business_group=self.business_group,
            is_global=False
        )
        
        with self.assertRaises(Exception):
            UserDataScope.objects.create(
                user=self.user,
                business_group=self.business_group,
                is_global=False
            )


class DateTrackingValidationTests(TestCase):
    """Test date tracking validation logic"""
    
    def setUp(self):
        self.enterprise = Enterprise.objects.create(code='ENT001', name='Test Enterprise')
        self.business_group = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Egypt Operations'
        )
        self.location = Location.objects.create(
            code='LOC001',
            name='Cairo Office',
            country='Egypt'
        )
    
    def test_end_date_before_start_date_validation(self):
        """Test that end_date cannot be before start_date"""
        dept = Department(
            code='DEPT001',
            business_group=self.business_group,
            name='IT Department',
            location=self.location,
            effective_start_date=date(2024, 12, 31),
            effective_end_date=date(2024, 1, 1)
        )
        
        with self.assertRaises(ValidationError):
            dept.clean()
    
    def test_overlapping_date_ranges(self):
        """Test that overlapping date ranges are prevented"""
        # Create first version
        Department.objects.create(
            code='DEPT001',
            business_group=self.business_group,
            name='IT Department',
            location=self.location,
            effective_start_date=date(2024, 1, 1),
            effective_end_date=date(2024, 12, 31)
        )
        
        # Try to create overlapping version
        overlapping_dept = Department(
            code='DEPT001',
            business_group=self.business_group,
            name='IT Department Updated',
            location=self.location,
            effective_start_date=date(2024, 6, 1),
            effective_end_date=date(2025, 6, 30)
        )
        
        with self.assertRaises(ValidationError):
            overlapping_dept.clean()
