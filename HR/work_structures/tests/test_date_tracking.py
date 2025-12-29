from django.test import TestCase
from django.contrib.auth import get_user_model
from datetime import date, timedelta
from HR.work_structures.models import Enterprise, BusinessGroup, Location, Department, Position, Grade, UserDataScope, StatusChoices
from HR.work_structures.services.department_service import DepartmentService
from HR.work_structures.services.position_service import PositionService
from HR.work_structures.services.grade_service import GradeService  
from HR.work_structures.dtos import DepartmentCreateDTO, DepartmentUpdateDTO, PositionCreateDTO, PositionUpdateDTO, GradeCreateDTO

from HR.work_structures.services.structure_service import StructureService
from HR.work_structures.dtos import (
    EnterpriseCreateDTO, EnterpriseUpdateDTO,
    BusinessGroupCreateDTO, BusinessGroupUpdateDTO
)

User = get_user_model()


class StructureDateTrackingTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(email='admin@test.com', name='Admin', phone_number='1234567890', password='password123')
        # We use StructureService to create to ensure proper behavior
        self.enterprise = StructureService.create_enterprise(self.user, EnterpriseCreateDTO(
            code='ENT1', name='Enterprise 1', effective_start_date=date(2024, 1, 1)
        ))
        self.business_group = StructureService.create_business_group(self.user, BusinessGroupCreateDTO(
            enterprise_id=self.enterprise.id, code='BG1', name='Business Group 1', effective_start_date=date(2024, 1, 1)
        ))

    def test_update_enterprise_creates_version(self):
        today = date.today()
        update_dto = EnterpriseUpdateDTO(code='ENT1', name='Enterprise 1 Updated', effective_start_date=today)
        new_version = StructureService.update_enterprise(self.user, update_dto)
        
        assert new_version.name == 'Enterprise 1 Updated'
        assert new_version.effective_start_date == today
        
        old_version = Enterprise.objects.get(pk=self.enterprise.pk)
        assert old_version.effective_end_date == today - timedelta(days=1)
        # It's now inactive because today > end_date
        assert old_version.status == StatusChoices.INACTIVE

    def test_update_business_group_creates_version(self):
        today = date.today()
        update_dto = BusinessGroupUpdateDTO(
            enterprise_id=self.enterprise.id, code='BG1', 
            name='Business Group 1 Updated', effective_start_date=today
        )
        new_version = StructureService.update_business_group(self.user, update_dto)
        
        assert new_version.name == 'Business Group 1 Updated'
        assert new_version.effective_start_date == today
        
        old_version = BusinessGroup.objects.get(pk=self.business_group.pk)
        assert old_version.effective_end_date == today - timedelta(days=1)


class DateTrackedEntityFixesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(email='admin@test.com', name='Admin', phone_number='1234567890', password='password123')
        self.enterprise = Enterprise.objects.create(code='TEST', name='Test Enterprise', effective_start_date=date(2024, 1, 1))
        self.business_group = BusinessGroup.objects.create(enterprise=self.enterprise, code='BG1', name='Business Group 1', effective_start_date=date(2024, 1, 1))
        self.location = Location.objects.create(enterprise=self.enterprise, code='LOC1', name='Location 1', country='Egypt', status='active')

    def test_create_department_with_end_date_active(self):
        today = date.today()
        dept = Department.objects.create(
            code='DEPT1', business_group=self.business_group, name='Department 1', location=self.location,
            effective_start_date=today - timedelta(days=30), effective_end_date=today + timedelta(days=30)
        )
        assert dept.status == StatusChoices.ACTIVE and dept.effective_end_date is not None

    def test_create_department_with_past_end_date_inactive(self):
        today = date.today()
        dept = Department.objects.create(
            code='DEPT2', business_group=self.business_group, name='Department 2', location=self.location,
            effective_start_date=today - timedelta(days=60), effective_end_date=today - timedelta(days=30)
        )
        assert dept.status == StatusChoices.INACTIVE and dept.effective_end_date is not None

    def test_update_department_creates_active_version(self):
        today = date.today()
        dto = DepartmentCreateDTO(
            business_group_id=self.business_group.id, code='DEPT3', name='Department 3', location_id=self.location.id,
            effective_start_date=today - timedelta(days=30)
        )
        dept = DepartmentService.create_department(self.user, dto)
        assert dept.status == StatusChoices.ACTIVE and dept.effective_end_date is None
        update_dto = DepartmentUpdateDTO(code='DEPT3', name='Department 3 Updated', effective_start_date=today)
        updated_dept = DepartmentService.update_department(self.user, update_dto)
        assert updated_dept.status == StatusChoices.ACTIVE and updated_dept.effective_end_date is None and updated_dept.effective_start_date == today
        old_dept = Department.objects.get(pk=dept.pk)
        assert old_dept.effective_end_date is not None and old_dept.effective_end_date == today - timedelta(days=1)

    def test_create_position_with_end_date(self):
        today = date.today()
        dept = Department.objects.create(code='DEPT4', business_group=self.business_group, name='Department 4', location=self.location, effective_start_date=today)
        grade = Grade.objects.create(code='GR1', business_group=self.business_group, name='Grade 1', effective_start_date=today)
        dto = PositionCreateDTO(
            code='POS1', name='Position 1', department_id=dept.id, location_id=self.location.id, grade_id=grade.id,
            effective_start_date=today, effective_end_date=today + timedelta(days=60)
        )
        position = PositionService.create_position(self.user, dto)
        assert position.status == StatusChoices.ACTIVE and position.effective_end_date == today + timedelta(days=60)

    def test_create_grade_with_end_date(self):
        today = date.today()
        dto = GradeCreateDTO(
            code='GR2', name='Grade 2', business_group_id=self.business_group.id,
            effective_start_date=today, effective_end_date=today + timedelta(days=90)
        )
        grade = GradeService.create_grade(self.user, dto)
        assert grade.status == StatusChoices.ACTIVE and grade.effective_end_date == today + timedelta(days=90)


class PatchEndDateTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(email='admin@test.com', name='Admin', phone_number='1234567890', password='password123')
        self.enterprise = Enterprise.objects.create(code='TEST', name='Test Enterprise', effective_start_date=date(2024, 1, 1))
        self.business_group = BusinessGroup.objects.create(enterprise=self.enterprise, code='BG1', name='Business Group 1', effective_start_date=date(2024, 1, 1))
        self.location = Location.objects.create(enterprise=self.enterprise, code='LOC1', name='Location 1', country='Egypt', status='active')
        self.department = Department.objects.create(code='DEPT1', business_group=self.business_group, name='Department 1', location=self.location, effective_start_date=date(2025, 1, 1))
        self.grade = Grade.objects.create(code='GR1', business_group=self.business_group, name='Grade 1', effective_start_date=date(2025, 1, 1))

    def test_patch_position_to_add_end_date(self):
        position = Position.objects.create(code='POS1', name='Position 1', department=self.department, location=self.location, grade=self.grade, effective_start_date=date(2025, 1, 1))
        assert position.effective_end_date is None and position.status == 'active'
        position.effective_end_date = date(2025, 6, 30)
        position.save()
        position.refresh_from_db()
        assert position.effective_end_date == date(2025, 6, 30)

    def test_patch_department_to_add_end_date(self):
        assert self.department.effective_end_date is None
        self.department.effective_end_date = date(2025, 12, 31)
        self.department.save()
        self.department.refresh_from_db()
        assert self.department.effective_end_date == date(2025, 12, 31)
        assert self.department.status == 'active'


class PatchWithDatesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(email='admin@test.com', name='Admin', phone_number='1234567890', password='password123')
        self.enterprise = Enterprise.objects.create(code='TEST', name='Test Enterprise', effective_start_date=date(2024, 1, 1))
        self.business_group = BusinessGroup.objects.create(enterprise=self.enterprise, code='BG1', name='Business Group 1', effective_start_date=date(2024, 1, 1))
        self.location = Location.objects.create(enterprise=self.enterprise, code='LOC1', name='Location 1', country='Egypt', status='active')
        self.department = Department.objects.create(code='DEPT1', business_group=self.business_group, name='Department 1', location=self.location, effective_start_date=date(2025, 1, 1))
        self.grade = Grade.objects.create(code='GR1', business_group=self.business_group, name='Grade 1', effective_start_date=date(2025, 1, 1))

    def test_patch_position_creates_version_with_dates(self):
        position = Position.objects.create(code='POS1', name='Position 1', department=self.department, location=self.location, grade=self.grade, effective_start_date=date(2025, 1, 1))
        dto = PositionUpdateDTO(code='POS1', name='Position 1 Updated', effective_start_date=date(2025, 7, 1), effective_end_date=date(2025, 12, 31))
        new_version = PositionService.update_position(self.user, dto)
        assert new_version.name == 'Position 1 Updated'
        assert new_version.effective_start_date == date(2025, 7, 1)
        assert new_version.effective_end_date == date(2025, 12, 31)
        assert new_version.status == 'active'
        old_version = Position.objects.get(pk=position.pk)
        assert old_version.effective_end_date == date(2025, 6, 30)

    def test_patch_department_creates_version_with_dates(self):
        dto = DepartmentUpdateDTO(code='DEPT1', name='Department 1 Updated', effective_start_date=date(2025, 3, 1), effective_end_date=date(2025, 8, 31))
        new_version = DepartmentService.update_department(self.user, dto)
        assert new_version.name == 'Department 1 Updated'
        assert new_version.effective_start_date == date(2025, 3, 1)
        assert new_version.effective_end_date == date(2025, 8, 31)
        assert new_version.status == 'inactive'
        old_version = Department.objects.get(pk=self.department.pk)
        assert old_version.effective_end_date == date(2025, 2, 28)

    def test_patch_without_end_date_creates_open_ended_version(self):
        position = Position.objects.create(code='POS2', name='Position 2', department=self.department, location=self.location, grade=self.grade, effective_start_date=date(2025, 1, 1))
        dto = PositionUpdateDTO(code='POS2', name='Position 2 Updated', effective_start_date=date(2025, 6, 1))
        new_version = PositionService.update_position(self.user, dto)
        assert new_version.effective_end_date is None and new_version.effective_start_date == date(2025, 6, 1)


class UpdatePositionWithEndDateTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(email='admin@test.com', name='Admin', phone_number='1234567890', password='password123')
        self.enterprise = Enterprise.objects.create(code='TEST', name='Test Enterprise', effective_start_date=date(2024, 1, 1))
        self.business_group = BusinessGroup.objects.create(enterprise=self.enterprise, code='BG1', name='Business Group 1', effective_start_date=date(2024, 1, 1))
        self.location = Location.objects.create(enterprise=self.enterprise, code='LOC1', name='Location 1', country='Egypt', status='active')
        self.department = Department.objects.create(code='DEPT1', business_group=self.business_group, name='Department 1', location=self.location, effective_start_date=date(2025, 1, 1))
        self.grade = Grade.objects.create(code='GR1', business_group=self.business_group, name='Grade 1', effective_start_date=date(2025, 1, 1))

    def test_update_position_with_future_end_date(self):
        today = date(2025, 12, 23)
        dto = PositionCreateDTO(code='SM3', name='Sales Manager', department_id=self.department.id, location_id=self.location.id, grade_id=self.grade.id, effective_start_date=date(2025, 1, 1), effective_end_date=date(2025, 12, 31))
        position = PositionService.create_position(self.user, dto)
        assert position.code == 'SM3' and position.status == 'active' and position.effective_end_date == date(2025, 12, 31)
        update_dto = PositionUpdateDTO(code='SM3', name='Senior Sales Manager', effective_start_date=today)
        updated_position = PositionService.update_position(self.user, update_dto)
        assert updated_position.name == 'Senior Sales Manager' and updated_position.code == 'SM3' and updated_position.status == 'active' and updated_position.effective_start_date == today and updated_position.effective_end_date == date(2025, 12, 31)
        old_position = Position.objects.get(pk=position.pk)
        assert old_position.effective_end_date == today - timedelta(days=1)


