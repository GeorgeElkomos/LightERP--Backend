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

from core.user_accounts.models import CustomUser
from core.job_roles.models import JobRole


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
            call_command('loaddata', 'initial_roles_and_pages.json')
            
            # Load HR structure
            self.stdout.write("Loading HR Structure...")
            call_command('loaddata', 'initial_hr_structure.json')
            
            # Load Users
            self.stdout.write("Loading Seed Users...")
            call_command('loaddata', 'seed_users.json')
            
            self.stdout.write(self.style.SUCCESS('\n' + '='*60))
            self.stdout.write(self.style.SUCCESS('SEEDING COMPLETED SUCCESSFULLY VIA FIXTURES'))
            self.stdout.write(self.style.SUCCESS('='*60))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error seeding data: {str(e)}"))

    def print_summary(self):
        # We can still print a summary if we want by querying the DB
        pass
