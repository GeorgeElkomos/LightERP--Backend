from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from datetime import date, timedelta
from HR.work_structures.models import (
    Enterprise,
    BusinessGroup,
    Location,
    Department,
    DepartmentManager as DeptManagerModel,
    Position,
    Grade,
    UserDataScope,
    StatusChoices
)
from HR.work_structures.security import validate_data_scope_on_create

User = get_user_model()


class DataScopeFilteringTests(TestCase):
    def setUp(self):
        from core.user_accounts.models import UserType
        self.user_type = UserType.objects.create(type_name='user')
        self.admin_type = UserType.objects.create(type_name='admin')
        self.super_admin_type = UserType.objects.create(type_name='super_admin')

        self.enterprise = Enterprise.objects.create(code='ENT001', name='Test Enterprise', effective_start_date=date(2024, 1, 1))
        self.bg_egypt = BusinessGroup.objects.create(enterprise=self.enterprise, code='EGY', name='Egypt Operations', effective_start_date=date(2024, 1, 1))
        self.bg_uae = BusinessGroup.objects.create(enterprise=self.enterprise, code='UAE', name='UAE Operations', effective_start_date=date(2024, 1, 1))
        self.bg_saudi = BusinessGroup.objects.create(enterprise=self.enterprise, code='KSA', name='Saudi Operations', effective_start_date=date(2024, 1, 1))

        self.location_enterprise = Location.objects.create(
            enterprise=self.enterprise, business_group=None, code='LOC_ENT', name='Enterprise HQ', country='Global'
        )
        self.location_egypt = Location.objects.create(
            business_group=self.bg_egypt, code='LOC_EGY', name='Cairo Office', country='Egypt'
        )
        self.location_uae = Location.objects.create(
            business_group=self.bg_uae, code='LOC_UAE', name='Dubai Office', country='UAE'
        )

        today = date.today()
        self.dept_egypt = Department.objects.create(
            business_group=self.bg_egypt, code='IT', name='IT Egypt', location=self.location_egypt, effective_start_date=today
        )
        self.dept_uae = Department.objects.create(
            business_group=self.bg_uae, code='IT', name='IT UAE', location=self.location_uae, effective_start_date=today
        )
        self.dept_saudi = Department.objects.create(
            business_group=self.bg_saudi, code='IT', name='IT Saudi', location=self.location_uae, effective_start_date=today
        )

        self.grade_egypt = Grade.objects.create(
            business_group=self.bg_egypt, code='G1', name='Grade 1', effective_start_date=today
        )
        self.grade_uae = Grade.objects.create(
            business_group=self.bg_uae, code='G1', name='Grade 1', effective_start_date=today
        )

        self.position_egypt = Position.objects.create(
            department=self.dept_egypt, code='POS_EGY', name='Engineer', location=self.location_egypt, grade=self.grade_egypt, effective_start_date=today
        )
        self.position_uae = Position.objects.create(
            department=self.dept_uae, code='POS_UAE', name='Engineer', location=self.location_uae, grade=self.grade_uae, effective_start_date=today
        )

        self.super_admin = User.objects.create_superuser(
            email='super@test.com', name='Super', phone_number='1000000000', password='test123'
        )

        self.global_user = User.objects.create_user(
            email='global@test.com', name='Global', phone_number='1000000001', password='test123'
        )
        UserDataScope.objects.create(user=self.global_user, is_global=True)

        self.egypt_user = User.objects.create_user(
            email='egypt@test.com', name='Egypt User', phone_number='1000000002', password='test123'
        )
        UserDataScope.objects.create(user=self.egypt_user, business_group=self.bg_egypt, is_global=False)

        self.uae_user = User.objects.create_user(
            email='uae@test.com', name='UAE User', phone_number='1000000003', password='test123'
        )
        UserDataScope.objects.create(user=self.uae_user, business_group=self.bg_uae, is_global=False)

        self.multi_bg_user = User.objects.create_user(
            email='multibg@test.com', name='Multi BG User', phone_number='1000000004', password='test123'
        )
        UserDataScope.objects.create(user=self.multi_bg_user, business_group=self.bg_egypt, is_global=False)
        UserDataScope.objects.create(user=self.multi_bg_user, business_group=self.bg_uae, is_global=False)

        self.no_scope_user = User.objects.create_user(
            email='noscope@test.com', name='No Scope User', phone_number='1000000005', password='test123'
        )

    def test_c17_business_group_scoping_super_admin(self):
        bgs = BusinessGroup.objects.scoped(self.super_admin).all()
        assert bgs.count() == 3
        assert self.bg_egypt in bgs and self.bg_uae in bgs and self.bg_saudi in bgs

    def test_c17_business_group_scoping_global_user(self):
        bgs = BusinessGroup.objects.scoped(self.global_user).all()
        assert bgs.count() == 3

    def test_c17_business_group_scoping_single_bg(self):
        bgs = BusinessGroup.objects.scoped(self.egypt_user).all()
        assert bgs.count() == 1 and bgs.first() == self.bg_egypt
        bgs_uae = BusinessGroup.objects.scoped(self.uae_user).all()
        assert bgs_uae.count() == 1 and bgs_uae.first() == self.bg_uae

    def test_c17_business_group_scoping_multi_bg(self):
        bgs = BusinessGroup.objects.scoped(self.multi_bg_user).all()
        assert bgs.count() == 2
        assert self.bg_egypt in bgs and self.bg_uae in bgs and self.bg_saudi not in bgs

    def test_c17_business_group_scoping_no_scope(self):
        bgs = BusinessGroup.objects.scoped(self.no_scope_user).all()
        assert bgs.count() == 0

    def test_c26_location_scoping_super_admin(self):
        locations = Location.objects.scoped(self.super_admin).all()
        assert locations.count() == 3

    def test_c26_location_scoping_includes_enterprise_level(self):
        locations = Location.objects.scoped(self.egypt_user).all()
        assert self.location_egypt in locations and self.location_enterprise in locations and self.location_uae not in locations

    def test_c26_location_scoping_single_bg(self):
        locations = Location.objects.scoped(self.uae_user).all()
        assert self.location_uae in locations and self.location_enterprise in locations and self.location_egypt not in locations

    def test_c44_department_scoping_super_admin(self):
        depts = Department.objects.scoped(self.super_admin).active()
        assert depts.count() == 3

    def test_c44_department_scoping_single_bg(self):
        depts = Department.objects.scoped(self.egypt_user).active()
        assert depts.count() == 1 and depts.first() == self.dept_egypt
        depts_uae = Department.objects.scoped(self.uae_user).active()
        assert depts_uae.count() == 1 and depts_uae.first() == self.dept_uae

    def test_c44_department_scoping_multi_bg(self):
        depts = Department.objects.scoped(self.multi_bg_user).active()
        assert depts.count() == 2
        assert self.dept_egypt in depts and self.dept_uae in depts and self.dept_saudi not in depts

    def test_c44_department_scoping_no_scope(self):
        depts = Department.objects.scoped(self.no_scope_user).active()
        assert depts.count() == 0

    def test_c64_position_scoping_cascades_through_department(self):
        positions = Position.objects.scoped(self.egypt_user).active()
        assert positions.count() == 1 and positions.first() == self.position_egypt

    def test_c64_position_scoping_multi_bg(self):
        positions = Position.objects.scoped(self.multi_bg_user).active()
        assert positions.count() == 2
        assert self.position_egypt in positions and self.position_uae in positions

    def test_grade_scoping_single_bg(self):
        grades = Grade.objects.scoped(self.egypt_user).active()
        assert grades.count() == 1 and grades.first() == self.grade_egypt
        grades_uae = Grade.objects.scoped(self.uae_user).active()
        assert grades_uae.count() == 1 and grades_uae.first() == self.grade_uae