class DateTrackingWithScopingTests(TestCase):
    def setUp(self):
        from core.user_accounts.models import UserType
        self.user_type = UserType.objects.create(type_name='user')
        self.enterprise = Enterprise.objects.create(code='ENT001', name='Test Enterprise', effective_start_date=date(2024, 1, 1))
        self.bg = BusinessGroup.objects.create(enterprise=self.enterprise, code='EGY', name='Egypt Operations', effective_start_date=date(2024, 1, 1))
        self.location = Location.objects.create(business_group=self.bg, code='LOC_EGY', name='Cairo Office', country='Egypt')
        self.scoped_user = User.objects.create_user(email='scoped@test.com', name='Scoped User', phone_number='1234567890', password='test123')
        UserDataScope.objects.create(user=self.scoped_user, business_group=self.bg, is_global=False)

    def test_scoped_active_on_date(self):
        today = date.today()
        yesterday = today - timedelta(days=1)
        dept_old = Department.objects.create(
            business_group=self.bg, code='IT', name='IT Department Old', location=self.location,
            effective_start_date=yesterday - timedelta(days=10), effective_end_date=yesterday
        )
        dept_current = Department.objects.create(
            business_group=self.bg, code='IT', name='IT Department Current', location=self.location, effective_start_date=today
        )
        depts_current = Department.objects.scoped(self.scoped_user).active()
        assert depts_current.count() == 1 and depts_current.first() == dept_current
        depts_old = Department.objects.scoped(self.scoped_user).active_on(yesterday)
        assert depts_old.count() == 1 and depts_old.first() == dept_old

    def test_scoped_currently_active_chainable(self):
        today = date.today()
        dept1 = Department.objects.create(business_group=self.bg, code='IT', name='IT Department', location=self.location, effective_start_date=today)
        dept2 = Department.objects.create(business_group=self.bg, code='HR', name='HR Department', location=self.location, effective_start_date=today)
        depts = Department.objects.scoped(self.scoped_user).active()
        assert depts.count() == 2
        it_dept = depts.filter(code='IT')
        assert it_dept.count() == 1 and it_dept.first() == dept1


