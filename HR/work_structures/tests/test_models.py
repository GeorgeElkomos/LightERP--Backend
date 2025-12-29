"""
HR Models Unit Tests

Comprehensive unit tests for all HR models including:
- Enterprise, BusinessGroup, Location models
- Department and DepartmentManager models with date tracking
- Position model with reporting hierarchy
- Grade and GradeRate models with validation
- UserDataScope model for security scoping
- Date tracking validation and constraints
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta, date
from django.contrib.auth import get_user_model

from HR.work_structures.models import (
    Enterprise,
    BusinessGroup,
    Location,
    Department,
    DepartmentManager,
    Position,
    Grade,
    GradeRateType,
    GradeRate,
    UserDataScope,
    StatusChoices
)

User = get_user_model()


class EnterpriseModelTests(TestCase):
    """Test Enterprise model functionality"""
    
    def test_create_enterprise(self):
        """Test creating an enterprise with valid data"""
        enterprise = Enterprise.objects.create(
            code='ENT001',
            name='Test Enterprise',
            effective_start_date=date(2024, 1, 1)
        )
        
        self.assertEqual(enterprise.code, 'ENT001')
        self.assertEqual(enterprise.name, 'Test Enterprise')
        # Status should be active since today is > 2024-01-01 and no end date
        self.assertEqual(enterprise.status, StatusChoices.ACTIVE)
    
    def test_enterprise_unique_version(self):
        """Test that enterprise code + start_date must be unique (versioning)"""
        Enterprise.objects.create(
            code='ENT001', 
            name='Enterprise 1',
            effective_start_date=date(2024, 1, 1)
        )
        
        with self.assertRaises(Exception):
            # Same code, same start date
            Enterprise.objects.create(
                code='ENT001', 
                name='Enterprise 2',
                effective_start_date=date(2024, 1, 1)
            )
    
    def test_enterprise_deactivate(self):
        """Test deactivating an enterprise"""
        enterprise = Enterprise.objects.create(
            code='ENT001', 
            name='Test Enterprise',
            effective_start_date=date(2024, 1, 1)
        )
        enterprise.deactivate()
        
        self.assertEqual(enterprise.status, StatusChoices.INACTIVE)
        self.assertIsNotNone(enterprise.effective_end_date)
    
    def test_enterprise_str(self):
        """Test string representation"""
        enterprise = Enterprise.objects.create(
            code='ENT001', 
            name='Test Enterprise',
            effective_start_date=date(2024, 1, 1)
        )
        self.assertEqual(str(enterprise), 'ENT001 - Test Enterprise')


class BusinessGroupModelTests(TestCase):
    """Test BusinessGroup model functionality"""
    
    def setUp(self):
        self.enterprise = Enterprise.objects.create(
            code='ENT001',
            name='Test Enterprise',
            effective_start_date=date(2024, 1, 1)
        )
    
    def test_create_business_group(self):
        """Test creating a business group with valid data"""
        bg = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Egypt Operations',
            effective_start_date=date(2024, 1, 1)
        )
        
        self.assertEqual(bg.code, 'BG001')
        self.assertEqual(bg.enterprise, self.enterprise)
        self.assertEqual(bg.status, StatusChoices.ACTIVE)
    
    def test_business_group_unique_version_per_enterprise(self):
        """Test that code + start_date must be unique within an enterprise"""
        BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Group 1',
            effective_start_date=date(2024, 1, 1)
        )
        
        with self.assertRaises(Exception):
            BusinessGroup.objects.create(
                enterprise=self.enterprise,
                code='BG001',
                name='Group 2',
                effective_start_date=date(2024, 1, 1)
            )
    
    def test_business_group_same_code_different_enterprise(self):
        """Test that same code is allowed for different enterprises"""
        enterprise2 = Enterprise.objects.create(
            code='ENT002', 
            name='Enterprise 2',
            effective_start_date=date(2024, 1, 1)
        )
        
        bg1 = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Group 1',
            effective_start_date=date(2024, 1, 1)
        )
        
        bg2 = BusinessGroup.objects.create(
            enterprise=enterprise2,
            code='BG001',
            name='Group 2',
            effective_start_date=date(2024, 1, 1)
        )
        
        self.assertIsNotNone(bg1)
        self.assertIsNotNone(bg2)
    
    def test_business_group_str(self):
        """Test string representation"""
        bg = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Egypt Operations',
            effective_start_date=date(2024, 1, 1)
        )
        self.assertEqual(str(bg), 'ENT001.BG001 - Egypt Operations')


class LocationModelTests(TestCase):
    """Test Location model functionality"""
    
    def setUp(self):
        self.enterprise = Enterprise.objects.create(code='ENT001', name='Test Enterprise', effective_start_date=date(2024, 1, 1))
        self.business_group = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Egypt Operations', effective_start_date=date(2024, 1, 1)
        )
    
    def test_create_location(self):
        """Test creating a location with valid data"""
        location = Location.objects.create(
            business_group=self.business_group,
            code='LOC001',
            name='Cairo Office',
            address_details='123 Main St, Cairo',
            country='Egypt'
        )
        
        self.assertEqual(location.code, 'LOC001')
        self.assertEqual(location.name, 'Cairo Office')
        self.assertEqual(location.country, 'Egypt')
    
    def test_location_unique_code(self):
        """Test that location code must be unique"""
        Location.objects.create(
            code='LOC001',
            name='Location 1',
            country='Egypt',
            business_group=self.business_group
        )
        
        with self.assertRaises(Exception):
            Location.objects.create(
                code='LOC001',
                name='Location 2',
                country='Egypt',
                business_group=self.business_group
            )


class DepartmentModelTests(TestCase):
    """Test Department model with date tracking functionality"""
    
    def setUp(self):
        self.enterprise = Enterprise.objects.create(code='ENT001', name='Test Enterprise', effective_start_date=date(2024, 1, 1))
        self.business_group = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Egypt Operations', effective_start_date=date(2024, 1, 1)
        )
        self.location = Location.objects.create(
            code='LOC001',
            name='Cairo Office',
            country='Egypt',
            business_group=self.business_group
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
        from HR.work_structures.serializers.department_serializers import DepartmentManagerSerializer
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
        """Test creating a department with valid data"""
        dept = Department.objects.create(
            code='DEPT001',
            business_group=self.business_group,
            name='IT Department',
            location=self.location,
            effective_start_date=date(2024, 1, 1)
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
        
        currently_active = Department.objects.active()
        
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
    """Test Position model with date tracking functionality"""
    
    def setUp(self):
        self.enterprise = Enterprise.objects.create(code='ENT001', name='Test Enterprise', effective_start_date=date(2024, 1, 1))
        self.business_group = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Egypt Operations', effective_start_date=date(2024, 1, 1)
        )
        self.location = Location.objects.create(
            code='LOC001',
            name='Cairo Office',
            country='Egypt',
            business_group=self.business_group
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
        """Test creating a position with valid data"""
        position = Position.objects.create(
            code='POS001',
            name='Software Engineer',
            department=self.department,
            location=self.location,
            grade=self.grade,
            effective_start_date=date(2024, 1, 1)
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
    """Test Grade and GradeRate models functionality"""
    
    def setUp(self):
        self.enterprise = Enterprise.objects.create(code='ENT001', name='Test Enterprise', effective_start_date=date(2024, 1, 1))
        self.business_group = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Egypt Operations', effective_start_date=date(2024, 1, 1)
        )
    
    def test_create_grade(self):
        """Test creating a grade with valid data"""
        grade = Grade.objects.create(
            code='G1',
            name='Grade 1',
            business_group=self.business_group,
            effective_start_date=date(2024, 1, 1)
        )
        
        self.assertEqual(grade.code, 'G1')
        self.assertEqual(grade.name, 'Grade 1')
    
    def test_create_grade_rate_range(self):
        """Test creating a range-based grade rate level"""
        grade = Grade.objects.create(
            code='G1',
            name='Grade 1',
            business_group=self.business_group,
            effective_start_date=date(2024, 1, 1)
        )
        
        # Create rate type
        rate_type = GradeRateType.objects.create(
            code='BASIC_SALARY',
            name='Basic Salary',
            has_range=True
        )
        
        # Create range-based rate level
        rate = GradeRate.objects.create(
            grade=grade,
            rate_type=rate_type,
            min_amount=5000.00,
            max_amount=8000.00,
            currency='EGP',
            effective_start_date=date(2024, 1, 1)
        )
        
        self.assertEqual(rate.min_amount, 5000.00)
        self.assertEqual(rate.max_amount, 8000.00)
        self.assertEqual(rate.currency, 'EGP')
        self.assertEqual(rate.grade, grade)
    
    def test_create_grade_rate_fixed(self):
        """Test creating a fixed-value grade rate level"""
        grade = Grade.objects.create(
            code='G1',
            name='Grade 1',
            business_group=self.business_group,
            effective_start_date=date(2024, 1, 1)
        )
        
        # Create rate type
        rate_type = GradeRateType.objects.create(
            code='TRANSPORT',
            name='Transportation Allowance',
            has_range=False
        )
        
        # Create fixed-value rate level
        rate = GradeRate.objects.create(
            grade=grade,
            rate_type=rate_type,
            fixed_amount=500.00,
            currency='EGP',
            effective_start_date=date(2024, 1, 1)
        )
        
        self.assertEqual(rate.fixed_amount, 500.00)
        self.assertEqual(rate.currency, 'EGP')
        self.assertEqual(rate.grade, grade)
    
    def test_grade_rate_validation(self):
        """Test that grade rate level validation works correctly"""
        grade = Grade.objects.create(
            code='G1',
            name='Grade 1',
            business_group=self.business_group,
            effective_start_date=date(2024, 1, 1)
        )
        
        rate_type = GradeRateType.objects.create(
            code='BASIC_SALARY',
            name='Basic Salary',
            has_range=True
        )
        
        # Range-based rate must have min and max amounts
        rate = GradeRate(
            grade=grade,
            rate_type=rate_type,
            fixed_amount=5000.00,  # Wrong: using fixed_amount for range type
            currency='EGP',
            effective_start_date=date(2024, 1, 1)
        )
        
        with self.assertRaises(ValidationError):
            rate.clean()


class UserDataScopeModelTests(TestCase):
    """Test UserDataScope model functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            name='Test User',
            phone_number='+201234567890',
            password='testpass123'
        )
        self.enterprise = Enterprise.objects.create(code='ENT001', name='Test Enterprise', effective_start_date=date(2024, 1, 1))
        self.business_group = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Egypt Operations', effective_start_date=date(2024, 1, 1)
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
        """Test that user + business_group + department combination must be unique"""
        from django.db import IntegrityError
        
        # Create a department for testing
        dept = Department.objects.create(
            code='DEPT001',
            business_group=self.business_group,
            name='IT Department',
            location=Location.objects.create(
                code='TESTLOC',
                name='Test Location',
                country='Egypt',
                business_group=self.business_group
            ),
            effective_start_date=date(2024, 1, 1)
        )
        
        # Create first scope
        UserDataScope.objects.create(
            user=self.user,
            business_group=self.business_group,
            department=dept
        )
        
        # Should fail when creating duplicate scope
        with self.assertRaises(IntegrityError):
            UserDataScope.objects.create(
                user=self.user,
                business_group=self.business_group,
                department=dept
            )


