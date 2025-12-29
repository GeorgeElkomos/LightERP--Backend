"""
HR Services Unit Tests

Comprehensive unit tests for all HR service layer functions including:
- DepartmentService: Department creation, updates, hierarchy management
- PositionService: Position creation, updates, reporting hierarchy
- GradeService: Grade and grade rate management
- Data scope enforcement and validation
- Business logic and permission checks
"""

from django.test import TestCase
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib.auth import get_user_model
from datetime import date

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
    UserDataScope
)
from HR.work_structures.services import DepartmentService, PositionService, GradeService
from HR.work_structures.dtos import (
    DepartmentCreateDTO,
    DepartmentUpdateDTO,
    PositionCreateDTO,
    PositionUpdateDTO,
    GradeCreateDTO,
    GradeRateCreateDTO
)

User = get_user_model()


class DepartmentServiceTests(TestCase):
    """Test DepartmentService business logic and data scope enforcement"""
    
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
        self.location = Location.objects.create(
            code='LOC001',
            name='Cairo Office',
            country='Egypt',
            business_group=self.business_group
        )
        
        # Give user access to this business group
        UserDataScope.objects.create(
            user=self.user,
            business_group=self.business_group,
            is_global=False
        )
    
    def test_create_department_success(self):
        """Test successful department creation with valid data scope"""
        dto = DepartmentCreateDTO(
            business_group_id=self.business_group.id,
            code='DEPT001',
            name='IT Department',
            location_id=self.location.id,
            effective_start_date=date(2024, 1, 1)
        )
        
        dept = DepartmentService.create_department(self.user, dto)
        
        self.assertIsNotNone(dept)
        self.assertEqual(dept.code, 'DEPT001')
        self.assertEqual(dept.name, 'IT Department')
        self.assertIsNone(dept.effective_end_date)
    
    def test_create_department_without_data_scope(self):
        """Test that creating department without data scope fails with PermissionDenied"""
        other_bg = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG002',
            name='Saudi Operations', effective_start_date=date(2024, 1, 1)
        )
        
        # Create a location for the other BG
        other_location = Location.objects.create(
            code='LOC002',
            name='Riyadh Office',
            country='Saudi Arabia',
            business_group=other_bg
        )
        
        dto = DepartmentCreateDTO(
            business_group_id=other_bg.id,
            code='DEPT001',
            name='IT Department',
            location_id=other_location.id,
            effective_start_date=date(2024, 1, 1)
        )
        
        with self.assertRaises(PermissionDenied):
            DepartmentService.create_department(self.user, dto)
    
    def test_create_department_with_parent(self):
        """Test creating department with parent hierarchy"""
        parent = Department.objects.create(
            code='PARENT',
            business_group=self.business_group,
            name='Parent Department',
            location=self.location,
            effective_start_date=date(2024, 1, 1)
        )
        
        dto = DepartmentCreateDTO(
            business_group_id=self.business_group.id,
            code='CHILD',
            name='Child Department',
            location_id=self.location.id,
            parent_id=parent.id,
            effective_start_date=date(2024, 1, 1)
        )
        
        dept = DepartmentService.create_department(self.user, dto)
        
        self.assertEqual(dept.parent, parent)
    
    def test_update_department_creates_new_version(self):
        """Test that updating creates a new version with date tracking"""
        # Create initial version
        dept = Department.objects.create(
            code='DEPT001',
            business_group=self.business_group,
            name='IT Department',
            location=self.location,
            effective_start_date=date(2024, 1, 1)
        )
        
        # Update
        dto = DepartmentUpdateDTO(
            code='DEPT001',
            name='IT Department Updated',
            effective_start_date=date(2024, 7, 1)
        )
        
        new_version = DepartmentService.update_department(self.user, dto)
        
        # Check old version is end-dated
        dept.refresh_from_db()
        self.assertIsNotNone(dept.effective_end_date)
        self.assertEqual(dept.effective_end_date, date(2024, 6, 30))
        
        # Check new version
        self.assertEqual(new_version.name, 'IT Department Updated')
        self.assertEqual(new_version.effective_start_date, date(2024, 7, 1))
        self.assertIsNone(new_version.effective_end_date)
    
    def test_get_department_tree(self):
        """Test getting department hierarchy tree structure"""
        # Create parent
        parent = Department.objects.create(
            code='PARENT',
            business_group=self.business_group,
            name='Parent Department',
            location=self.location,
            effective_start_date=date(2024, 1, 1)
        )
        
        # Create children
        child1 = Department.objects.create(
            code='CHILD1',
            business_group=self.business_group,
            name='Child 1',
            location=self.location,
            parent=parent,
            effective_start_date=date(2024, 1, 1)
        )
        
        child2 = Department.objects.create(
            code='CHILD2',
            business_group=self.business_group,
            name='Child 2',
            location=self.location,
            parent=parent,
            effective_start_date=date(2024, 1, 1)
        )
        
        tree = DepartmentService.get_department_tree(self.user, self.business_group.id)
        
        self.assertEqual(len(tree), 1)
        self.assertEqual(tree[0]['code'], 'PARENT')
        self.assertEqual(len(tree[0]['children']), 2)
    
    def test_circular_reference_validation(self):
        """Test that circular department references are prevented"""
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
        
        # Try to make parent a child of child (circular)
        dto = DepartmentUpdateDTO(
            code='PARENT',
            parent_id=child.id,
            effective_start_date=date(2024, 7, 1)
        )
        
        with self.assertRaises(ValidationError):
            DepartmentService.update_department(self.user, dto)