class UnifiedCorrectionVsVersioningTests(TestCase):
    """
    Test the unified correction vs. versioning logic across all date-tracked entities.
    
    Rules:
    - Correction Mode: effective_start_date NOT provided OR equals current date → updates existing record
    - Versioning Mode: effective_start_date provided AND different from current → end-dates old, creates new version
    """
    
    def setUp(self):
        self.user = User.objects.create_superuser(
            email='admin@test.com', 
            name='Admin', 
            phone_number='1234567890', 
            password='password123'
        )
        self.enterprise = Enterprise.objects.create(
            code='TEST', 
            name='Test Enterprise', 
            effective_start_date=date(2024, 1, 1)
        )
        self.business_group = BusinessGroup.objects.create(
            enterprise=self.enterprise, 
            code='BG1', 
            name='Business Group 1', 
            effective_start_date=date(2024, 1, 1)
        )
        self.location = Location.objects.create(
            enterprise=self.enterprise, 
            code='LOC1', 
            name='Location 1', 
            country='Egypt', 
            status='active'
        )
        self.grade = Grade.objects.create(
            code='GR1', 
            business_group=self.business_group, 
            name='Grade 1', 
            effective_start_date=date(2025, 1, 1)
        )
    
    # ========== ENTERPRISE TESTS ==========
    
    def test_enterprise_correction_without_date(self):
        """Test Enterprise: correction mode when effective_start_date NOT provided"""
        dto = EnterpriseUpdateDTO(code='TEST', name='Updated Name')
        updated = StructureService.update_enterprise(self.user, dto)
        
        # Should update the same record
        assert updated.id == self.enterprise.id
        assert updated.name == 'Updated Name'
        assert updated.effective_start_date == date(2024, 1, 1)  # Original date preserved
        
        # Should be only one version
        assert Enterprise.objects.filter(code='TEST').count() == 1
    
    def test_enterprise_correction_with_same_date(self):
        """Test Enterprise: correction mode when effective_start_date equals current"""
        dto = EnterpriseUpdateDTO(
            code='TEST', 
            name='Updated Name',
            effective_start_date=date(2024, 1, 1)  # Same as current
        )
        updated = StructureService.update_enterprise(self.user, dto)
        
        # Should update the same record
        assert updated.id == self.enterprise.id
        assert updated.name == 'Updated Name'
        assert updated.effective_start_date == date(2024, 1, 1)
        
        # Should be only one version
        assert Enterprise.objects.filter(code='TEST').count() == 1
    
    def test_enterprise_versioning_with_different_date(self):
        """Test Enterprise: versioning mode when effective_start_date different"""
        new_date = date(2025, 6, 1)
        dto = EnterpriseUpdateDTO(
            code='TEST', 
            name='Updated Name',
            effective_start_date=new_date
        )
        updated = StructureService.update_enterprise(self.user, dto)
        
        # Should create new version
        assert updated.id != self.enterprise.id
        assert updated.name == 'Updated Name'
        assert updated.effective_start_date == new_date
        
        # Should be two versions
        assert Enterprise.objects.filter(code='TEST').count() == 2
        
        # Old version should be end-dated
        self.enterprise.refresh_from_db()
        assert self.enterprise.effective_end_date == new_date - timedelta(days=1)
    
    # ========== BUSINESS GROUP TESTS ==========
    
    def test_business_group_correction_without_date(self):
        """Test BusinessGroup: correction mode when effective_start_date NOT provided"""
        dto = BusinessGroupUpdateDTO(
            enterprise_id=self.enterprise.id,
            code='BG1', 
            name='Updated BG Name'
        )
        updated = StructureService.update_business_group(self.user, dto)
        
        # Should update the same record
        assert updated.id == self.business_group.id
        assert updated.name == 'Updated BG Name'
        assert updated.effective_start_date == date(2024, 1, 1)
        
        # Should be only one version
        assert BusinessGroup.objects.filter(code='BG1').count() == 1
    
    def test_business_group_versioning_with_different_date(self):
        """Test BusinessGroup: versioning mode when effective_start_date different"""
        new_date = date(2025, 3, 1)
        dto = BusinessGroupUpdateDTO(
            enterprise_id=self.enterprise.id,
            code='BG1', 
            name='Updated BG Name',
            effective_start_date=new_date
        )
        updated = StructureService.update_business_group(self.user, dto)
        
        # Should create new version
        assert updated.id != self.business_group.id
        assert updated.name == 'Updated BG Name'
        assert updated.effective_start_date == new_date
        
        # Should be two versions
        assert BusinessGroup.objects.filter(code='BG1').count() == 2
        
        # Old version should be end-dated
        self.business_group.refresh_from_db()
        assert self.business_group.effective_end_date == new_date - timedelta(days=1)
    
    # ========== DEPARTMENT TESTS ==========
    
    def test_department_correction_without_date(self):
        """Test Department: correction mode when effective_start_date NOT provided"""
        dept = Department.objects.create(
            code='DEPT1',
            business_group=self.business_group,
            name='Department 1',
            location=self.location,
            effective_start_date=date(2025, 1, 1)
        )
        
        dto = DepartmentUpdateDTO(code='DEPT1', name='Updated Dept Name')
        updated = DepartmentService.update_department(self.user, dto)
        
        # Should update the same record
        assert updated.id == dept.id
        assert updated.name == 'Updated Dept Name'
        assert updated.effective_start_date == date(2025, 1, 1)
        
        # Should be only one version
        assert Department.objects.filter(code='DEPT1').count() == 1
    
    def test_department_versioning_with_different_date(self):
        """Test Department: versioning mode when effective_start_date different"""
        dept = Department.objects.create(
            code='DEPT2',
            business_group=self.business_group,
            name='Department 2',
            location=self.location,
            effective_start_date=date(2025, 1, 1)
        )
        
        new_date = date(2025, 7, 1)
        dto = DepartmentUpdateDTO(
            code='DEPT2', 
            name='Updated Dept Name',
            effective_start_date=new_date
        )
        updated = DepartmentService.update_department(self.user, dto)
        
        # Should create new version
        assert updated.id != dept.id
        assert updated.name == 'Updated Dept Name'
        assert updated.effective_start_date == new_date
        
        # Should be two versions
        assert Department.objects.filter(code='DEPT2').count() == 2
        
        # Old version should be end-dated
        dept.refresh_from_db()
        assert dept.effective_end_date == new_date - timedelta(days=1)
    
    # ========== POSITION TESTS ==========
    
    def test_position_correction_without_date(self):
        """Test Position: correction mode when effective_start_date NOT provided"""
        dept = Department.objects.create(
            code='DEPT3',
            business_group=self.business_group,
            name='Department 3',
            location=self.location,
            effective_start_date=date(2025, 1, 1)
        )
        position = Position.objects.create(
            code='POS1',
            name='Position 1',
            department=dept,
            location=self.location,
            grade=self.grade,
            effective_start_date=date(2025, 1, 1)
        )
        
        dto = PositionUpdateDTO(code='POS1', name='Updated Position Name')
        updated = PositionService.update_position(self.user, dto)
        
        # Should update the same record
        assert updated.id == position.id
        assert updated.name == 'Updated Position Name'
        assert updated.effective_start_date == date(2025, 1, 1)
        
        # Should be only one version
        assert Position.objects.filter(code='POS1').count() == 1
    
    def test_position_versioning_with_different_date(self):
        """Test Position: versioning mode when effective_start_date different"""
        dept = Department.objects.create(
            code='DEPT4',
            business_group=self.business_group,
            name='Department 4',
            location=self.location,
            effective_start_date=date(2025, 1, 1)
        )
        position = Position.objects.create(
            code='POS2',
            name='Position 2',
            department=dept,
            location=self.location,
            grade=self.grade,
            effective_start_date=date(2025, 1, 1)
        )
        
        new_date = date(2025, 8, 1)
        dto = PositionUpdateDTO(
            code='POS2', 
            name='Updated Position Name',
            effective_start_date=new_date
        )
        updated = PositionService.update_position(self.user, dto)
        
        # Should create new version
        assert updated.id != position.id
        assert updated.name == 'Updated Position Name'
        assert updated.effective_start_date == new_date
        
        # Should be two versions
        assert Position.objects.filter(code='POS2').count() == 2
        
        # Old version should be end-dated
        position.refresh_from_db()
        assert position.effective_end_date == new_date - timedelta(days=1)
    
    # ========== GRADE TESTS ==========
    
    def test_grade_correction_without_date(self):
        """Test Grade: correction mode when effective_start_date NOT provided"""
        from HR.work_structures.dtos import GradeUpdateDTO
        
        dto = GradeUpdateDTO(code='GR1', name='Updated Grade Name')
        updated = GradeService.update_grade(self.user, dto)
        
        # Should update the same record
        assert updated.id == self.grade.id
        assert updated.name == 'Updated Grade Name'
        assert updated.effective_start_date == date(2025, 1, 1)
        
        # Should be only one version
        assert Grade.objects.filter(code='GR1').count() == 1
    
    def test_grade_versioning_with_different_date(self):
        """Test Grade: versioning mode when effective_start_date different"""
        from HR.work_structures.dtos import GradeUpdateDTO
        
        new_date = date(2025, 9, 1)
        dto = GradeUpdateDTO(
            code='GR1', 
            name='Updated Grade Name',
            effective_start_date=new_date
        )
        updated = GradeService.update_grade(self.user, dto)
        
        # Should create new version
        assert updated.id != self.grade.id
        assert updated.name == 'Updated Grade Name'
        assert updated.effective_start_date == new_date
        
        # Should be two versions
        assert Grade.objects.filter(code='GR1').count() == 2
        
        # Old version should be end-dated
        self.grade.refresh_from_db()
        assert self.grade.effective_end_date == new_date - timedelta(days=1)
    
    # ========== GRADE RATE TESTS ==========
    
    def test_grade_rate_correction_without_date(self):
        """Test GradeRate: correction mode when effective_start_date NOT provided"""
        from HR.work_structures.models import GradeRateType, GradeRate
        
        rate_type = GradeRateType.objects.create(
            code='BASIC',
            name='Basic Salary',
            has_range=True
        )
        
        rate = GradeRate.objects.create(
            grade=self.grade,
            rate_type=rate_type,
            min_amount=5000,
            max_amount=8000,
            currency='USD',
            effective_start_date=date(2025, 1, 1)
        )
        
        updates = {'min_amount': 5500, 'max_amount': 8500}
        updated = GradeService.update_grade_rate(self.user, rate.id, updates)
        
        # Should update the same record
        assert updated.id == rate.id
        assert updated.min_amount == 5500
        assert updated.max_amount == 8500
        assert updated.effective_start_date == date(2025, 1, 1)
        
        # Should be only one version
        assert GradeRate.objects.filter(grade=self.grade, rate_type=rate_type).count() == 1
    
    def test_grade_rate_versioning_with_different_date(self):
        """Test GradeRate: versioning mode when effective_start_date different"""
        from HR.work_structures.models import GradeRateType, GradeRate
        
        rate_type = GradeRateType.objects.create(
            code='TRANS',
            name='Transportation',
            has_range=False
        )
        
        rate = GradeRate.objects.create(
            grade=self.grade,
            rate_type=rate_type,
            fixed_amount=500,
            currency='USD',
            effective_start_date=date(2025, 1, 1)
        )
        
        new_date = date(2025, 10, 1)
        updates = {
            'fixed_amount': 600,
            'effective_start_date': new_date
        }
        updated = GradeService.update_grade_rate(self.user, rate.id, updates)
        
        # Should create new version
        assert updated.id != rate.id
        assert updated.fixed_amount == 600
        assert updated.effective_start_date == new_date
        
        # Should be two versions
        assert GradeRate.objects.filter(grade=self.grade, rate_type=rate_type).count() == 2
        
        # Old version should be end-dated
        rate.refresh_from_db()
        assert rate.effective_end_date == new_date - timedelta(days=1)
    
    # ========== EDGE CASES ==========
    
    def test_correction_preserves_effective_end_date(self):
        """Test that correction mode preserves effective_end_date unless explicitly changed"""
        end_date = date(2025, 12, 31)
        dept = Department.objects.create(
            code='DEPT5',
            business_group=self.business_group,
            name='Department 5',
            location=self.location,
            effective_start_date=date(2025, 1, 1),
            effective_end_date=end_date
        )
        
        # Correction without specifying end date
        dto = DepartmentUpdateDTO(code='DEPT5', name='Updated Name')
        updated = DepartmentService.update_department(self.user, dto)
        
        # Should preserve end date
        assert updated.effective_end_date == end_date
    
    def test_versioning_inherits_effective_end_date(self):
        """Test that versioning inherits effective_end_date from previous version"""
        end_date = date(2025, 12, 31)
        dept = Department.objects.create(
            code='DEPT6',
            business_group=self.business_group,
            name='Department 6',
            location=self.location,
            effective_start_date=date(2025, 1, 1),
            effective_end_date=end_date
        )
        
        # Versioning without specifying end date
        new_date = date(2025, 6, 1)
        dto = DepartmentUpdateDTO(
            code='DEPT6', 
            name='Updated Name',
            effective_start_date=new_date
        )
        updated = DepartmentService.update_department(self.user, dto)
        
        # New version should inherit end date
        assert updated.effective_end_date == end_date
    
    def test_can_explicitly_change_effective_end_date_in_correction(self):
        """Test that effective_end_date can be explicitly changed in correction mode"""
        dept = Department.objects.create(
            code='DEPT7',
            business_group=self.business_group,
            name='Department 7',
            location=self.location,
            effective_start_date=date(2025, 1, 1),
            effective_end_date=date(2025, 12, 31)
        )
        
        new_end_date = date(2025, 6, 30)
        dto = DepartmentUpdateDTO(
            code='DEPT7',
            name='Updated Name',
            effective_end_date=new_end_date
        )
        updated = DepartmentService.update_department(self.user, dto)
        
        # Should update end date in place
        assert updated.id == dept.id
        assert updated.effective_end_date == new_end_date