class DateTrackingValidationTests(TestCase):
    """Test date tracking validation functionality"""
    
    def setUp(self):
        self.enterprise = Enterprise.objects.create(code='ENT001', name='Test Enterprise', effective_start_date=date(2024, 1, 1))
        self.business_group = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Egypt Operations', effective_start_date=date(2024, 1, 1)
        )
    
    def test_end_date_before_start_date_validation(self):
        """Test that end date cannot be before start date"""
        dept = Department(
            code='DEPT001',
            business_group=self.business_group,
            name='Test Department',
            location=Location.objects.create(
                code='TESTLOC',
                name='Test Location',
                country='Egypt',
                business_group=self.business_group
            ),
            effective_start_date=date(2024, 1, 1),
            effective_end_date=date(2023, 12, 31)  # End before start
        )
        
        with self.assertRaises(ValidationError):
            dept.clean()
    
    def test_overlapping_date_ranges(self):
        """Test validation for overlapping date ranges"""
        location = Location.objects.create(
            code='TESTLOC',
            name='Test Location',
            country='Egypt',
            business_group=self.business_group
        )
        
        # Create first department version
        Department.objects.create(
            code='DEPT001',
            business_group=self.business_group,
            name='Test Department',
            location=location,
            effective_start_date=date(2024, 1, 1),
            effective_end_date=date(2024, 6, 30)
        )
        
        # Try to create overlapping department
        overlapping_dept = Department(
            code='DEPT001',
            business_group=self.business_group,
            name='Test Department Updated',
            location=location,
            effective_start_date=date(2024, 3, 1),  # Overlaps with existing
            effective_end_date=date(2024, 9, 30)
        )
        
        with self.assertRaises(ValidationError):
            overlapping_dept.clean()