class PositionServiceTests(TestCase):
    """Test PositionService business logic and reporting hierarchy"""
    
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
        
        # Give user access
        UserDataScope.objects.create(
            user=self.user,
            business_group=self.business_group,
            is_global=False
        )
    
    def test_create_position_success(self):
        """Test successful position creation with valid data"""
        dto = PositionCreateDTO(
            code='POS001',
            name='Software Engineer',
            department_id=self.department.id,
            location_id=self.location.id,
            grade_id=self.grade.id,
            effective_start_date=date(2024, 1, 1)
        )
        
        position = PositionService.create_position(self.user, dto)
        
        self.assertIsNotNone(position)
        self.assertEqual(position.code, 'POS001')
        self.assertEqual(position.name, 'Software Engineer')
    
    def test_create_position_with_reporting_line(self):
        """Test creating position with reports_to hierarchy"""
        manager = Position.objects.create(
            code='MGR001',
            name='Engineering Manager',
            department=self.department,
            location=self.location,
            grade=self.grade,
            effective_start_date=date(2024, 1, 1)
        )
        
        dto = PositionCreateDTO(
            code='ENG001',
            name='Software Engineer',
            department_id=self.department.id,
            location_id=self.location.id,
            grade_id=self.grade.id,
            reports_to_id=manager.id,
            effective_start_date=date(2024, 1, 1)
        )
        
        position = PositionService.create_position(self.user, dto)
        
        self.assertEqual(position.reports_to, manager)
    
    def test_update_position_creates_new_version(self):
        """Test that updating creates a new version with date tracking"""
        position = Position.objects.create(
            code='POS001',
            name='Software Engineer',
            department=self.department,
            location=self.location,
            grade=self.grade,
            effective_start_date=date(2024, 1, 1)
        )
        
        dto = PositionUpdateDTO(
            code='POS001',
            name='Senior Software Engineer',
            effective_start_date=date(2024, 7, 1)
        )
        
        new_version = PositionService.update_position(self.user, dto)
        
        # Check old version is end-dated
        position.refresh_from_db()
        self.assertIsNotNone(position.effective_end_date)
        
        # Check new version
        self.assertEqual(new_version.name, 'Senior Software Engineer')
        self.assertIsNone(new_version.effective_end_date)
    
    def test_get_position_hierarchy(self):
        """Test getting position reporting hierarchy structure"""
        # Create manager
        manager = Position.objects.create(
            code='MGR001',
            name='Engineering Manager',
            department=self.department,
            location=self.location,
            grade=self.grade,
            effective_start_date=date(2024, 1, 1)
        )
        
        # Create reporting positions
        eng1 = Position.objects.create(
            code='ENG001',
            name='Engineer 1',
            department=self.department,
            location=self.location,
            grade=self.grade,
            reports_to=manager,
            effective_start_date=date(2024, 1, 1)
        )
        
        eng2 = Position.objects.create(
            code='ENG002',
            name='Engineer 2',
            department=self.department,
            location=self.location,
            grade=self.grade,
            reports_to=manager,
            effective_start_date=date(2024, 1, 1)
        )
        
        hierarchy = PositionService.get_position_hierarchy(self.user, self.business_group.id)
        
        self.assertEqual(len(hierarchy), 1)
        self.assertEqual(hierarchy[0]['code'], 'MGR001')
        self.assertEqual(len(hierarchy[0]['direct_reports']), 2)
    
    def test_circular_reporting_line_validation(self):
        """Test that circular reporting lines are prevented"""
        pos1 = Position.objects.create(
            code='POS001',
            name='Position 1',
            department=self.department,
            location=self.location,
            grade=self.grade,
            effective_start_date=date(2024, 1, 1)
        )
        
        pos2 = Position.objects.create(
            code='POS002',
            name='Position 2',
            department=self.department,
            location=self.location,
            grade=self.grade,
            reports_to=pos1,
            effective_start_date=date(2024, 1, 1)
        )
        
        # Try to make pos1 report to pos2 (circular)
        dto = PositionUpdateDTO(
            code='POS001',
            reports_to_id=pos2.id,
            effective_start_date=date(2024, 7, 1)
        )
        
        with self.assertRaises(ValidationError):
            PositionService.update_position(self.user, dto)


