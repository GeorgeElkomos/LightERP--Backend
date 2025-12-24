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
            'actions': []
        }

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Starting comprehensive data seeding using fixtures...'))
        
        from django.core.management import call_command
        
        try:
            # Load basic structure
            self.stdout.write("Loading seed data for job_roles app...")
            call_command('loaddata', 'job_roles_test_data.json')
            
            
            self.stdout.write(self.style.SUCCESS('\n' + '='*60))
            self.stdout.write(self.style.SUCCESS('SEEDING COMPLETED SUCCESSFULLY VIA FIXTURES'))
            self.stdout.write(self.style.SUCCESS('='*60))
            self.stdout.write(self.style.SUCCESS('Test Users (all passwords: "password123"):'))
            self.stdout.write(self.style.SUCCESS('  1. superadmin@lightidea.com'))
            self.stdout.write(self.style.SUCCESS('  2. admin@lightidea.com'))
            self.stdout.write(self.style.SUCCESS('  3. accountant@lightidea.com'))
            self.stdout.write(self.style.SUCCESS('  4. hrmanager@lightidea.com'))
            self.stdout.write(self.style.SUCCESS('  5. sales@lightidea.com'))
            self.stdout.write(self.style.SUCCESS('  6. inventory@lightidea.com'))
            self.stdout.write(self.style.SUCCESS('='*60))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error seeding data: {str(e)}"))