class DepartmentManagerScopingTests(TestCase):
    def setUp(self):
        from core.user_accounts.models import UserType
        self.user_type = UserType.objects.create(type_name='user')
        self.super_admin_type = UserType.objects.create(type_name='super_admin')

        self.enterprise = Enterprise.objects.create(code='ENT001', name='Test Enterprise', effective_start_date=date(2024, 1, 1))
        self.bg_egypt = BusinessGroup.objects.create(enterprise=self.enterprise, code='EGY', name='Egypt Operations', effective_start_date=date(2024, 1, 1))
        self.bg_uae = BusinessGroup.objects.create(enterprise=self.enterprise, code='UAE', name='UAE Operations', effective_start_date=date(2024, 1, 1))

        self.location_egypt = Location.objects.create(business_group=self.bg_egypt, code='LOC_EGY', name='Cairo Office', country='Egypt')
        self.location_uae = Location.objects.create(business_group=self.bg_uae, code='LOC_UAE', name='Dubai Office', country='UAE')

        today = date.today()
        self.dept_egypt = Department.objects.create(
            business_group=self.bg_egypt, code='IT', name='IT Department Egypt', location=self.location_egypt, effective_start_date=today
        )
        self.dept_uae = Department.objects.create(
            business_group=self.bg_uae, code='IT', name='IT Department UAE', location=self.location_uae, effective_start_date=today
        )

        self.manager1 = User.objects.create_user(email='manager1@test.com', name='Manager 1', phone_number='1111111111', password='test123')
        self.manager2 = User.objects.create_user(email='manager2@test.com', name='Manager 2', phone_number='2222222222', password='test123')

        self.dept_mgr_egypt = DeptManagerModel.objects.create(department=self.dept_egypt, manager=self.manager1, effective_start_date=today)
        self.dept_mgr_uae = DeptManagerModel.objects.create(department=self.dept_uae, manager=self.manager2, effective_start_date=today)

        self.egypt_user = User.objects.create_user(email='egypt@test.com', name='Egypt User', phone_number='3333333333', password='test123')
        UserDataScope.objects.create(user=self.egypt_user, business_group=self.bg_egypt, is_global=False)
        self.uae_user = User.objects.create_user(email='uae@test.com', name='UAE User', phone_number='4444444444', password='test123')
        UserDataScope.objects.create(user=self.uae_user, business_group=self.bg_uae, is_global=False)

    def test_c44_department_manager_scoping(self):
        dept_mgrs = DeptManagerModel.objects.scoped(self.egypt_user).active()
        assert dept_mgrs.count() == 1 and dept_mgrs.first() == self.dept_mgr_egypt
        dept_mgrs_uae = DeptManagerModel.objects.scoped(self.uae_user).active()
        assert dept_mgrs_uae.count() == 1 and dept_mgrs_uae.first() == self.dept_mgr_uae


