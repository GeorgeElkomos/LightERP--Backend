"""
HR API Tests

Comprehensive tests for all HR API endpoints covering CRUD operations,
filtering, pagination, data scope, and edge cases.
"""

from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from datetime import date

from hr.models import (
    Enterprise,
    BusinessGroup,
    Location,
    Department,
    Position,
    Grade,
    GradeRate,
    UserDataScope,
    StatusChoices
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
            name='Test Enterprise'
        )
        self.business_group = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Egypt Operations'
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
        response = self.client.get('/hr/enterprises/?page_size=100')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self._get_results(response)
        self.assertGreaterEqual(len(results), 1)
    
    def test_enterprise_create_post(self):
        """POST /hr/enterprises/ - Create new enterprise"""
        data = {
            'code': 'ENT002',
            'name': 'New Enterprise',
            'status': 'active'
        }
        
        response = self.client.post('/hr/enterprises/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'ENT002')
        self.assertEqual(response.data['name'], 'New Enterprise')
    
    def test_enterprise_detail_get(self):
        """GET /hr/enterprises/{id}/ - Get enterprise details"""
        response = self.client.get(f'/hr/enterprises/{self.enterprise.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['code'], 'ENT001')
    
    def test_enterprise_update_patch(self):
        """PATCH /hr/enterprises/{id}/ - Update enterprise"""
        data = {'name': 'Updated Enterprise Name'}
        
        response = self.client.patch(
            f'/hr/enterprises/{self.enterprise.id}/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Enterprise Name')
    
    def test_enterprise_deactivate_delete(self):
        """DELETE /hr/enterprises/{id}/ - Deactivate enterprise"""
        response = self.client.delete(f'/hr/enterprises/{self.enterprise.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify it's deactivated
        self.enterprise.refresh_from_db()
        self.assertEqual(self.enterprise.status, StatusChoices.INACTIVE)
    
    def test_enterprise_list_filter_by_status(self):
        """GET /hr/enterprises/?status=active - Filter by status"""
        Enterprise.objects.create(code='ENT002', name='Active', status='active')
        Enterprise.objects.create(code='ENT003', name='Inactive', status='inactive')
        
        response = self.client.get('/hr/enterprises/?status=active&page_size=100')
        
        results = self._get_results(response)
        for result in results:
            self.assertEqual(result['status'], 'active')
    
    def test_enterprise_list_search(self):
        """GET /hr/enterprises/?search=Test - Search enterprises"""
        response = self.client.get('/hr/enterprises/?search=Test&page_size=100')
        
        results = self._get_results(response)
        self.assertGreaterEqual(len(results), 1)


class BusinessGroupAPITests(BaseHRAPITest):
    """Test BusinessGroup API endpoints"""
    
    def test_business_group_list_get(self):
        """GET /hr/business-groups/ - List all business groups"""
        response = self.client.get('/hr/business-groups/?page_size=100')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self._get_results(response)
        self.assertGreaterEqual(len(results), 1)
    
    def test_business_group_create_post(self):
        """POST /hr/business-groups/ - Create new business group"""
        data = {
            'enterprise': self.enterprise.id,
            'code': 'BG002',
            'name': 'Saudi Operations',
            'status': 'active'
        }
        
        response = self.client.post('/hr/business-groups/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'BG002')
    
    def test_business_group_detail_get(self):
        """GET /hr/business-groups/{id}/ - Get business group details"""
        response = self.client.get(f'/hr/business-groups/{self.business_group.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['code'], 'BG001')
    
    def test_business_group_filter_by_enterprise(self):
        """GET /hr/business-groups/?enterprise={id} - Filter by enterprise"""
        response = self.client.get(
            f'/hr/business-groups/?enterprise={self.enterprise.id}&page_size=100'
        )
        
        results = self._get_results(response)
        for result in results:
            self.assertEqual(result['enterprise_name'], 'Test Enterprise')


class LocationAPITests(BaseHRAPITest):
    """Test Location API endpoints"""
    
    def test_location_list_get(self):
        """GET /hr/locations/ - List all locations (scoped)"""
        response = self.client.get('/hr/locations/?page_size=100')
        
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
        
        response = self.client.post('/hr/locations/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'LOC002')
    
    def test_location_filter_by_country(self):
        """GET /hr/locations/?country=Egypt - Filter by country"""
        response = self.client.get('/hr/locations/?country=Egypt&page_size=100')
        
        results = self._get_results(response)
        for result in results:
            self.assertEqual(result['country'], 'Egypt')


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
        response = self.client.get('/hr/departments/?page_size=100')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self._get_results(response)
        self.assertGreaterEqual(len(results), 1)
    
    def test_department_create_post(self):
        """POST /hr/departments/ - Create new department"""
        data = {
            'business_group_id': self.business_group.id,
            'code': 'DEPT002',
            'name': 'HR Department',
            'location_id': self.location.id,
            'effective_start_date': '2024-01-01'
        }
        
        response = self.client.post('/hr/departments/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'DEPT002')
    
    def test_department_detail_get(self):
        """GET /hr/departments/{id}/ - Get department details"""
        response = self.client.get(f'/hr/departments/{self.department.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['code'], 'DEPT001')
    
    def test_department_update_creates_new_version(self):
        """PUT /hr/departments/{id}/ - Update creates new version"""
        data = {
            'code': 'DEPT001',
            'name': 'IT Department Updated',
            'effective_date': '2024-07-01'
        }
        
        response = self.client.put(
            f'/hr/departments/{self.department.id}/',
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
        
        response = self.client.get(f'/hr/departments/{self.department.id}/history/')
        
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
            f'/hr/departments/tree/?bg={self.business_group.id}'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertGreaterEqual(len(response.data), 1)
    
    def test_department_filter_by_business_group(self):
        """GET /hr/departments/?business_group={id} - Filter by BG"""
        response = self.client.get(
            f'/hr/departments/?business_group={self.business_group.id}&page_size=100'
        )
        
        results = self._get_results(response)
        for result in results:
            self.assertEqual(result['business_group_name'], 'Egypt Operations')


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
        response = self.client.get('/hr/positions/?page_size=100')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self._get_results(response)
        self.assertGreaterEqual(len(results), 1)
    
    def test_position_create_post(self):
        """POST /hr/positions/ - Create new position"""
        data = {
            'code': 'POS002',
            'name': 'Senior Engineer',
            'department_id': self.department.id,
            'location_id': self.location.id,
            'grade_id': self.grade.id,
            'effective_start_date': '2024-01-01'
        }
        
        response = self.client.post('/hr/positions/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'POS002')
    
    def test_position_detail_get(self):
        """GET /hr/positions/{id}/ - Get position details"""
        response = self.client.get(f'/hr/positions/{self.position.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['code'], 'POS001')
    
    def test_position_update_creates_new_version(self):
        """PUT /hr/positions/{id}/ - Update creates new version"""
        data = {
            'code': 'POS001',
            'name': 'Senior Software Engineer',
            'effective_date': '2024-07-01'
        }
        
        response = self.client.put(
            f'/hr/positions/{self.position.id}/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Senior Software Engineer')
    
    def test_position_history_get(self):
        """GET /hr/positions/{id}/history/ - Get all versions"""
        response = self.client.get(f'/hr/positions/{self.position.id}/history/')
        
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
            f'/hr/positions/hierarchy/?bg={self.business_group.id}'
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
            f'/hr/positions/?department={self.department.id}&page_size=100'
        )
        
        results = self._get_results(response)
        for result in results:
            self.assertEqual(result['department_name'], 'IT Department')


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
        response = self.client.get('/hr/grades/?page_size=100')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self._get_results(response)
        self.assertGreaterEqual(len(results), 1)
    
    def test_grade_create_post(self):
        """POST /hr/grades/ - Create new grade"""
        data = {
            'code': 'G2',
            'name': 'Grade 2',
            'business_group_id': self.business_group.id,
            'effective_start_date': '2024-01-01'
        }
        
        response = self.client.post('/hr/grades/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'G2')
    
    def test_grade_detail_get(self):
        """GET /hr/grades/{id}/ - Get grade details"""
        response = self.client.get(f'/hr/grades/{self.grade.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['code'], 'G1')
    
    def test_grade_history_get(self):
        """GET /hr/grades/{id}/history/ - Get all versions"""
        response = self.client.get(f'/hr/grades/{self.grade.id}/history/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)


class GradeRateAPITests(BaseHRAPITest):
    """Test Grade Rate API endpoints"""
    
    def setUp(self):
        super().setUp()
        self.grade = Grade.objects.create(
            code='G1',
            name='Grade 1',
            business_group=self.business_group,
            effective_start_date=date(2024, 1, 1)
        )
        self.rate = GradeRate.objects.create(
            grade=self.grade,
            rate_type='MIN_SALARY',
            amount=5000.00,
            currency='EGP',
            effective_start_date=date(2024, 1, 1)
        )
    
    def test_grade_rate_list_get(self):
        """GET /hr/grades/{grade_id}/rates/ - List all rates for grade"""
        response = self.client.get(f'/hr/grades/{self.grade.id}/rates/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)
    
    def test_grade_rate_create_post(self):
        """POST /hr/grades/{grade_id}/rates/ - Create new rate"""
        data = {
            'rate_type': 'MAX_SALARY',
            'amount': 10000.00,
            'currency': 'EGP',
            'effective_start_date': '2024-01-01'
        }
        
        response = self.client.post(
            f'/hr/grades/{self.grade.id}/rates/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['rate_type'], 'MAX_SALARY')
    
    def test_grade_rate_detail_get(self):
        """GET /hr/grades/{grade_id}/rates/{rate_id}/ - Get rate details"""
        response = self.client.get(
            f'/hr/grades/{self.grade.id}/rates/{self.rate.id}/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['rate_type'], 'MIN_SALARY')
    
    def test_grade_rate_update_patch(self):
        """PATCH /hr/grades/{grade_id}/rates/{rate_id}/ - Update rate"""
        data = {'amount': 6000.00}
        
        response = self.client.patch(
            f'/hr/grades/{self.grade.id}/rates/{self.rate.id}/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data['amount']), 6000.00)
    
    def test_grade_rate_delete(self):
        """DELETE /hr/grades/{grade_id}/rates/{rate_id}/ - Delete rate"""
        response = self.client.delete(
            f'/hr/grades/{self.grade.id}/rates/{self.rate.id}/'
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
            name='Saudi Operations'
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
        response = self.client.get('/hr/departments/?page_size=100')
        
        results = self._get_results(response)
        codes = [r['code'] for r in results]
        
        self.assertIn('DEPT001', codes)
        self.assertNotIn('DEPT002', codes)
    
    def test_user_cannot_create_in_unscoped_bg(self):
        """Test that user cannot create in business group they don't have access to"""
        data = {
            'business_group_id': self.bg2.id,
            'code': 'DEPT003',
            'name': 'Unauthorized Department',
            'location_id': self.location2.id,
            'effective_start_date': '2024-01-01'
        }
        
        response = self.client.post('/hr/departments/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
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
            )
        
        response = self.client.get('/hr/enterprises/?page_size=10')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIn('count', response.data['data'])
        self.assertIn('results', response.data['data'])
    
    def test_custom_page_size(self):
        """Test custom page size parameter"""
        for i in range(5):
            Enterprise.objects.create(
                code=f'CUST-{i:03d}',
                name=f'Enterprise {i}'
            )
        
        response = self.client.get('/hr/enterprises/?page_size=3')
        
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
        )
        self.business_group = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Egypt Operations'
        )
        
        # Give user data scope but NO role permissions
        UserDataScope.objects.create(
            user=self.user,
            business_group=self.business_group,
            is_global=False
        )
    
    def test_unauthenticated_user_gets_401(self):
        """Test that unauthenticated users get 401"""
        self.client.force_authenticate(user=None)
        
        response = self.client.get('/hr/enterprises/')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
    
    def test_user_without_role_gets_403(self):
        """Test that user without job role gets 403"""
        response = self.client.get('/hr/enterprises/')
        
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
        
        # In this architecture, roles grant page access and by default all actions on that page.
        # To make it "view-only" for a specific action, we must explicitly deny that action.
        create_page_action = PageAction.objects.get(page=page, action=create_action)
        UserActionDenial.objects.get_or_create(user=self.user, page_action=create_page_action)
        
        # View should work
        response = self.client.get('/hr/enterprises/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Create should fail
        data = {'code': 'ENT002', 'name': 'New Enterprise', 'status': 'active'}
        response = self.client.post('/hr/enterprises/', data, format='json')
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
        
        # Test all CRUD operations
        # View
        response = self.client.get('/hr/enterprises/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Create
        data = {'code': 'ENT002', 'name': 'New Enterprise', 'status': 'active'}
        response = self.client.post('/hr/enterprises/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        enterprise_id = response.data['id']
        
        # Edit
        response = self.client.patch(
            f'/hr/enterprises/{enterprise_id}/',
            {'name': 'Updated Enterprise'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Delete
        response = self.client.delete(f'/hr/enterprises/{enterprise_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_permission_denied_includes_helpful_details(self):
        """Test that permission denied response includes helpful information"""
        response = self.client.get('/hr/departments/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('error', response.data)
        self.assertIn('detail', response.data)
        self.assertIn('required_permission', response.data)
        self.assertEqual(response.data['required_permission']['page'], 'hr_department')
        self.assertEqual(response.data['required_permission']['action'], 'view')
