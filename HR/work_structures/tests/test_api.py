"""
HR API Tests

Comprehensive tests for all HR API endpoints covering CRUD operations,
filtering, pagination, data scope, and edge cases.
"""

from urllib import response
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from datetime import date, timedelta

from HR.work_structures.models import (
    Enterprise,
    BusinessGroup,
    Location,
    Department,
    Position,
    Grade,
    GradeRateType,
    GradeRate,
    UserDataScope
    )
from core.job_roles.models import JobRole, Page, Action, PageAction, JobRolePage, UserActionDenial

User = get_user_model()


class BaseHRAPITest(APITestCase):
    """Base test class with common setup"""
    
    def setUp(self):
        """Set up test data and authenticate"""
        self.user = User.objects.create_user(
            email='test@example.com',
            name='Test User',
            phone_number='+201234567890',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        # Set up permissions for testing
        self._setup_permissions()
        
        self.enterprise = Enterprise.objects.create(
            code='ENT001',
            name='Test Enterprise',
            effective_start_date=date(2024, 1, 1)
        )
        self.business_group = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Egypt Operations',
            effective_start_date=date(2024, 1, 1)
        )
        self.location = Location.objects.create(
            code='LOC001',
            name='Cairo Office',
            country='Egypt',
            business_group=self.business_group
        )
        
        # Give user access to business group
        UserDataScope.objects.create(
            user=self.user,
            business_group=self.business_group,
            is_global=False
        )
    
    def _setup_permissions(self):
        """Set up job roles and permissions for testing"""
        # Create standard CRUD actions
        view_action, _ = Action.objects.get_or_create(
            name='view',
            defaults={'display_name': 'View', 'description': 'View records'}
        )
        create_action, _ = Action.objects.get_or_create(
            name='create',
            defaults={'display_name': 'Create', 'description': 'Create new records'}
        )
        edit_action, _ = Action.objects.get_or_create(
            name='edit',
            defaults={'display_name': 'Edit', 'description': 'Edit existing records'}
        )
        delete_action, _ = Action.objects.get_or_create(
            name='delete',
            defaults={'display_name': 'Delete', 'description': 'Delete records'}
        )
        
        actions = [view_action, create_action, edit_action, delete_action]
        
        # Create HR pages
        hr_pages_data = [
            ('hr_enterprise', 'HR - Enterprises', 'Manage enterprise organizational structure'),
            ('hr_business_group', 'HR - Business Groups', 'Manage business groups within enterprises'),
            ('hr_location', 'HR - Locations', 'Manage physical or logical workplace locations'),
            ('hr_department', 'HR - Departments', 'Manage departments and their hierarchies'),
            ('hr_department_manager', 'HR - Department Managers', 'Manage department manager assignments'),
            ('hr_position', 'HR - Positions', 'Manage job positions'),
            ('hr_grade', 'HR - Grades', 'Manage job grades and grade rates'),
        ]
        
        hr_pages = []
        for page_name, display_name, description in hr_pages_data:
            page, _ = Page.objects.get_or_create(
                name=page_name,
                defaults={
                    'display_name': display_name,
                    'description': description
                }
            )
            hr_pages.append(page)
            
            # Link all actions to this page
            for action in actions:
                PageAction.objects.get_or_create(
                    page=page,
                    action=action
                )
        
        # Create HR Administrator role with full access
        hr_admin_role, _ = JobRole.objects.get_or_create(
            name='HR Administrator',
            defaults={
                'description': 'Full administrative access to all HR modules for testing'
            }
        )
        
        # Grant HR Administrator access to all HR pages
        for page in hr_pages:
            JobRolePage.objects.get_or_create(
                job_role=hr_admin_role,
                page=page
            )
        
        # Assign role to test user
        self.user.job_role = hr_admin_role
        self.user.save()
        self.hr_admin_role = hr_admin_role
    
    def _get_results(self, response):
        """Helper to extract results from paginated response"""
        if 'data' in response.data and 'results' in response.data['data']:
            return response.data['data']['results']
        return response.data