class HierarchicalScopeTests(TestCase):
    def setUp(self):
        from core.user_accounts.models import UserType
        self.user_type = UserType.objects.create(type_name='user')

        self.enterprise = Enterprise.objects.create(code='ENT001', name='Test Enterprise', effective_start_date=date(2024, 1, 1))
        self.bg1 = BusinessGroup.objects.create(enterprise=self.enterprise, code='BG1', name='Business Group 1', effective_start_date=date(2024, 1, 1))
        self.bg2 = BusinessGroup.objects.create(enterprise=self.enterprise, code='BG2', name='Business Group 2', effective_start_date=date(2024, 1, 1))

        today = date.today()
        self.location1 = Location.objects.create(business_group=self.bg1, code='LOC1', name='Location 1', country='Egypt')
        self.location2 = Location.objects.create(business_group=self.bg2, code='LOC2', name='Location 2', country='UAE')

        self.dept1_bg1 = Department.objects.create(business_group=self.bg1, code='D1', name='Dept 1', location=self.location1, effective_start_date=today)
        self.dept2_bg1 = Department.objects.create(business_group=self.bg1, code='D2', name='Dept 2', location=self.location1, effective_start_date=today)
        self.dept3_bg2 = Department.objects.create(business_group=self.bg2, code='D3', name='Dept 3', location=self.location2, effective_start_date=today)
        self.dept4_bg2 = Department.objects.create(business_group=self.bg2, code='D4', name='Dept 4', location=self.location2, effective_start_date=today)
        self.dept5_bg2 = Department.objects.create(business_group=self.bg2, code='D5', name='Dept 5', location=self.location2, effective_start_date=today)

        self.grade1 = Grade.objects.create(business_group=self.bg1, code='G1', name='Grade 1', effective_start_date=today)
        self.grade2 = Grade.objects.create(business_group=self.bg2, code='G2', name='Grade 2', effective_start_date=today)

        self.pos1 = Position.objects.create(department=self.dept1_bg1, code='POS1', name='Position 1', location=self.location1, grade=self.grade1, effective_start_date=today)
        self.pos3 = Position.objects.create(department=self.dept3_bg2, code='POS3', name='Position 3', location=self.location2, grade=self.grade2, effective_start_date=today)
        self.pos4 = Position.objects.create(department=self.dept4_bg2, code='POS4', name='Position 4', location=self.location2, grade=self.grade2, effective_start_date=today)
        self.pos5 = Position.objects.create(department=self.dept5_bg2, code='POS5', name='Position 5', location=self.location2, grade=self.grade2, effective_start_date=today)

    def test_bg_full_access_scope(self):
        user = User.objects.create_user(email='bg1_user@test.com', name='BG1 User', phone_number='1111111111', password='test123')
        UserDataScope.objects.create(user=user, business_group=self.bg1)
        depts = Department.objects.scoped(user).active()
        assert depts.count() == 2 and self.dept1_bg1 in depts and self.dept2_bg1 in depts and self.dept3_bg2 not in depts

    def test_department_restricted_scope(self):
        user = User.objects.create_user(email='dept_user@test.com', name='Dept User', phone_number='2222222222', password='test123')
        UserDataScope.objects.create(user=user, business_group=self.bg2, department=self.dept3_bg2)
        depts = Department.objects.scoped(user).active()
        assert depts.count() == 1 and depts.first() == self.dept3_bg2

    def test_mixed_bg_and_dept_scope(self):
        user = User.objects.create_user(email='mixed_user@test.com', name='Mixed User', phone_number='3333333333', password='test123')
        UserDataScope.objects.create(user=user, business_group=self.bg1)
        UserDataScope.objects.create(user=user, business_group=self.bg2, department=self.dept3_bg2)
        UserDataScope.objects.create(user=user, business_group=self.bg2, department=self.dept4_bg2)
        depts = Department.objects.scoped(user).active()
        assert depts.count() == 4
        assert self.dept1_bg1 in depts and self.dept2_bg1 in depts and self.dept3_bg2 in depts and self.dept4_bg2 in depts and self.dept5_bg2 not in depts

    def test_positions_follow_dept_scope(self):
        user = User.objects.create_user(email='pos_user@test.com', name='Position User', phone_number='4444444444', password='test123')
        UserDataScope.objects.create(user=user, business_group=self.bg2, department=self.dept3_bg2)
        positions = Position.objects.scoped(user).active()
        assert positions.count() == 1 and positions.first() == self.pos3

    def test_positions_mixed_scope(self):
        user = User.objects.create_user(email='pos_mixed@test.com', name='Position Mixed User', phone_number='5555555555', password='test123')
        UserDataScope.objects.create(user=user, business_group=self.bg1)
        UserDataScope.objects.create(user=user, business_group=self.bg2, department=self.dept3_bg2)
        UserDataScope.objects.create(user=user, business_group=self.bg2, department=self.dept4_bg2)
        positions = Position.objects.scoped(user).active()
        assert positions.count() == 3
        assert self.pos1 in positions and self.pos3 in positions and self.pos4 in positions and self.pos5 not in positions

    def test_locations_cascade_from_dept_scope(self):
        user = User.objects.create_user(email='loc_user@test.com', name='Location User', phone_number='6666666666', password='test123')
        UserDataScope.objects.create(user=user, business_group=self.bg2, department=self.dept3_bg2)
        locations = Location.objects.scoped(user).all()
        assert self.location2 in locations and self.location1 not in locations

    def test_grades_visible_for_dept_scope_bg(self):
        user = User.objects.create_user(email='grade_user@test.com', name='Grade User', phone_number='7777777777', password='test123')
        UserDataScope.objects.create(user=user, business_group=self.bg2, department=self.dept3_bg2)
        grades = Grade.objects.scoped(user).active()
        assert grades.count() == 1 and grades.first() == self.grade2

    def test_business_groups_visible_with_any_scope(self):
        user = User.objects.create_user(email='bg_user@test.com', name='BG User', phone_number='8888888888', password='test123')
        UserDataScope.objects.create(user=user, business_group=self.bg1)
        UserDataScope.objects.create(user=user, business_group=self.bg2, department=self.dept3_bg2)
        bgs = BusinessGroup.objects.scoped(user).all()
        assert bgs.count() == 2 and self.bg1 in bgs and self.bg2 in bgs

    def test_multiple_dept_scopes_in_same_bg(self):
        user = User.objects.create_user(email='multi_dept@test.com', name='Multi Dept User', phone_number='9999999999', password='test123')
        UserDataScope.objects.create(user=user, business_group=self.bg2, department=self.dept3_bg2)
        UserDataScope.objects.create(user=user, business_group=self.bg2, department=self.dept4_bg2)
        UserDataScope.objects.create(user=user, business_group=self.bg2, department=self.dept5_bg2)
        depts = Department.objects.scoped(user).active()
        assert depts.count() == 3
        assert self.dept3_bg2 in depts and self.dept4_bg2 in depts and self.dept5_bg2 in depts

    def test_dept_scope_does_not_grant_other_depts_in_bg(self):
        user = User.objects.create_user(email='restricted@test.com', name='Restricted User', phone_number='1010101010', password='test123')
        UserDataScope.objects.create(user=user, business_group=self.bg2, department=self.dept3_bg2)
        depts = Department.objects.scoped(user).active()
        assert depts.count() == 1 and self.dept4_bg2 not in depts and self.dept5_bg2 not in depts


