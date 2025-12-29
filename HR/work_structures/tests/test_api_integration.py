"""
HR API Integration Tests

Comprehensive integration tests for all HR API endpoints including:
- CRUD operations for all HR entities
- Data scope filtering and security
- Pagination, filtering, and search functionality
- Date tracking and versioning
- Reporting hierarchy and tree structures
"""

from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from datetime import date

from HR.work_structures.models import (
    Enterprise,
    BusinessGroup,
    Location,
    Department,
    Position,
    Grade,
    UserDataScope,
    StatusChoices
)
from core.job_roles.models import JobRole, Page, Action, PageAction, JobRolePage, UserActionDenial

User = get_user_model()


class BaseHRAPITest(APITestCase):
    """Base test class with common setup for all HR API tests"""
    
    def setUp(self):
        """Set up test data and authenticate user"""
        self.user = User.objects.create_user(
            email='test@example.com',
            name='Test User',
            phone_number='+201234567890',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        # Set up permissions for testing
        self._setup_permissions()
        
        from datetime import date, timedelta
        past_date = date.today() - timedelta(days=10)
        
        self.enterprise = Enterprise.objects.create(
            code='ENT001',
            name='Test Enterprise',
            effective_start_date=past_date
        )
        self.business_group = BusinessGroup.objects.create(
            enterprise=self.enterprise,
            code='BG001',
            name='Egypt Operations',
            effective_start_date=past_date
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
        """Set up job roles and permissions for API testing"""
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
    
    def test_enterprise_create_post(self):
        """POST /hr/enterprises/ - Create new enterprise"""
        data = {
            'code': 'ENT002',
            'name': 'New Enterprise',
            'status': 'active'
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
    
    def test_enterprise_update_patch(self):
        """PATCH /hr/enterprises/{id}/ - Update enterprise"""
        data = {'name': 'Updated Enterprise Name'}
        
        # Give global scope for enterprise update
        UserDataScope.objects.filter(user=self.user).update(is_global=True)
        
        response = self.client.patch(
            f'/hr/work_structures/enterprises/{self.enterprise.id}/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Enterprise Name')
    
    def test_enterprise_deactivate_delete(self):
        """DELETE /hr/enterprises/{id}/ - Deactivate enterprise"""
        # Give global scope for enterprise deactivation
        UserDataScope.objects.filter(user=self.user).update(is_global=True)
        
        # First deactivate the business group
        self.business_group.deactivate()
        
        response = self.client.delete(f'/hr/work_structures/enterprises/{self.enterprise.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify it's deactivated
        self.enterprise.refresh_from_db()
        self.assertEqual(self.enterprise.status, StatusChoices.INACTIVE)
    
    def test_enterprise_list_filter_by_status(self):
        """GET /hr/enterprises/?status=active - Filter by status"""
        Enterprise.objects.create(code='ENT002', name='Active', effective_start_date=date(2024, 1, 1))
        Enterprise.objects.create(code='ENT003', name='Inactive', effective_start_date=date(2024, 1, 1))
        
        response = self.client.get('/hr/work_structures/enterprises/?status=active&page_size=100')
        
        results = self._get_results(response)
        for result in results:
            self.assertEqual(result['status'], 'active')
    
    def test_enterprise_list_search(self):
        """GET /hr/enterprises/?search=Test - Search enterprises"""
        response = self.client.get('/hr/work_structures/enterprises/?search=Test&page_size=100')
        
        results = self._get_results(response)
        self.assertGreaterEqual(len(results), 1)


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
            'status': 'active'
        }
        
        response = self.client.post('/hr/work_structures/business-groups/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'BG002')
    
    def test_business_group_detail_get(self):
        """GET /hr/business-groups/{id}/ - Get business group details"""
        response = self.client.get(f'/hr/work_structures/business-groups/{self.business_group.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['code'], 'BG001')
    
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