class EnterpriseAPITests(BaseHRAPITest):
    """Test Enterprise API endpoints"""
    
    def test_enterprise_list_get(self):
        """GET /hr/enterprises/ - List all enterprises"""
        response = self.client.get('/hr/work_structures/enterprises/?page_size=100')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self._get_results(response)
        self.assertGreaterEqual(len(results), 1)
    
    def test_enterprise_list_filter_by_status(self):
        """GET /hr/enterprises/?status=active - Filter by computed status"""
        Enterprise.objects.create(code='ENT002', name='Active', effective_start_date=date(2024, 1, 1))
        Enterprise.objects.create(code='ENT003', name='Inactive', effective_start_date=date(2024, 1, 1))
        response = self.client.get('/hr/work_structures/enterprises/?status=active&page_size=100')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self._get_results(response)
        for result in results:
            self.assertEqual(result['status'], 'active')
    
    def test_enterprise_create_post(self):
        """POST /hr/enterprises/ - Create new enterprise"""
        data = {
            'code': 'ENT002',
            'name': 'New Enterprise',
            'effective_start_date': '2024-01-01'
        }
        
        # Give global scope for enterprise creation
        UserDataScope.objects.filter(user=self.user).update(is_global=True)
        
        response = self.client.post('/hr/work_structures/enterprises/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'ENT002')
        self.assertEqual(response.data['name'], 'New Enterprise')
    
    def test_enterprise_detail_get(self):
        """GET /hr/enterprises/{id}/ - Get enterprise details"""
        response = self.client.get(f'/hr/work_structures/enterprises/{self.enterprise.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['code'], 'ENT001')
    
    def test_enterprise_update_creates_new_version(self):
        """PATCH /hr/enterprises/{id}/ - Update creates new version"""
        data = {
            'name': 'Updated Enterprise Name',
            'effective_start_date': '2024-07-01'
        }
        
        # Give global scope for enterprise update
        UserDataScope.objects.filter(user=self.user).update(is_global=True)
        
        response = self.client.patch(
            f'/hr/work_structures/enterprises/{self.enterprise.id}/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Enterprise Name')
        
        # Verify old version is end-dated
        self.enterprise.refresh_from_db()
        self.assertIsNotNone(self.enterprise.effective_end_date)
        self.assertEqual(self.enterprise.effective_end_date, date(2024, 6, 30))
    
    def test_enterprise_deactivate_delete(self):
        """DELETE /hr/enterprises/{id}/ - Deactivate enterprise"""
        # Give global scope for enterprise deactivation
        UserDataScope.objects.filter(user=self.user).update(is_global=True)
        
        # First deactivate the business group
        self.business_group.deactivate()
        
        response = self.client.delete(f'/hr/work_structures/enterprises/{self.enterprise.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify it's end-dated
        self.enterprise.refresh_from_db()
        self.assertIsNotNone(self.enterprise.effective_end_date)
    
    def test_enterprise_history_get(self):
        """GET /hr/enterprises/{id}/history/ - Get history"""
        # Create another version
        Enterprise.objects.create(
            code='ENT001',
            name='Version 2',
            effective_start_date=date(2024, 7, 1)
        )
        
        response = self.client.get(f'/hr/work_structures/enterprises/{self.enterprise.id}/history/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 2)


class BusinessGroupAPITests(BaseHRAPITest):
    """Test BusinessGroup API endpoints"""
    
    def test_business_group_list_get(self):
        """GET /hr/business-groups/ - List all business groups"""
        response = self.client.get('/hr/work_structures/business-groups/?page_size=100')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self._get_results(response)
        self.assertGreaterEqual(len(results), 1)
    
    def test_business_group_create_post(self):
        """POST /hr/business-groups/ - Create new business group"""
        data = {
            'enterprise': self.enterprise.id,
            'code': 'BG002',
            'name': 'Saudi Operations',
            'effective_start_date': '2024-01-01'
        }
        
        response = self.client.post('/hr/work_structures/business-groups/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'BG002')
    
    def test_business_group_update_creates_new_version(self):
        """PATCH /hr/business-groups/{id}/ - Update creates new version"""
        data = {
            'name': 'Updated Saudi Operations',
            'effective_start_date': '2024-07-01'
        }
        
        response = self.client.patch(
            f'/hr/work_structures/business-groups/{self.business_group.id}/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Saudi Operations')
        
        # Verify old version is end-dated
        self.business_group.refresh_from_db()
        self.assertIsNotNone(self.business_group.effective_end_date)
    
    def test_business_group_detail_get(self):
        """GET /hr/business-groups/{id}/ - Get business group details"""
        response = self.client.get(f'/hr/work_structures/business-groups/{self.business_group.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['code'], 'BG001')
    
    def test_business_group_history_get(self):
        """GET /hr/business-groups/{id}/history/ - Get history"""
        # Create another version
        BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Version 2',
            effective_start_date=date(2024, 7, 1)
        )
        
        response = self.client.get(f'/hr/work_structures/business-groups/{self.business_group.id}/history/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 2)

    def test_business_group_filter_by_enterprise(self):
        """GET /hr/business-groups/?enterprise={id} - Filter by enterprise"""
        response = self.client.get(
            f'/hr/work_structures/business-groups/?enterprise={self.enterprise.id}&page_size=100'
        )
        
        results = self._get_results(response)
        for result in results:
            self.assertEqual(result['enterprise_name'], 'Test Enterprise')


class LocationAPITests(BaseHRAPITest):
    """Test Location API endpoints"""
    
    def test_location_list_get(self):
        """GET /hr/locations/ - List all locations (scoped)"""
        response = self.client.get('/hr/work_structures/locations/?page_size=100')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self._get_results(response)
        self.assertGreaterEqual(len(results), 1)
    
    def test_location_create_post(self):
        """POST /hr/locations/ - Create new location"""
        data = {
            'code': 'LOC002',
            'name': 'Alexandria Office',
            'business_group': self.business_group.id,
            'city': 'Alexandria',
            'country': 'Egypt',
            'status': 'active'
        }
        
        response = self.client.post('/hr/work_structures/locations/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'LOC002')
    
    def test_location_filter_by_country(self):
        """GET /hr/locations/?country=Egypt - Filter by country"""
        response = self.client.get('/hr/work_structures/locations/?country=Egypt&page_size=100')
        
        results = self._get_results(response)
        for result in results:
            self.assertEqual(result['country'], 'Egypt')
    
    def test_location_delete_validations(self):
        """DELETE /hr/locations/{id}/ - Prevent deactivation if linked to active enterprise/BG"""
        # Enterprise-linked location
        ent_loc = Location.objects.create(
            enterprise=self.enterprise, code='LOC_ENT', name='Enterprise HQ', country='Global', status='active'
        )
        resp1 = self.client.delete(f'/hr/work_structures/locations/{ent_loc.id}/')
        self.assertEqual(resp1.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', resp1.data)
        self.assertIn('enterprise', resp1.data)
        
        # BG-linked active location
        bg_loc = Location.objects.create(
            business_group=self.business_group, code='LOC_BG', name='BG Office', country='Egypt', status='active'
        )
        resp2 = self.client.delete(f'/hr/work_structures/locations/{bg_loc.id}/')
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', resp2.data)
        self.assertIn('business_group', resp2.data)


class DepartmentAPITests(BaseHRAPITest):
    """Test Department API endpoints"""
    
    def setUp(self):
        super().setUp()
        self.department = Department.objects.create(
            code='DEPT001',
            business_group=self.business_group,
            name='IT Department',
            location=self.location,
            effective_start_date=date(2024, 1, 1)
        )
    
    def test_department_list_get(self):
        """GET /hr/departments/ - List all active departments (scoped)"""
        response = self.client.get('/hr/work_structures/departments/?page_size=100')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self._get_results(response)
        self.assertGreaterEqual(len(results), 1)
    
    def test_department_create_post(self):
        """POST /hr/departments/ - Create new department"""
        data = {
            'business_group': self.business_group.id,
            'code': 'DEPT002',
            'name': 'HR Department',
            'location': self.location.id,
            'effective_start_date': '2024-01-01'
        }
        
        response = self.client.post('/hr/work_structures/departments/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'DEPT002')
    
    def test_department_detail_get(self):
        """GET /hr/departments/{id}/ - Get department details"""
        response = self.client.get(f'/hr/work_structures/departments/{self.department.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['code'], 'DEPT001')
    
    def test_department_update_creates_new_version(self):
        """PUT /hr/departments/{id}/ - Update creates new version"""
        data = {
            'code': 'DEPT001',
            'name': 'IT Department Updated',
            'effective_start_date': '2024-07-01'
        }
        
        response = self.client.put(
            f'/hr/work_structures/departments/{self.department.id}/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'IT Department Updated')
        
        # Verify old version is end-dated
        self.department.refresh_from_db()
        self.assertIsNotNone(self.department.effective_end_date)
    
    def test_department_history_get(self):
        """GET /hr/departments/{id}/history/ - Get all versions"""
        # Create another version
        Department.objects.create(
            code='DEPT001',
            business_group=self.business_group,
            name='IT Department V2',
            location=self.location,
            effective_start_date=date(2024, 7, 1)
        )
        
        response = self.client.get(f'/hr/work_structures/departments/{self.department.id}/history/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 2)
    
    def test_department_tree_get(self):
        """GET /hr/departments/tree/?bg={id} - Get hierarchy tree"""
        # Create child department
        Department.objects.create(
            code='CHILD',
            business_group=self.business_group,
            name='Child Department',
            location=self.location,
            parent=self.department,
            effective_start_date=date(2024, 1, 1)
        )
        
        response = self.client.get(
            f'/hr/work_structures/departments/tree/?bg={self.business_group.id}'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertGreaterEqual(len(response.data), 1)
    
    def test_department_filter_by_business_group(self):
        """GET /hr/departments/?business_group={id} - Filter by BG"""
        response = self.client.get(
            f'/hr/work_structures/departments/?business_group={self.business_group.id}&page_size=100'
        )
        
        results = self._get_results(response)
        for result in results:
            self.assertEqual(result['business_group_name'], 'Egypt Operations')
    
    def test_deactivate_business_group_validation(self):
        """DELETE /hr/business-groups/{id}/ - Prevent deactivation with active departments"""
        # Attempt to deactivate BG with active dept
        response = self.client.delete(f'/hr/work_structures/business-groups/{self.business_group.id}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)


class PositionAPITests(BaseHRAPITest):
    """Test Position API endpoints"""
    
    def setUp(self):
        super().setUp()
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
        self.position = Position.objects.create(
            code='POS001',
            name='Software Engineer',
            department=self.department,
            location=self.location,
            grade=self.grade,
            effective_start_date=date(2024, 1, 1)
        )
    
    def test_position_list_get(self):
        """GET /hr/positions/ - List all active positions (scoped)"""
        response = self.client.get('/hr/work_structures/positions/?page_size=100')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self._get_results(response)
        self.assertGreaterEqual(len(results), 1)
    
    def test_position_create_post(self):
        """POST /hr/positions/ - Create new position"""
        data = {
            'code': 'POS002',
            'name': 'Senior Engineer',
            'department': self.department.id,
            'location': self.location.id,
            'grade': self.grade.id,
            'effective_start_date': '2024-01-01'
        }
        
        response = self.client.post('/hr/work_structures/positions/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'POS002')
    
    def test_position_detail_get(self):
        """GET /hr/positions/{id}/ - Get position details"""
        response = self.client.get(f'/hr/work_structures/positions/{self.position.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['code'], 'POS001')
    
    def test_position_update_creates_new_version(self):
        """PUT /hr/positions/{id}/ - Update creates new version"""
        data = {
            'code': 'POS001',
            'name': 'Senior Software Engineer',
            'effective_start_date': '2024-07-01'
        }
        
        response = self.client.put(
            f'/hr/work_structures/positions/{self.position.id}/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Senior Software Engineer')
    
    def test_position_history_get(self):
        """GET /hr/positions/{id}/history/ - Get all versions"""
        response = self.client.get(f'/hr/work_structures/positions/{self.position.id}/history/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)
    
    def test_position_hierarchy_get(self):
        """GET /hr/positions/hierarchy/?bg={id} - Get reporting hierarchy"""
        # Create manager position
        manager = Position.objects.create(
            code='MGR001',
            name='Engineering Manager',
            department=self.department,
            location=self.location,
            grade=self.grade,
            effective_start_date=date(2024, 1, 1)
        )
        
        # Update position to report to manager
        self.position.reports_to = manager
        self.position.save()
        
        response = self.client.get(
            f'/hr/work_structures/positions/hierarchy/?bg={self.business_group.id}'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        
        # Find manager node and verify direct_reports contains our position
        manager_nodes = [n for n in response.data if n.get('code') == 'MGR001']
        self.assertTrue(len(manager_nodes) >= 1)
        manager_node = manager_nodes[0]
        self.assertIn('direct_reports', manager_node)
        direct_codes = [r.get('code') for r in manager_node.get('direct_reports', [])]
        self.assertIn('POS001', direct_codes)
    
    def test_position_filter_by_department(self):
        """GET /hr/positions/?department={id} - Filter by department"""
        response = self.client.get(
            f'/hr/work_structures/positions/?department={self.department.id}&page_size=100'
        )
        
        results = self._get_results(response)
        for result in results:
            self.assertEqual(result['department_name'], 'IT Department')
    
    def test_position_deactivate_validation_reports(self):
        """DELETE /hr/positions/{id}/ - Prevent deactivation with active direct reports"""
        manager = Position.objects.create(
            code='MGRX', name='Mgr', department=self.department, location=self.location, grade=self.grade, effective_start_date=date(2024,1,1)
        )
        self.position.reports_to = manager
        self.position.save()
        response = self.client.delete(f'/hr/work_structures/positions/{manager.id}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)


class GradeAPITests(BaseHRAPITest):
    """Test Grade API endpoints"""
    
    def setUp(self):
        super().setUp()
        self.grade = Grade.objects.create(
            code='G1',
            name='Grade 1',
            business_group=self.business_group,
            effective_start_date=date(2024, 1, 1)
        )
    
    def test_grade_list_get(self):
        """GET /hr/grades/ - List all active grades (scoped)"""
        response = self.client.get('/hr/work_structures/grades/?page_size=100')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self._get_results(response)
        self.assertGreaterEqual(len(results), 1)
    
    def test_grade_create_post(self):
        """POST /hr/grades/ - Create new grade"""
        data = {
            'code': 'G2',
            'name': 'Grade 2',
            'business_group': self.business_group.id,
            'effective_start_date': '2024-01-01'
        }
        
        response = self.client.post('/hr/work_structures/grades/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'G2')
    
    def test_grade_detail_get(self):
        """GET /hr/grades/{id}/ - Get grade details"""
        response = self.client.get(f'/hr/work_structures/grades/{self.grade.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['code'], 'G1')
    
    def test_grade_history_get(self):
        """GET /hr/grades/{id}/history/ - Get all versions"""
        response = self.client.get(f'/hr/work_structures/grades/{self.grade.id}/history/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)


class GradeRateAPITests(BaseHRAPITest):
    """Test Grade Rate Level API endpoints"""
    
    def setUp(self):
        super().setUp()
        self.grade = Grade.objects.create(
            code='G1',
            name='Grade 1',
            business_group=self.business_group,
            effective_start_date=date(2024, 1, 1)
        )
        self.rate_type = GradeRateType.objects.create(
            code='BASIC_SALARY',
            name='Basic Salary',
            has_range=True
        )
        self.rate = GradeRate.objects.create(
            grade=self.grade,
            rate_type=self.rate_type,
            min_amount=5000.00,
            max_amount=8000.00,
            currency='EGP',
            effective_start_date=date(2024, 1, 1)
        )
    
    def test_grade_rate_list_get(self):
        """GET /hr/grades/{grade_id}/rates/ - List all rates for grade"""
        response = self.client.get(f'/hr/work_structures/grades/{self.grade.id}/rates/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)
    
    def test_grade_rate_create_post(self):
        """POST /hr/grades/{grade_id}/rates/ - Create new rate level"""
        # Create a different rate type for this test
        transport_rate_type = GradeRateType.objects.create(
            code='TRANSPORT',
            name='Transportation Allowance',
            has_range=False
        )
        
        data = {
            'rate_type': transport_rate_type.id,
            'fixed_amount': 1500.00,
            'currency': 'EGP',
            'effective_start_date': '2024-01-01'
        }
        
        response = self.client.post(
            f'/hr/work_structures/grades/{self.grade.id}/rates/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_grade_rate_detail_get(self):
        """GET /hr/grades/{grade_id}/rates/{rate_id}/ - Get rate details"""
        response = self.client.get(
            f'/hr/work_structures/grades/{self.grade.id}/rates/{self.rate.id}/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['rate_type_code'], 'BASIC_SALARY')
    
    def test_grade_rate_update_patch(self):
        """PATCH /hr/grades/{grade_id}/rates/{rate_id}/ - Update rate"""
        data = {'min_amount': 6000.00}
        
        response = self.client.patch(
            f'/hr/work_structures/grades/{self.grade.id}/rates/{self.rate.id}/',
            data,
            format='json'
        )
        
        # TEMP: Print the error
        if response.status_code != 200:
            print(f"ERROR: {response.data}")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data['min_amount']), 6000.00)
    
    def test_grade_rate_delete(self):
        """DELETE /hr/grades/{grade_id}/rates/{rate_id}/ - Delete rate"""
        response = self.client.delete(
            f'/hr/work_structures/grades/{self.grade.id}/rates/{self.rate.id}/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify it's deleted
        self.assertFalse(GradeRate.objects.filter(id=self.rate.id).exists())


class DataScopeFilteringTests(BaseHRAPITest):
    """Test data scope filtering in API endpoints"""
    
    def setUp(self):
        super().setUp()
        # Create second business group
        self.bg2 = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG002',
            name='Saudi Operations', effective_start_date=date(2024, 1, 1)
        )
        self.location2 = Location.objects.create(
            code='LOC002',
            name='Riyadh Office',
            country='Saudi Arabia',
            business_group=self.bg2
        )
        
        # Create departments in both BGs
        self.dept1 = Department.objects.create(
            code='DEPT001',
            business_group=self.business_group,
            name='Egypt IT',
            location=self.location,
            effective_start_date=date(2024, 1, 1)
        )
        self.dept2 = Department.objects.create(
            code='DEPT002',
            business_group=self.bg2,
            name='Saudi IT',
            location=self.location2,
            effective_start_date=date(2024, 1, 1)
        )
    
    def test_user_sees_only_scoped_departments(self):
        """Test that user only sees departments in their business group"""
        response = self.client.get('/hr/work_structures/departments/?page_size=100')
        
        results = self._get_results(response)
        codes = [r['code'] for r in results]
        
        self.assertIn('DEPT001', codes)
        self.assertNotIn('DEPT002', codes)
    
    def test_user_cannot_create_in_unscoped_bg(self):
        """Test that user cannot create in business group they don't have access to"""
        data = {
            'business_group': self.bg2.id,
            'code': 'DEPT003',
            'name': 'Unauthorized Department',
            'location': self.location2.id,
            'effective_start_date': '2024-01-01'
        }
        
        response = self.client.post('/hr/work_structures/departments/', data, format='json')
        
        # Should return 403 Forbidden (authorization issue), not 400 Bad Request
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('error', response.data)


class PaginationTests(BaseHRAPITest):
    """Test pagination across all list endpoints"""
    
    def test_enterprises_pagination(self):
        """Test enterprise list pagination"""
        # Create multiple enterprises
        for i in range(15):
            Enterprise.objects.create(
                code=f'PAG-{i:03d}',
                name=f'Enterprise {i}'
            , effective_start_date=date(2024, 1, 1))
        
        response = self.client.get('/hr/work_structures/enterprises/?page_size=10')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIn('count', response.data['data'])
        self.assertIn('results', response.data['data'])
    
    def test_departments_pagination_defaults_and_custom(self):
        """Test department pagination default and custom page_size"""
        for i in range(1, 6):
            Department.objects.create(
                code=f'DEPT{i:03d}',
                business_group=self.business_group,
                name=f'Department {i}',
                location=self.location,
                effective_start_date=date(2024, 1, 1)
            )
        resp_default = self.client.get('/hr/work_structures/departments/')
        self.assertEqual(resp_default.status_code, status.HTTP_200_OK)
        self.assertIn('data', resp_default.data)
        resp_custom = self.client.get('/hr/work_structures/departments/?page_size=3')
        results = self._get_results(resp_custom)
        self.assertLessEqual(len(results), 3)


class PermissionTests(APITestCase):
    """Test permission enforcement for unauthorized users"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='unauth@example.com',
            name='Unauthorized User',
            phone_number='+201000000000',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        self.enterprise = Enterprise.objects.create(code='ENT001', name='Test Enterprise', effective_start_date=date(2024, 1, 1))
    
    def test_unauthorized_user_cannot_access_hr_endpoints(self):
        """Unauthorized users get 403 Forbidden"""
        response = self.client.get('/hr/work_structures/enterprises/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DepartmentManagerAPITests(BaseHRAPITest):
    """Test Department Manager assignment endpoints and rules"""
    
    def setUp(self):
        super().setUp()
        self.department = Department.objects.create(
            code='DEPT001', business_group=self.business_group, name='IT', location=self.location, effective_start_date=date(2024,1,1)
        )
        self.manager1 = User.objects.create_user(email='mgr1@test.com', name='Manager 1', phone_number='+201111111111', password='test123')
        self.manager2 = User.objects.create_user(email='mgr2@test.com', name='Manager 2', phone_number='+201111111112', password='test123')
        # Create initial manager assignment
        self.client.post(f'/hr/work_structures/departments/{self.department.id}/managers/', {
            'manager': self.manager1.id,
            'effective_start_date': '2024-01-01'
        }, format='json')
    
    def test_list_managers(self):
        resp = self.client.get(f'/hr/work_structures/departments/{self.department.id}/managers/?page_size=100')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._get_results(resp)
        self.assertGreaterEqual(len(results), 1)
    
    def test_active_only_param(self):
        resp = self.client.get(f'/hr/work_structures/departments/{self.department.id}/managers/?active_only=true&page_size=100')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = self._get_results(resp)
        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0]['effective_end_date'])
    
    def test_assign_new_manager_ends_previous(self):
        resp = self.client.post(f'/hr/work_structures/departments/{self.department.id}/managers/', {
            'manager': self.manager2.id,
            'effective_start_date': '2024-02-01'
        }, format='json')
            # TEMP: Print the error
        if resp.status_code != 201:
            print(f"ERROR: {resp.data}")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # Previous manager should be end-dated to 2024-01-31
        from HR.work_structures.models import DepartmentManager as DM
        prev = DM.objects.filter(department=self.department, manager=self.manager1).order_by('effective_start_date').first()
        self.assertIsNotNone(prev.effective_end_date)
        self.assertEqual(str(prev.effective_end_date), '2024-01-31')
    
    def test_patch_end_date_assignment(self):
        # Fetch current active manager assignment
        from HR.work_structures.models import DepartmentManager as DM
        active = DM.objects.filter(department=self.department, effective_end_date__isnull=True).first()
        resp = self.client.patch(f'/hr/work_structures/departments/{self.department.id}/managers/{active.id}/', {
            'effective_end_date': '2024-12-31'
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['effective_end_date'], '2024-12-31')
    
    def test_delete_end_dates_assignment(self):
        from HR.work_structures.models import DepartmentManager as DM
        active = DM.objects.filter(department=self.department, effective_end_date__isnull=True).first()
        resp = self.client.delete(f'/hr/work_structures/departments/{self.department.id}/managers/{active.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('assignment', resp.data)
    
    def test_custom_page_size(self):
        """Test custom page size parameter"""
        for i in range(5):
            Enterprise.objects.create(
                code=f'CUST-{i:03d}',
                name=f'Enterprise {i}'
            , effective_start_date=date(2024, 1, 1))
        
        response = self.client.get('/hr/work_structures/enterprises/?page_size=3')
        
        results = self._get_results(response)
        self.assertLessEqual(len(results), 3)


class PermissionTests(APITestCase):
    """Test role-based permission enforcement"""
    
    def setUp(self):
        """Set up test data without permissions"""
        self.user = User.objects.create_user(
            email='noperm@example.com',
            name='No Permission User',
            phone_number='+201234567891',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.enterprise = Enterprise.objects.create(
            code='ENT001',
            name='Test Enterprise'
        , effective_start_date=date(2024, 1, 1))
        self.business_group = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Egypt Operations', effective_start_date=date(2024, 1, 1)
        )
        
        # Give user data scope but NO role permissions
        UserDataScope.objects.create(
            user=self.user,
            business_group=self.business_group,
            is_global=True  # Grant global scope so tests can create and manage any enterprise
        )
    
    def test_unauthenticated_user_gets_401(self):
        """Test that unauthenticated users get 401"""
        self.client.force_authenticate(user=None)
        
        response = self.client.get('/hr/work_structures/enterprises/')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
    
    def test_user_without_role_gets_403(self):
        """Test that user without job role gets 403"""
        response = self.client.get('/hr/work_structures/enterprises/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('error', response.data)
        self.assertIn('Permission denied', response.data['error'])
    
    def test_user_with_view_only_cannot_create(self):
        """Test that user with view-only permission cannot create"""
        # Set up view-only permissions
        view_action, _ = Action.objects.get_or_create(name='view', defaults={'display_name': 'View'})
        create_action, _ = Action.objects.get_or_create(name='create', defaults={'display_name': 'Create'})
        
        page, _ = Page.objects.get_or_create(
            name='hr_enterprise',
            defaults={'display_name': 'HR - Enterprises'}
        )
        
        PageAction.objects.get_or_create(page=page, action=view_action)
        PageAction.objects.get_or_create(page=page, action=create_action)
        
        # Create view-only role
        view_only_role, _ = JobRole.objects.get_or_create(
            name='HR Viewer',
            defaults={'description': 'View-only access'}
        )
        JobRolePage.objects.get_or_create(job_role=view_only_role, page=page)
        self.user.job_role = view_only_role
        self.user.save()
        
        # Re-authenticate to pick up the new role assignment
        self.client.force_authenticate(user=self.user)
        
        # In this architecture, roles grant page access and by default all actions on that page.
        # To make it "view-only" for a specific action, we must explicitly deny that action.
        create_page_action = PageAction.objects.get(page=page, action=create_action)
        UserActionDenial.objects.get_or_create(user=self.user, page_action=create_page_action)
        
        # View should work
        response = self.client.get('/hr/work_structures/enterprises/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Create should fail
        data = {'code': 'ENT002', 'name': 'New Enterprise', 'status': 'active'}
        response = self.client.post('/hr/work_structures/enterprises/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_user_with_full_access_can_crud(self):
        """Test that user with full permissions can perform all CRUD operations"""
        # Set up full permissions
        actions = []
        for action_name in ['view', 'create', 'edit', 'delete']:
            action, _ = Action.objects.get_or_create(
                name=action_name,
                defaults={'display_name': action_name.capitalize()}
            )
            actions.append(action)
        
        page, _ = Page.objects.get_or_create(
            name='hr_enterprise',
            defaults={'display_name': 'HR - Enterprises'}
        )
        
        for action in actions:
            PageAction.objects.get_or_create(page=page, action=action)
        
        # Create full access role
        admin_role, _ = JobRole.objects.get_or_create(
            name='HR Admin',
            defaults={'description': 'Full access'}
        )
        JobRolePage.objects.get_or_create(job_role=admin_role, page=page)
        self.user.job_role = admin_role
        self.user.save()
        
        # Refresh user from database and re-authenticate to pick up the new role assignment
        self.user.refresh_from_db()
        self.client.force_authenticate(user=self.user)
        
        # Test all CRUD operations
        # View
        response = self.client.get('/hr/work_structures/enterprises/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Create
        data = {'code': 'ENT002', 'name': 'New Enterprise', 'status': 'active'}
        response = self.client.post('/hr/work_structures/enterprises/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        enterprise_id = response.data['id']
        
        # Edit - Use a future date since creation was also today
        future_date = (date.today() + timedelta(days=30)).isoformat()
        response = self.client.patch(
            f'/hr/work_structures/enterprises/{enterprise_id}/',
            {'name': 'Updated Enterprise', 'effective_start_date': future_date},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Delete
        response = self.client.delete(f'/hr/work_structures/enterprises/{enterprise_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_permission_denied_includes_helpful_details(self):
        """Test that permission denied response includes helpful information"""
        response = self.client.get('/hr/work_structures/departments/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('error', response.data)
        self.assertIn('detail', response.data)
        self.assertIn('required_permission', response.data)
        self.assertEqual(response.data['required_permission']['page'], 'hr_department')
        self.assertEqual(response.data['required_permission']['action'], 'view')


class HardDeleteAPITests(APITestCase):
    def setUp(self):
        self.super_admin = User.objects.create_superuser(
            email='super@test.com',
            name='Super Admin',
            phone_number='1000000000',
            password='password123'
        )
        self.user = User.objects.create_user(
            email='user@test.com',
            name='Regular User',
            phone_number='2000000000',
            password='password123'
        )
        self.client.force_authenticate(user=self.super_admin)
        self.enterprise = Enterprise.objects.create(
            code='ENTX',
            name='Enterprise X',
            effective_start_date=date(2024, 1, 1)
        )
        self.bg = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BGX',
            name='BG X',
            effective_start_date=date(2024, 1, 1)
        )
        self.location = Location.objects.create(
            code='LOCX',
            name='Location X',
            country='Egypt',
            business_group=self.bg
        )
        self.department = Department.objects.create(
            code='DEPTX',
            business_group=self.bg,
            name='Dept X',
            location=self.location,
            effective_start_date=date(2024, 1, 1)
        )
        self.grade = Grade.objects.create(
            code='GRX',
            name='Grade X',
            business_group=self.bg,
            effective_start_date=date(2024, 1, 1)
        )
        self.position = Position.objects.create(
            code='POSX',
            name='Position X',
            department=self.department,
            location=self.location,
            grade=self.grade,
            effective_start_date=date(2024, 1, 1)
        )
    
    def test_hard_delete_requires_super_admin(self):
        self.client.force_authenticate(user=self.user)
        r1 = self.client.delete(f'/hr/work_structures/enterprises/{self.enterprise.id}/hard-delete/')
        self.assertEqual(r1.status_code, status.HTTP_403_FORBIDDEN)
        r2 = self.client.delete(f'/hr/work_structures/business-groups/{self.bg.id}/hard-delete/')
        self.assertEqual(r2.status_code, status.HTTP_403_FORBIDDEN)
        r3 = self.client.delete(f'/hr/work_structures/departments/{self.department.id}/hard-delete/')
        self.assertEqual(r3.status_code, status.HTTP_403_FORBIDDEN)
        r4 = self.client.delete(f'/hr/work_structures/positions/{self.position.id}/hard-delete/')
        self.assertEqual(r4.status_code, status.HTTP_403_FORBIDDEN)
        r5 = self.client.delete(f'/hr/work_structures/grades/{self.grade.id}/hard-delete/')
        self.assertEqual(r5.status_code, status.HTTP_403_FORBIDDEN)
        r6 = self.client.delete(f'/hr/work_structures/locations/{self.location.id}/hard-delete/')
        self.assertEqual(r6.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_enterprise_hard_delete_blocked_by_active_bgs(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.delete(f'/hr/work_structures/enterprises/{self.enterprise.id}/hard-delete/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_business_group_hard_delete_blocked_by_active_departments(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.delete(f'/hr/work_structures/business-groups/{self.bg.id}/hard-delete/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_department_hard_delete_blocked_by_children_and_positions(self):
        self.client.force_authenticate(user=self.super_admin)
        child = Department.objects.create(
            code='CHILDX',
            business_group=self.bg,
            name='Child X',
            location=self.location,
            parent=self.department,
            effective_start_date=date(2024, 1, 1)
        )
        _ = child  # ensure creation
        response = self.client.delete(f'/hr/work_structures/departments/{self.department.id}/hard-delete/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_position_hard_delete_blocked_by_direct_reports(self):
        self.client.force_authenticate(user=self.super_admin)
        report = Position.objects.create(
            code='POSR',
            name='Report',
            department=self.department,
            location=self.location,
            grade=self.grade,
            reports_to=self.position,
            effective_start_date=date(2024, 1, 1)
        )
        _ = report
        response = self.client.delete(f'/hr/work_structures/positions/{self.position.id}/hard-delete/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_grade_hard_delete_blocked_by_positions(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.delete(f'/hr/work_structures/grades/{self.grade.id}/hard-delete/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_location_hard_delete_blocked_by_active_links(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.delete(f'/hr/work_structures/locations/{self.location.id}/hard-delete/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class FlexibleLookupAPITests(BaseHRAPITest):
    def test_create_department_with_codes(self):
        data = {
            'business_group_code': self.business_group.code,
            'code': 'DEPTC',
            'name': 'Created Via Codes',
            'location_code': self.location.code,
            'effective_start_date': '2024-01-01'
        }
        response = self.client.post('/hr/work_structures/departments/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'DEPTC')
    
    def test_create_position_with_codes(self):
        grade = Grade.objects.create(
            code='GCODE',
            name='Grade Code',
            business_group=self.business_group,
            effective_start_date=date(2024, 1, 1)
        )
        dept = Department.objects.create(
            code='DEPTC2',
            business_group=self.business_group,
            name='Dept Codes 2',
            location=self.location,
            effective_start_date=date(2024, 1, 1)
        )
        data = {
            'code': 'POSC',
            'name': 'Position Via Codes',
            'department_code': dept.code,
            'location_code': self.location.code,
            'grade_code': grade.code,
            'effective_start_date': '2024-01-01'
        }
        response = self.client.post('/hr/work_structures/positions/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'POSC')
    
    def test_create_grade_with_bg_code(self):
        data = {
            'code': 'GCODE2',
            'name': 'Grade Via Code',
            'business_group_code': self.business_group.code,
            'effective_start_date': '2024-01-01'
        }
        response = self.client.post('/hr/work_structures/grades/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'GCODE2')
    
    def test_create_grade_rate_with_rate_type_code(self):
        grade = Grade.objects.create(
            code='GRTEST',
            name='Grade Test',
            business_group=self.business_group,
            effective_start_date=date(2024, 1, 1)
        )
        rate_type = GradeRateType.objects.create(
            code='TRANSPORT',
            name='Transportation',
            has_range=False
        )
        data = {
            'rate_type_code': rate_type.code,
            'fixed_amount': 1000.00,
            'currency': 'EGP',
            'effective_start_date': '2024-01-01'
        }
        response = self.client.post(f'/hr/work_structures/grades/{grade.id}/rates/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_grade_rate_validation_errors(self):
        grade = Grade.objects.create(
            code='GRVAL',
            name='Grade Val',
            business_group=self.business_group,
            effective_start_date=date(2024, 1, 1)
        )
        range_type = GradeRateType.objects.create(
            code='BASE',
            name='Base',
            has_range=True
        )
        fixed_type = GradeRateType.objects.create(
            code='ALLOW',
            name='Allowance',
            has_range=False
        )
        bad_range_payload = {
            'rate_type_code': range_type.code,
            'fixed_amount': 5000.00,
            'currency': 'EGP',
            'effective_start_date': '2024-01-01'
        }
        r1 = self.client.post(f'/hr/work_structures/grades/{grade.id}/rates/', bad_range_payload, format='json')
        self.assertEqual(r1.status_code, status.HTTP_400_BAD_REQUEST)
        bad_fixed_payload = {
            'rate_type_code': fixed_type.code,
            'min_amount': 100.00,
            'max_amount': 200.00,
            'currency': 'EGP',
            'effective_start_date': '2024-01-01'
        }
        r2 = self.client.post(f'/hr/work_structures/grades/{grade.id}/rates/', bad_fixed_payload, format='json')
        self.assertEqual(r2.status_code, status.HTTP_400_BAD_REQUEST)


class DeactivationValidationAPITests(BaseHRAPITest):
    def test_enterprise_deactivate_blocked_by_active_bgs(self):
        self.client.force_authenticate(user=self.user)
        UserDataScope.objects.filter(user=self.user).update(is_global=True)
        response = self.client.delete(f'/hr/work_structures/enterprises/{self.enterprise.id}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_business_group_deactivate_blocked_by_active_departments(self):
        dept = Department.objects.create(
            code='DEPTB',
            business_group=self.business_group,
            name='Dept Block',
            location=self.location,
            effective_start_date=date(2024, 1, 1)
        )
        _ = dept
        response = self.client.delete(f'/hr/work_structures/business-groups/{self.business_group.id}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_department_deactivate_blocked_by_children_or_positions(self):
        # Create parent department first
        parent = Department.objects.create(
            code='DEPTPAR',
            business_group=self.business_group,
            name='Parent',
            location=self.location,
            effective_start_date=date(2024, 1, 1)
        )
        child = Department.objects.create(
            code='DEPTCH',
            business_group=self.business_group,
            name='Child',
            location=self.location,
            parent=parent,
            effective_start_date=date(2024, 1, 1)
        )
        # Try to deactivate parent - should fail because of child
        response = self.client.delete(f'/hr/work_structures/departments/{parent.id}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        grade = Grade.objects.create(
            code='GRDB',
            name='Grade Block',
            business_group=self.business_group,
            effective_start_date=date(2024, 1, 1)
        )
        pos = Position.objects.create(
            code='POSB',
            name='Pos Block',
            department=child,
            location=self.location,
            grade=grade,
            effective_start_date=date(2024, 1, 1)
        )
        _ = pos
        response2 = self.client.delete(f'/hr/work_structures/departments/{child.id}/')
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_position_deactivate_blocked_by_direct_reports(self):
        grade = Grade.objects.create(
            code='GRP',
            name='Grade P',
            business_group=self.business_group,
            effective_start_date=date(2024, 1, 1)
        )
        dept = Department.objects.create(
            code='DEPTP',
            business_group=self.business_group,
            name='Dept P',
            location=self.location,
            effective_start_date=date(2024, 1, 1)
        )
        manager = Position.objects.create(
            code='MGRP',
            name='Mgr P',
            department=dept,
            location=self.location,
            grade=grade,
            effective_start_date=date(2024, 1, 1)
        )
        report = Position.objects.create(
            code='REPP',
            name='Rep P',
            department=dept,
            location=self.location,
            grade=grade,
            reports_to=manager,
            effective_start_date=date(2024, 1, 1)
        )
        _ = report
        response = self.client.delete(f'/hr/work_structures/positions/{manager.id}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_location_deactivate_blocked_by_active_links(self):
        # Use existing enterprise that user has access to
        loc = Location.objects.create(
            code='LOCL',
            name='Location L',
            country='Egypt',
            enterprise=self.enterprise
        )
        response = self.client.delete(f'/hr/work_structures/locations/{loc.id}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