class HierarchicalScopeEdgeCasesTests(TestCase):
    def setUp(self):
        from core.user_accounts.models import UserType
        self.user_type = UserType.objects.create(type_name='user')
        self.enterprise = Enterprise.objects.create(code='ENT', name='Enterprise', effective_start_date=date(2024, 1, 1))
        self.bg = BusinessGroup.objects.create(enterprise=self.enterprise, code='BG', name='BG', effective_start_date=date(2024, 1, 1))
        self.location = Location.objects.create(business_group=self.bg, code='LOC', name='Location', country='Egypt')
        self.dept = Department.objects.create(business_group=self.bg, code='DEPT', name='Department', location=self.location, effective_start_date=date.today())
        self.user = User.objects.create_user(email='test@test.com', name='Test User', phone_number='1234567890', password='test123')

    def test_cannot_create_dept_scope_without_bg(self):
        from django.db import IntegrityError
        try:
            UserDataScope.objects.create(user=self.user, department=self.dept)
            assert False, "Should have raised IntegrityError"
        except IntegrityError:
            assert True

    def test_can_create_bg_scope_without_dept(self):
        scope = UserDataScope.objects.create(user=self.user, business_group=self.bg)
        assert scope.department is None and scope.business_group == self.bg

    def test_global_scope_requires_no_bg(self):
        scope = UserDataScope.objects.create(user=self.user, is_global=True)
        assert scope.is_global and scope.business_group is None and scope.department is None

    def test_unique_user_bg_dept_combination(self):
        from django.db import IntegrityError
        UserDataScope.objects.create(user=self.user, business_group=self.bg, department=self.dept)
        try:
            UserDataScope.objects.create(user=self.user, business_group=self.bg, department=self.dept)
            assert False, "Should have raised IntegrityError"
        except IntegrityError:
            assert True

    def test_can_have_multiple_dept_scopes_same_bg(self):
        dept2 = Department.objects.create(business_group=self.bg, code='DEPT2', name='Department 2', location=self.location, effective_start_date=date.today())
        UserDataScope.objects.create(user=self.user, business_group=self.bg, department=self.dept)
        UserDataScope.objects.create(user=self.user, business_group=self.bg, department=dept2)
        assert UserDataScope.objects.filter(user=self.user).count() == 2


