"""
Management command to seed the database with realistic test data.

Usage: python manage.py seed_all_data
"""

from django.core.management.base import BaseCommand


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
        self.stdout.write(self.style.WARNING('Starting comprehensive data seeding using fixtures...'))
        
        from django.core.management import call_command
        
        try:
            # Load basic structure
            self.stdout.write("Loading Job Roles and Pages...")
            call_command('loaddata', 'initial_roles_pages_actions.json')
            
            # Load Grade Rate Types (must be before HR structure)
            self.stdout.write("Loading Grade Rate Types...")
            call_command('loaddata', 'initial_grade_rate_types.json')
            
            # Load HR structure
            self.stdout.write("Loading HR Structure...")
            call_command('loaddata', 'initial_hr_structure.json')
            
            # Load Users (Enhanced with 5 users)
            self.stdout.write("Loading Enhanced Seed Users...")
            call_command('loaddata', 'enhanced_users.json')

            # Load data scopes (Enhanced with 5 users)
            self.stdout.write("Loading Enhanced Data Scopes...")
            call_command('loaddata', 'enhanced_data_scopes.json')
            
            # Load Department Managers
            self.stdout.write("Loading Department Managers...")
            call_command('loaddata', 'department_managers.json')
            
            self.stdout.write(self.style.SUCCESS('\n' + '='*60))
            self.stdout.write(self.style.SUCCESS('SEEDING COMPLETED SUCCESSFULLY VIA FIXTURES'))
            self.stdout.write(self.style.SUCCESS('='*60))
            self.stdout.write(self.style.SUCCESS('Test Users (all passwords: "password123"):'))
            self.stdout.write(self.style.SUCCESS('  1. superadmin@lightidea.com (Global Admin)'))
            self.stdout.write(self.style.SUCCESS('  2. admin1@lightidea.com (GULF BG Admin)'))
            self.stdout.write(self.style.SUCCESS('  3. admin2@lightidea.com (LEVANT BG Manager)'))
            self.stdout.write(self.style.SUCCESS('  4. manager.egypt@lightidea.com (Egypt IT Dept Manager)'))
            self.stdout.write(self.style.SUCCESS('  5. manager.levant@lightidea.com (Lebanon Sales Dept Manager)'))
            self.stdout.write(self.style.SUCCESS('='*60))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error seeding data: {str(e)}"))