class SerializerValidationTests(TestCase):
    """Validation and flexible lookup rules via serializers"""
    
    def setUp(self):
        self.enterprise = Enterprise.objects.create(code='ENT001', name='Test Ent', effective_start_date=date(2024,1,1))
        self.bg = BusinessGroup.objects.create(enterprise=self.enterprise, code='BG001', name='BG', effective_start_date=date(2024,1,1))
        self.location = Location.objects.create(business_group=self.bg, code='LOC1', name='Loc', country='EG')
        self.dept = Department.objects.create(code='DEPT1', business_group=self.bg, name='Dept', location=self.location, effective_start_date=date(2024,1,1))
        self.grade = Grade.objects.create(code='G1', business_group=self.bg, name='Grade 1', effective_start_date=date(2024,1,1))
    
    def test_business_group_create_serializer_enterprise_code_lookup(self):
        from HR.work_structures.serializers.structure_serializers import BusinessGroupCreateSerializer
        ser = BusinessGroupCreateSerializer(data={'name': 'New BG', 'enterprise_code': 'ENT001'})
        self.assertTrue(ser.is_valid(), ser.errors)
        dto = ser.to_dto()
        self.assertEqual(dto.enterprise_id, self.enterprise.id)
    
    def test_location_create_serializer_requires_either_ent_or_bg(self):
        from HR.work_structures.serializers.structure_serializers import LocationCreateSerializer
        ser = LocationCreateSerializer(data={'name': 'LocX', 'country': 'EG'})
        self.assertFalse(ser.is_valid())
        # Check for validation error in either '__all__' or 'non_field_errors'
        self.assertTrue('__all__' in ser.errors or 'non_field_errors' in ser.errors)
    
    def test_location_create_serializer_bg_code_lookup_and_active_validation(self):
        from HR.work_structures.models import StatusChoices
        from HR.work_structures.serializers.structure_serializers import LocationCreateSerializer
        # Deactivate BG to trigger validation
        self.bg.effective_end_date = date(2024,12,31)
        self.bg.save()
        ser = LocationCreateSerializer(data={'name': 'LocY', 'country': 'EG', 'business_group_code': 'BG001'})
        self.assertFalse(ser.is_valid())
        self.assertIn('business_group_code', ser.errors)
    
    def test_department_create_serializer_location_and_parent_code_lookups(self):
        from HR.work_structures.serializers.department_serializers import DepartmentCreateSerializer
        # Create child under existing dept using codes
        ser = DepartmentCreateSerializer(data={
            'name': 'Child Dept',
            'business_group_code': 'BG001',
            'location_code': 'LOC1',
            'parent_code': 'DEPT1'
        })
        self.assertTrue(ser.is_valid(), ser.errors)
        dto = ser.to_dto()
        self.assertEqual(dto.business_group_id, self.bg.id)
        self.assertEqual(dto.location_id, self.location.id)
        self.assertEqual(dto.parent_id, self.dept.id)
    
    def test_position_create_serializer_requires_all_fk_and_supports_code_lookups(self):
        from HR.work_structures.serializers.position_serializers import PositionCreateSerializer
        ser = PositionCreateSerializer(data={
            'name': 'Engineer',
            'department_code': 'DEPT1',
            'location_code': 'LOC1',
            'grade_code': 'G1'
        })
        self.assertTrue(ser.is_valid(), ser.errors)
        dto = ser.to_dto()
        self.assertEqual(dto.department_id, self.dept.id)
        self.assertEqual(dto.location_id, self.location.id)
        self.assertEqual(dto.grade_id, self.grade.id)
    
    def test_user_data_scope_create_serializer_rules(self):
        from HR.work_structures.serializers.security_serializers import UserDataScopeCreateSerializer
        # Create user
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.create_user(email='scope@test.com', name='Scope', phone_number='+201000000009', password='pass123')
        # Global cannot include bg/department
        ser1 = UserDataScopeCreateSerializer(data={'user': user.id, 'is_global': True, 'business_group': self.bg.id})
        self.assertFalse(ser1.is_valid())
        # Dept requires BG
        ser2 = UserDataScopeCreateSerializer(data={'user': user.id, 'department': self.dept.id})
        self.assertFalse(ser2.is_valid())
        # Valid BG scope
        ser3 = UserDataScopeCreateSerializer(data={'user_email': 'scope@test.com', 'business_group_code': 'BG001'})
        self.assertTrue(ser3.is_valid(), ser3.errors)