class EnterpriseScopingTests(TestCase):
    def setUp(self):
        from core.user_accounts.models import UserType
        self.user_type = UserType.objects.create(type_name='user')
        self.super_admin_type = UserType.objects.create(type_name='super_admin')

        self.enterprise_mena = Enterprise.objects.create(code='MENA', name='MENA Operations', effective_start_date=date(2024, 1, 1))
        self.enterprise_asia = Enterprise.objects.create(code='ASIA', name='Asia Operations', effective_start_date=date(2024, 1, 1))

        self.bg_egypt = BusinessGroup.objects.create(enterprise=self.enterprise_mena, code='EGY', name='Egypt Operations', effective_start_date=date(2024, 1, 1))
        self.bg_uae = BusinessGroup.objects.create(enterprise=self.enterprise_mena, code='UAE', name='UAE Operations', effective_start_date=date(2024, 1, 1))
        self.bg_india = BusinessGroup.objects.create(enterprise=self.enterprise_asia, code='IND', name='India Operations', effective_start_date=date(2024, 1, 1))

        self.super_admin = User.objects.create_superuser(email='super@test.com', name='Super', phone_number='1200000000', password='test123')
        self.global_user = User.objects.create_user(email='global@test.com', name='Global', phone_number='1200000001', password='test123')
        UserDataScope.objects.create(user=self.global_user, is_global=True)
        self.egypt_user = User.objects.create_user(email='egypt@test.com', name='Egypt User', phone_number='1200000002', password='test123')
        UserDataScope.objects.create(user=self.egypt_user, business_group=self.bg_egypt)
        self.india_user = User.objects.create_user(email='india@test.com', name='India User', phone_number='1200000003', password='test123')
        UserDataScope.objects.create(user=self.india_user, business_group=self.bg_india)
        self.mena_user = User.objects.create_user(email='mena@test.com', name='MENA User', phone_number='1200000004', password='test123')
        UserDataScope.objects.create(user=self.mena_user, business_group=self.bg_egypt)
        UserDataScope.objects.create(user=self.mena_user, business_group=self.bg_uae)
        self.multi_enterprise_user = User.objects.create_user(email='multi@test.com', name='Multi Ent User', phone_number='1200000005', password='test123')
        UserDataScope.objects.create(user=self.multi_enterprise_user, business_group=self.bg_egypt)
        UserDataScope.objects.create(user=self.multi_enterprise_user, business_group=self.bg_india)
        self.no_scope_user = User.objects.create_user(email='noscope@test.com', name='No Scope User', phone_number='1200000006', password='test123')

    def test_enterprise_scoping_super_admin(self):
        enterprises = Enterprise.objects.scoped(self.super_admin).all()
        assert enterprises.count() == 2 and self.enterprise_mena in enterprises and self.enterprise_asia in enterprises

    def test_enterprise_scoping_global_user(self):
        enterprises = Enterprise.objects.scoped(self.global_user).all()
        assert enterprises.count() == 2

    def test_enterprise_scoping_single_bg_user(self):
        enterprises = Enterprise.objects.scoped(self.egypt_user).all()
        assert enterprises.count() == 1 and enterprises.first() == self.enterprise_mena
        enterprises_asia = Enterprise.objects.scoped(self.india_user).all()
        assert enterprises_asia.count() == 1 and enterprises_asia.first() == self.enterprise_asia

    def test_enterprise_scoping_multi_bg_same_enterprise(self):
        enterprises = Enterprise.objects.scoped(self.mena_user).all()
        assert enterprises.count() == 1 and enterprises.first() == self.enterprise_mena

    def test_enterprise_scoping_multi_bg_different_enterprises(self):
        enterprises = Enterprise.objects.scoped(self.multi_enterprise_user).all()
        assert enterprises.count() == 2 and self.enterprise_mena in enterprises and self.enterprise_asia in enterprises

    def test_enterprise_scoping_no_scope_user(self):
        enterprises = Enterprise.objects.scoped(self.no_scope_user).all()
        assert enterprises.count() == 0