class GradeServiceTests(TestCase):
    """Test GradeService business logic and grade rate management"""
    
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
        
        # Give user access
        UserDataScope.objects.create(
            user=self.user,
            business_group=self.business_group,
            is_global=False
        )
    
    def test_create_grade_success(self):
        """Test successful grade creation with valid data"""
        dto = GradeCreateDTO(
            code='G1',
            name='Grade 1',
            business_group_id=self.business_group.id,
            effective_start_date=date(2024, 1, 1)
        )
        
        grade = GradeService.create_grade(self.user, dto)
        
        self.assertIsNotNone(grade)
        self.assertEqual(grade.code, 'G1')
        self.assertEqual(grade.name, 'Grade 1')
    
    def test_create_grade_without_data_scope(self):
        """Test that creating grade without data scope fails with PermissionDenied"""
        other_bg = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG002',
            name='Saudi Operations', effective_start_date=date(2024, 1, 1)
        )
        
        dto = GradeCreateDTO(
            code='G1',
            name='Grade 1',
            business_group_id=other_bg.id,
            effective_start_date=date(2024, 1, 1)
        )
        
        with self.assertRaises(PermissionDenied):
            GradeService.create_grade(self.user, dto)
    
    def test_create_grade_rate_success(self):
        """Test successful grade rate level creation"""
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
        
        dto = GradeRateCreateDTO(
            grade_id=grade.id,
            rate_type_id=rate_type.id,
            min_amount=5000.00,
            max_amount=8000.00,
            currency='EGP',
            effective_start_date=date(2024, 1, 1)
        )
        
        rate = GradeService.create_grade_rate(self.user, dto)
        
        self.assertIsNotNone(rate)
        self.assertEqual(rate.min_amount, 5000.00)
        self.assertEqual(rate.max_amount, 8000.00)
        self.assertEqual(rate.rate_type, rate_type)
    
    def test_create_grade_rate_with_end_date(self):
        """Test creating grade rate level with end date"""
        grade = Grade.objects.create(
            code='G1',
            name='Grade 1',
            business_group=self.business_group,
            effective_start_date=date(2024, 1, 1)
        )
        
        rate_type = GradeRateType.objects.create(
            code='TRANSPORT',
            name='Transportation',
            has_range=False
        )
        
        dto = GradeRateCreateDTO(
            grade_id=grade.id,
            rate_type_id=rate_type.id,
            fixed_amount=500.00,
            currency='EGP',
            effective_start_date=date(2024, 1, 1),
            effective_end_date=date(2024, 12, 31)
        )
        
        rate = GradeService.create_grade_rate(self.user, dto)
        
        self.assertEqual(rate.effective_end_date, date(2024, 12, 31))


class DataScopeSuperuserTests(TestCase):
    """Test that superusers bypass data scope restrictions"""
    
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            email='admin@example.com',
            name='Super Admin',
            phone_number='+201111111111',
            password='adminpass123'
        )
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
    
    def test_superuser_can_create_without_scope(self):
        """Test that superusers can create without having data scope"""
        dto = DepartmentCreateDTO(
            business_group_id=self.business_group.id,
            code='DEPT001',
            name='IT Department',
            location_id=self.location.id,
            effective_start_date=date(2024, 1, 1)
        )
        
        # Should succeed even without UserDataScope
        dept = DepartmentService.create_department(self.superuser, dto)
        
        self.assertIsNotNone(dept)


class DataScopeGlobalAccessTests(TestCase):
    """Test global data scope access functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            name='Global User',
            phone_number='+201222222222',
            password='testpass123'
        )
        self.enterprise = Enterprise.objects.create(code='ENT001', name='Test Enterprise', effective_start_date=date(2024, 1, 1))
        self.bg1 = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Egypt Operations',
            effective_start_date=date(2024, 1, 1)
        )
        self.bg2 = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG002',
            name='Saudi Operations',
            effective_start_date=date(2024, 1, 1)
        )
        self.location1 = Location.objects.create(
            code='LOC001',
            name='Cairo Office',
            country='Egypt',
            business_group=self.bg1
        )
        self.location2 = Location.objects.create(
            code='LOC002',
            name='Riyadh Office',
            country='Saudi Arabia',
            business_group=self.bg2
        )
        
        # Give user global access
        UserDataScope.objects.create(
            user=self.user,
            is_global=True
        )
    
    def test_global_user_can_access_all_business_groups(self):
        """Test that users with global scope can access all business groups"""
        # Create in BG1
        dto1 = DepartmentCreateDTO(
            business_group_id=self.bg1.id,
            code='DEPT001',
            name='IT Department',
            location_id=self.location1.id,
            effective_start_date=date(2024, 1, 1)
        )
        
        dept1 = DepartmentService.create_department(self.user, dto1)
        self.assertIsNotNone(dept1)
        
        # Create in BG2
        dto2 = DepartmentCreateDTO(
            business_group_id=self.bg2.id,
            code='DEPT002',
            name='HR Department',
            location_id=self.location2.id,
            effective_start_date=date(2024, 1, 1)
        )
        
        dept2 = DepartmentService.create_department(self.user, dto2)
        self.assertIsNotNone(dept2)
