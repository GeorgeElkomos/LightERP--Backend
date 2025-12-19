# Generated data migration for HR job roles

from django.db import migrations


def create_hr_roles(apps, schema_editor):
    """Create HR Administrator and HR Manager roles with permissions"""
    JobRole = apps.get_model('job_roles', 'JobRole')
    Page = apps.get_model('job_roles', 'Page')
    Action = apps.get_model('job_roles', 'Action')
    PageAction = apps.get_model('job_roles', 'PageAction')
    JobRolePage = apps.get_model('job_roles', 'JobRolePage')
    
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
        {
            'name': 'hr_enterprise',
            'display_name': 'HR - Enterprises',
            'description': 'Manage enterprise organizational structure'
        },
        {
            'name': 'hr_business_group',
            'display_name': 'HR - Business Groups',
            'description': 'Manage business groups within enterprises'
        },
        {
            'name': 'hr_location',
            'display_name': 'HR - Locations',
            'description': 'Manage physical or logical workplace locations'
        },
        {
            'name': 'hr_department',
            'display_name': 'HR - Departments',
            'description': 'Manage departments and their hierarchies'
        },
        {
            'name': 'hr_department_manager',
            'display_name': 'HR - Department Managers',
            'description': 'Manage department manager assignments'
        },
        {
            'name': 'hr_position',
            'display_name': 'HR - Positions',
            'description': 'Manage job positions'
        },
        {
            'name': 'hr_grade',
            'display_name': 'HR - Grades',
            'description': 'Manage job grades and grade rates'
        },
    ]
    
    hr_pages = []
    for page_data in hr_pages_data:
        page, _ = Page.objects.get_or_create(
            name=page_data['name'],
            defaults={
                'display_name': page_data['display_name'],
                'description': page_data['description']
            }
        )
        hr_pages.append(page)
        
        # Link all actions to this page
        for action in actions:
            PageAction.objects.get_or_create(
                page=page,
                action=action
            )
    
    # Create HR Administrator role
    hr_admin_role, _ = JobRole.objects.get_or_create(
        name='HR Administrator',
        defaults={
            'description': (
                'Full administrative access to all HR modules. '
                'Can create enterprises, business groups, locations, departments, '
                'department managers, positions, grades, and grade rates. '
                'Can view and update all details except entity codes.'
            )
        }
    )
    
    # Grant HR Administrator access to all HR pages
    for page in hr_pages:
        JobRolePage.objects.get_or_create(
            job_role=hr_admin_role,
            page=page
        )
    
    # Create HR Manager role
    hr_manager_role, _ = JobRole.objects.get_or_create(
        name='HR Manager',
        defaults={
            'description': (
                'View-only access to department information. '
                'Can view department details but cannot create or modify data.'
            )
        }
    )
    
    # Grant HR Manager access to hr_department page only
    department_page = Page.objects.get(name='hr_department')
    JobRolePage.objects.get_or_create(
        job_role=hr_manager_role,
        page=department_page
    )


def reverse_hr_roles(apps, schema_editor):
    """Remove HR roles and related data"""
    JobRole = apps.get_model('job_roles', 'JobRole')
    Page = apps.get_model('job_roles', 'Page')
    
    # Delete job roles
    JobRole.objects.filter(name__in=['HR Administrator', 'HR Manager']).delete()
    
    # Delete HR pages
    Page.objects.filter(name__startswith='hr_').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('job_roles', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_hr_roles, reverse_hr_roles),
    ]