class DepartmentLevelScopingTests(TestCase):
    def setUp(self):
        from core.user_accounts.models import UserType
        self.user_type = UserType.objects.create(type_name='user')
        self.enterprise = Enterprise.objects.create(code='ENT001', name='Test Enterprise', effective_start_date=date(2024, 1, 1))
        self.bg = BusinessGroup.objects.create(enterprise=self.enterprise, code='EGY', name='Egypt Operations', effective_start_date=date(2024, 1, 1))
        self.location = Location.objects.create(business_group=self.bg, code='LOC_EGY', name='Cairo Office', country='Egypt')

        today = date.today()
        self.dept_it = Department.objects.create(business_group=self.bg, code='IT', name='IT Department', location=self.location, effective_start_date=today)
        self.dept_it_dev = Department.objects.create(business_group=self.bg, code='IT-DEV', name='IT Development', location=self.location, parent=self.dept_it, effective_start_date=today)
        self.dept_frontend = Department.objects.create(business_group=self.bg, code='IT-DEV-FE', name='Frontend Team', location=self.location, parent=self.dept_it_dev, effective_start_date=today)
        self.dept_backend = Department.objects.create(business_group=self.bg, code='IT-DEV-BE', name='Backend Team', location=self.location, parent=self.dept_it_dev, effective_start_date=today)
        self.dept_it_ops = Department.objects.create(business_group=self.bg, code='IT-OPS', name='IT Operations', location=self.location, parent=self.dept_it, effective_start_date=today)
        self.dept_hr = Department.objects.create(business_group=self.bg, code='HR', name='HR Department', location=self.location, effective_start_date=today)

        self.bg_user = User.objects.create_user(email='bg_user@test.com', name='BG User', phone_number='2000000001', password='test123')
        UserDataScope.objects.create(user=self.bg_user, business_group=self.bg, department=None, is_global=False)
        self.it_user = User.objects.create_user(email='it_user@test.com', name='IT User', phone_number='2000000002', password='test123')
        UserDataScope.objects.create(user=self.it_user, business_group=self.bg, department=self.dept_it, is_global=False)
        self.dev_user = User.objects.create_user(email='dev_user@test.com', name='Dev User', phone_number='2000000003', password='test123')
        UserDataScope.objects.create(user=self.dev_user, business_group=self.bg, department=self.dept_it_dev, is_global=False)
        self.frontend_user = User.objects.create_user(email='frontend_user@test.com', name='Frontend User', phone_number='2000000004', password='test123')
        UserDataScope.objects.create(user=self.frontend_user, business_group=self.bg, department=self.dept_frontend, is_global=False)

    def test_department_level_bg_user_sees_all(self):
        depts = Department.objects.scoped(self.bg_user).active()
        assert depts.count() == 6

    def test_department_level_top_parent_sees_descendants(self):
        depts = Department.objects.scoped(self.it_user).active().order_by('code')
        dept_codes = [d.code for d in depts]
        assert 'IT' in dept_codes and 'IT-DEV' in dept_codes and 'IT-DEV-FE' in dept_codes and 'IT-DEV-BE' in dept_codes and 'IT-OPS' in dept_codes
        assert 'HR' not in dept_codes and len(dept_codes) == 5

    def test_department_level_mid_level_sees_children(self):
        depts = Department.objects.scoped(self.dev_user).active().order_by('code')
        dept_codes = [d.code for d in depts]
        assert 'IT-DEV' in dept_codes and 'IT-DEV-FE' in dept_codes and 'IT-DEV-BE' in dept_codes
        assert 'IT' not in dept_codes and 'IT-OPS' not in dept_codes and 'HR' not in dept_codes and len(dept_codes) == 3

    def test_department_level_leaf_sees_only_self(self):
        depts = Department.objects.scoped(self.frontend_user).active()
        assert depts.count() == 1 and depts.first() == self.dept_frontend

    def test_validate_scope_bg_level_can_create_anywhere(self):
        validate_data_scope_on_create(self.bg_user, self.bg.id, parent_department_id=self.dept_it.id)
        validate_data_scope_on_create(self.bg_user, self.bg.id, parent_department_id=self.dept_hr.id)

    def test_validate_scope_dept_level_can_create_in_subtree(self):
        validate_data_scope_on_create(self.it_user, self.bg.id, parent_department_id=self.dept_it.id)
        validate_data_scope_on_create(self.it_user, self.bg.id, parent_department_id=self.dept_it_dev.id)
        validate_data_scope_on_create(self.dev_user, self.bg.id, parent_department_id=self.dept_it_dev.id)
        validate_data_scope_on_create(self.dev_user, self.bg.id, parent_department_id=self.dept_frontend.id)

    def test_validate_scope_dept_level_cannot_create_outside_subtree(self):
        try:
            validate_data_scope_on_create(self.it_user, self.bg.id, parent_department_id=self.dept_hr.id)
            assert False, "Should have raised PermissionDenied"
        except PermissionDenied:
            pass
        try:
            validate_data_scope_on_create(self.dev_user, self.bg.id, parent_department_id=self.dept_it_ops.id)
            assert False, "Should have raised PermissionDenied"
        except PermissionDenied:
            pass
        try:
            validate_data_scope_on_create(self.frontend_user, self.bg.id, parent_department_id=self.dept_backend.id)
            assert False, "Should have raised PermissionDenied"
        except PermissionDenied:
            pass

    def test_validate_scope_dept_level_update_own_dept(self):
        validate_data_scope_on_create(self.it_user, self.bg.id, department_id=self.dept_it.id)
        validate_data_scope_on_create(self.dev_user, self.bg.id, department_id=self.dept_it_dev.id)

    def test_validate_scope_dept_level_cannot_update_outside(self):
        try:
            validate_data_scope_on_create(self.it_user, self.bg.id, department_id=self.dept_hr.id)
            assert False, "Should have raised PermissionDenied"
        except PermissionDenied:
            pass
        try:
            validate_data_scope_on_create(self.dev_user, self.bg.id, department_id=self.dept_it.id)
            assert False, "Should have raised PermissionDenied"
        except PermissionDenied:
            pass
