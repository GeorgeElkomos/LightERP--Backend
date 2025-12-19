"""
Management command to seed the database with realistic test data.

Usage: python manage.py seed_all_data
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
import random

from core.user_accounts.models import CustomUser, UserType
from core.job_roles.models import (
    JobRole, Page, Action, PageAction, 
    JobRolePage, UserActionDenial
)
from hr.models import (
    Enterprise, BusinessGroup, Location, Department,
    DepartmentManager, Grade, GradeRate, Position, UserDataScope,
    StatusChoices
)


class Command(BaseCommand):
    help = 'Seeds database with comprehensive test data across all modules'

    def __init__(self):
        super().__init__()
        self.created_objects = {
            'users': [],
            'job_roles': [],
            'pages': [],
            'actions': [],
            'enterprises': [],
            'business_groups': [],
            'locations': [],
            'departments': [],
            'grades': [],
            'positions': [],
        }

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Starting comprehensive data seeding...'))
        
        # Order matters due to foreign key relationships
        self.seed_users()
        self.seed_job_roles_structure()
        self.seed_hr_structure()
        self.seed_department_managers()
        self.seed_grades()
        self.seed_positions()
        self.seed_user_data_scopes()
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('SEEDING COMPLETED SUCCESSFULLY'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.print_summary()

    def seed_users(self):
        """Seed Users with different types"""
        self.stdout.write(self.style.MIGRATE_HEADING('\n1. Seeding Users...'))
        
        users_data = [
            {
                'email': 'superadmin@lightidea.com',
                'name': 'Amr Elsayed',
                'phone_number': '01000000001',
                'user_type_name': 'super_admin',
            },
            {
                'email': 'admin1@lightidea.com',
                'name': 'Omar Hassan',
                'phone_number': '01000000002',
                'user_type_name': 'admin',
            },
            {
                'email': 'admin2@lightidea.com',
                'name': 'Layla Mansour',
                'phone_number': '01000000003',
                'user_type_name': 'admin',
            },
            {
                'email': 'khalid.salem@lightidea.com',
                'name': 'Khalid Salem',
                'phone_number': '01000000004',
                'user_type_name': 'user',
            },
            {
                'email': 'nour.ibrahim@lightidea.com',
                'name': 'Nour Ibrahim',
                'phone_number': '01000000005',
                'user_type_name': 'user',
            },
            {
                'email': 'ahmad.zahran@lightidea.com',
                'name': 'Ahmad Zahran',
                'phone_number': '01000000006',
                'user_type_name': 'user',
            },
            {
                'email': 'sara.farid@lightidea.com',
                'name': 'Sara Farid',
                'phone_number': '01000000007',
                'user_type_name': 'user',
            },
            {
                'email': 'youssef.amin@lightidea.com',
                'name': 'Youssef Amin',
                'phone_number': '01000000008',
                'user_type_name': 'user',
            },
        ]
        
        for user_data in users_data:
            user_type_name = user_data.get('user_type_name', 'user')
            user = CustomUser.objects.filter(email=user_data['email']).first()
            
            if not user:
                if user_type_name == 'super_admin':
                    user = CustomUser.objects.create_superuser(
                        email=user_data['email'],
                        name=user_data['name'],
                        phone_number=user_data['phone_number'],
                        password='password123'
                    )
                else:
                    user = CustomUser.objects.create_user(
                        email=user_data['email'],
                        name=user_data['name'],
                        phone_number=user_data['phone_number'],
                        password='password123',
                        user_type_name=user_type_name
                    )
                self.created_objects['users'].append(user)
                self.stdout.write(f"  ✓ Created {user_type_name}: {user.name}")
            else:
                self.created_objects['users'].append(user)
                self.stdout.write(f"  → Exists: {user.name}")

    def seed_job_roles_structure(self):
        """Seed Job Roles, Pages, Actions, and their relationships"""
        self.stdout.write(self.style.MIGRATE_HEADING('\n2. Seeding Job Roles Structure...'))
        
        # Create Actions
        actions_data = ['view', 'create', 'edit', 'delete']
        actions = {}
        
        for action_name in actions_data:
            action, created = Action.objects.get_or_create(
                name=action_name,
                defaults={
                    'display_name': action_name.capitalize(),
                    'description': f'Can {action_name} records'
                }
            )
            actions[action_name] = action
            if created:
                self.created_objects['actions'].append(action)
                self.stdout.write(f"  ✓ Created Action: {action_name}")
        
        # Create Pages
        pages_data = [
            {
                'name': 'job_roles_management',
                'display_name': 'Job Roles Management',
                'description': 'Manage job roles and permissions',
            },
            {
                'name': 'user_management',
                'display_name': 'User Management',
                'description': 'Manage users and their accounts',
            },
            {
                'name': 'hr_dashboard',
                'display_name': 'HR Dashboard',
                'description': 'General HR Overview',
            },
        ]
        
        pages = {}
        for page_data in pages_data:
            page, created = Page.objects.get_or_create(
                name=page_data['name'],
                defaults=page_data
            )
            pages[page_data['name']] = page
            if created:
                self.created_objects['pages'].append(page)
                self.stdout.write(f"  ✓ Created Page: {page_data['name']}")
        
        # Create PageActions
        page_actions = {}
        for page in pages.values():
            for action in actions.values():
                pa, created = PageAction.objects.get_or_create(
                    page=page,
                    action=action
                )
                page_actions[f"{page.name}_{action.name}"] = pa
                if created:
                    self.stdout.write(f"    → Linked {page.name} + {action.name}")
        
        # Create Job Roles
        job_roles_data = [
            {
                'name': 'System Admin',
                'description': 'Full system access and control',
                'pages': ['job_roles_management', 'user_management', 'hr_dashboard'],
            },
            {
                'name': 'HR Manager',
                'description': 'Manage HR operations and staff',
                'pages': ['user_management', 'hr_dashboard'],
            },
            {
                'name': 'HR Admin',
                'description': 'Administrative HR tasks',
                'pages': ['user_management', 'hr_dashboard'],
            },
            {
                'name': 'Department Manager',
                'description': 'Manage department resources',
                'pages': ['hr_dashboard'],
            },
            {
                'name': 'Employee',
                'description': 'Basic employee access',
                'pages': [],
            },
        ]
        
        for role_data in job_roles_data:
            role, created = JobRole.objects.get_or_create(
                name=role_data['name'],
                defaults={'description': role_data['description']}
            )
            
            if created:
                self.created_objects['job_roles'].append(role)
                self.stdout.write(f"  ✓ Created Job Role: {role_data['name']}")
                
                # Assign page access
                for page_name in role_data['pages']:
                    page = pages[page_name]
                    JobRolePage.objects.get_or_create(
                        job_role=role,
                        page=page
                    )
                    self.stdout.write(f"    → Configured access for {page_name}")
        
        # Assign job roles to users
        # Superadmin
        super_admin_role = JobRole.objects.get(name='System Admin')
        super_admin_user = self.created_objects['users'][0]
        super_admin_user.job_role = super_admin_role
        super_admin_user.save()
        
        # Admins
        hr_manager_role = JobRole.objects.get(name='HR Manager')
        admin1 = self.created_objects['users'][1]
        admin1.job_role = hr_manager_role
        admin1.save()
        
        admin2 = self.created_objects['users'][2]
        admin2.job_role = hr_manager_role
        admin2.save()
        
        # Create sample UserActionDenials for testing
        # user1 is khalid.salem (index 3)
        user1 = self.created_objects['users'][3]
        user1.job_role = super_admin_role # Give him admin role but deny delete
        user1.save()
        
        pa_delete_users = page_actions['user_management_delete']
        
        denial, created = UserActionDenial.objects.get_or_create(
            user=user1,
            page_action=pa_delete_users,
        )
        if created:
            self.stdout.write(f"  ✓ Created UserActionDenial: {user1.email} cannot delete users")

    def seed_hr_structure(self):
        """Seed HR organizational structure"""
        self.stdout.write(self.style.MIGRATE_HEADING('\n3. Seeding HR Structure...'))
        
        # Create Enterprise
        enterprise, created = Enterprise.objects.get_or_create(
            code='lightidea',
            defaults={
                'name': 'Lightidea Technologies',
                'status': StatusChoices.ACTIVE,
            }
        )
        if created:
            self.created_objects['enterprises'].append(enterprise)
            self.stdout.write(f"  ✓ Created Enterprise: {enterprise.name}")
        
        # Create Business Groups
        business_groups_data = [
            {
                'name': 'Gulf Operations',
                'code': 'GULF',
            },
            {
                'name': 'Levant Operations',
                'code': 'LEVANT',
            },
            {
                'name': 'North Africa Operations',
                'code': 'NAFR',
            },
        ]
        
        for bg_data in business_groups_data:
            bg, created = BusinessGroup.objects.get_or_create(
                enterprise=enterprise,
                code=bg_data['code'],
                defaults={
                    'name': bg_data['name'],
                    'status': StatusChoices.ACTIVE,
                }
            )
            if created:
                self.created_objects['business_groups'].append(bg)
                self.stdout.write(f"  ✓ Created Business Group: {bg.name}")
        
        # Create Locations
        locations_data = [
            {'name': 'Dubai Headquarters', 'code': 'DXB', 'city': 'Dubai', 'country': 'UAE', 'bg_code': 'GULF'},
            {'name': 'Riyadh Office', 'code': 'RUH', 'city': 'Riyadh', 'country': 'Saudi Arabia', 'bg_code': 'GULF'},
            {'name': 'Amman Branch', 'code': 'AMM', 'city': 'Amman', 'country': 'Jordan', 'bg_code': 'LEVANT'},
            {'name': 'Cairo Hub', 'code': 'CAI', 'city': 'Cairo', 'country': 'Egypt', 'bg_code': 'NAFR'},
        ]
        
        for loc_data in locations_data:
            bg = BusinessGroup.objects.get(code=loc_data['bg_code'])
            loc, created = Location.objects.get_or_create(
                code=loc_data['code'],
                defaults={
                    'business_group': bg,
                    'enterprise': enterprise,
                    'name': loc_data['name'],
                    'city': loc_data['city'],
                    'country': loc_data['country'],
                    'status': StatusChoices.ACTIVE,
                }
            )
            if created:
                self.created_objects['locations'].append(loc)
                self.stdout.write(f"  ✓ Created Location: {loc.name}")
        
        # Create Departments with hierarchy
        departments_data = [
            {'name': 'Technology & Engineering', 'code': 'TECH', 'parent': None, 'location': 'DXB'},
            {'name': 'Backend Development', 'code': 'BE', 'parent': 'TECH', 'location': 'DXB'},
            {'name': 'Frontend Development', 'code': 'FE', 'parent': 'TECH', 'location': 'DXB'},
            {'name': 'Human Resources', 'code': 'HR', 'parent': None, 'location': 'DXB'},
            {'name': 'Financial Operations', 'code': 'FIN', 'parent': None, 'location': 'RUH'},
            {'name': 'Business Development', 'code': 'BIZDEV', 'parent': None, 'location': 'CAI'},
        ]
        
        # First pass: create departments without parent
        for dept_data in departments_data:
            location = Location.objects.get(code=dept_data['location'])
            bg = location.business_group
            dept, created = Department.objects.get_or_create(
                business_group=bg,
                department_code=dept_data['code'],
                effective_start_date=date.today() - timedelta(days=365),
                defaults={
                    'name': dept_data['name'],
                    'location': location,
                    'status': StatusChoices.ACTIVE,
                }
            )
            if created:
                self.created_objects['departments'].append(dept)
                self.stdout.write(f"  ✓ Created Department: {dept.name}")
        
        # Second pass: set up hierarchy
        for dept_data in departments_data:
            if dept_data['parent']:
                dept = Department.objects.filter(department_code=dept_data['code']).first()
                parent = Department.objects.filter(department_code=dept_data['parent']).first()
                if dept and parent:
                    dept.parent = parent
                    dept.save()
                    self.stdout.write(f"    → Linked {dept.name} under {parent.name}")

    def seed_department_managers(self):
        """Seed Department Managers"""
        self.stdout.write(self.style.MIGRATE_HEADING('\n4. Seeding Department Managers...'))
        
        managers_data = [
            {'user_index': 3, 'dept_code': 'TECH'},  # Khalid Salem
            {'user_index': 4, 'dept_code': 'HR'},    # Nour Ibrahim
            {'user_index': 5, 'dept_code': 'FIN'},   # Ahmad Zahran
        ]
        
        for mgr_data in managers_data:
            user = self.created_objects['users'][mgr_data['user_index']]
            dept = Department.objects.filter(department_code=mgr_data['dept_code']).first()
            
            if dept:
                mgr, created = DepartmentManager.objects.get_or_create(
                    department=dept,
                    manager=user,
                    effective_start_date=date.today() - timedelta(days=180),
                )
                if created:
                    self.stdout.write(f"  ✓ Assigned {user.name} as manager of {dept.name}")

    def seed_grades(self):
        """Seed Grades with GradeRates"""
        self.stdout.write(self.style.MIGRATE_HEADING('\n5. Seeding Grades and Rates...'))
        
        bg = BusinessGroup.objects.get(code='GULF')
        
        grades_data = [
            {'name': 'Junior', 'code': 'JR', 'rates': [
                {'currency': 'AED', 'amount': Decimal('10000')},
                {'currency': 'EGP', 'amount': Decimal('20000')},
            ]},
            {'name': 'Mid-Level', 'code': 'ML', 'rates': [
                {'currency': 'AED', 'amount': Decimal('16000')},
                {'currency': 'EGP', 'amount': Decimal('35000')},
            ]},
            {'name': 'Senior', 'code': 'SR', 'rates': [
                {'currency': 'AED', 'amount': Decimal('26000')},
                {'currency': 'EGP', 'amount': Decimal('60000')},
            ]},
            {'name': 'Lead', 'code': 'LD', 'rates': [
                {'currency': 'AED', 'amount': Decimal('40000')},
            ]},
            {'name': 'Principal', 'code': 'PR', 'rates': [
                {'currency': 'AED', 'amount': Decimal('60000')},
            ]},
        ]
        
        for grade_data in grades_data:
            grade, created = Grade.objects.get_or_create(
                business_group=bg,
                code=grade_data['code'],
                effective_start_date=date.today() - timedelta(days=365),
                defaults={
                    'name': grade_data['name'],
                }
            )
            if created:
                self.created_objects['grades'].append(grade)
                self.stdout.write(f"  ✓ Created Grade: {grade.name}")
                
                # Create grade rates
                for rate_data in grade_data['rates']:
                    GradeRate.objects.get_or_create(
                        grade=grade,
                        currency=rate_data['currency'],
                        rate_type='Base',
                        defaults={
                            'amount': rate_data['amount'],
                            'effective_start_date': date.today() - timedelta(days=90),
                        }
                    )
                    self.stdout.write(f"    → Added {rate_data['currency']} rate")

    def seed_positions(self):
        """Seed Positions with hierarchy"""
        self.stdout.write(self.style.MIGRATE_HEADING('\n6. Seeding Positions...'))
        
        tech_dept = Department.objects.filter(department_code='TECH').first()
        be_dept = Department.objects.filter(department_code='BE').first()
        fe_dept = Department.objects.filter(department_code='FE').first()
        hr_dept = Department.objects.filter(department_code='HR').first()
        
        if not all([tech_dept, be_dept, fe_dept, hr_dept]):
            self.stdout.write(self.style.ERROR('  ✗ Required departments not found, skipping positions'))
            return

        loc_dxb = Location.objects.get(code='DXB')
        
        positions_data = [
            {'title': 'VP of Technology', 'code': 'VP-TECH', 'dept': tech_dept, 'grade': 'PR', 'parent': None},
            {'title': 'Engineering Manager', 'code': 'EM', 'dept': tech_dept, 'grade': 'LD', 'parent': 'VP-TECH'},
            {'title': 'Senior Backend Engineer', 'code': 'SBE', 'dept': be_dept, 'grade': 'SR', 'parent': 'EM'},
            {'title': 'Backend Engineer', 'code': 'BE', 'dept': be_dept, 'grade': 'ML', 'parent': 'SBE'},
            {'title': 'Junior Backend Engineer', 'code': 'JBE', 'dept': be_dept, 'grade': 'JR', 'parent': 'BE'},
            {'title': 'Senior Frontend Engineer', 'code': 'SFE', 'dept': fe_dept, 'grade': 'SR', 'parent': 'EM'},
            {'title': 'Frontend Engineer', 'code': 'FE', 'dept': fe_dept, 'grade': 'ML', 'parent': 'SFE'},
            {'title': 'HR Director', 'code': 'HR-DIR', 'dept': hr_dept, 'grade': 'LD', 'parent': None},
            {'title': 'HR Business Partner', 'code': 'HRBP', 'dept': hr_dept, 'grade': 'SR', 'parent': 'HR-DIR'},
            {'title': 'HR Coordinator', 'code': 'HRC', 'dept': hr_dept, 'grade': 'JR', 'parent': 'HRBP'},
        ]
        
        # First pass: create positions
        for pos_data in positions_data:
            grade = Grade.objects.filter(code=pos_data['grade']).first()
            if not grade: continue
            
            pos, created = Position.objects.get_or_create(
                code=pos_data['code'],
                effective_start_date=date.today() - timedelta(days=365),
                defaults={
                    'name': pos_data['title'],
                    'department': pos_data['dept'],
                    'location': loc_dxb,
                    'grade': grade,
                    'status': StatusChoices.ACTIVE,
                }
            )
            if created:
                self.created_objects['positions'].append(pos)
                self.stdout.write(f"  ✓ Created Position: {pos.name}")
        
        # Second pass: set up hierarchy
        for pos_data in positions_data:
            if pos_data['parent']:
                pos = Position.objects.filter(code=pos_data['code']).first()
                parent = Position.objects.filter(code=pos_data['parent']).first()
                if pos and parent:
                    pos.reports_to = parent
                    pos.save()
                    self.stdout.write(f"    → {pos.name} reports to {parent.name}")

    def seed_user_data_scopes(self):
        """Seed UserDataScopes linking users to business groups"""
        self.stdout.write(self.style.MIGRATE_HEADING('\n7. Seeding User Data Scopes...'))
        
        scopes_data = [
            {'user_index': 0, 'bg_code': 'GULF', 'is_global': True},
            {'user_index': 1, 'bg_code': 'LEVANT', 'is_global': False},
            {'user_index': 2, 'bg_code': 'NAFR', 'is_global': False},
        ]
        
        for scope_data in scopes_data:
            user = self.created_objects['users'][scope_data['user_index']]
            bg = BusinessGroup.objects.get(code=scope_data['bg_code'])
            
            scope, created = UserDataScope.objects.get_or_create(
                user=user,
                business_group=bg,
                defaults={
                    'is_global': scope_data['is_global'],
                }
            )
            if created:
                self.stdout.write(f"  ✓ Granted {user.email} access to {bg.name}")

    def print_summary(self):
        """Print summary of created objects"""
        self.stdout.write(self.style.SUCCESS('\nSummary of Created Objects:'))
        self.stdout.write(self.style.SUCCESS('-' * 60))
        
        summary = {
            'Users': len(self.created_objects['users']),
            'Job Roles': len(self.created_objects['job_roles']),
            'Pages': len(self.created_objects['pages']),
            'Actions': len(self.created_objects['actions']),
            'Enterprises': len(self.created_objects['enterprises']),
            'Business Groups': len(self.created_objects['business_groups']),
            'Locations': len(self.created_objects['locations']),
            'Departments': len(self.created_objects['departments']),
            'Grades': len(self.created_objects['grades']),
            'Positions': len(self.created_objects['positions']),
        }
        
        for label, count in summary.items():
            self.stdout.write(f"  • {label}: {count}")
        
        self.stdout.write(self.style.SUCCESS('\nDefault Login Credentials:'))
        self.stdout.write(self.style.SUCCESS('-' * 60))
        self.stdout.write('  Emails: superadmin@lightidea.com / admin1@lightidea.com / ...')
        self.stdout.write('  Password: password123')
        self.stdout.write('')
