"""
Custom management command to run all project tests.
Usage: python manage.py test_all
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
import sys


class Command(BaseCommand):
    help = 'Run all tests in the entire project'

    def add_arguments(self, parser):
        # Django BaseCommand already provides --verbosity, --keepdb, etc.
        # We just need to add custom arguments if any
        pass

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('='*80))
        self.stdout.write(self.style.SUCCESS('Running All Project Tests'))
        self.stdout.write(self.style.SUCCESS('='*80))
        self.stdout.write('')
        
        verbosity = options.get('verbosity', 1)
        keepdb = options.get('keepdb', False)
        failfast = options.get('failfast', False)
        
        try:
            # Run ALL tests in the project using pattern matching
            # This will discover all test_*.py files in all apps automatically
            call_command(
                'test',
                '--pattern=test_*.py',
                verbosity=verbosity,
                keepdb=keepdb,
                failfast=failfast
            )
            
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('='*80))
            self.stdout.write(self.style.SUCCESS('✓ ALL TESTS PASSED'))
            self.stdout.write(self.style.SUCCESS('='*80))
            
        except SystemExit as e:
            if e.code != 0:
                self.stdout.write('')
                self.stdout.write(self.style.ERROR('='*80))
                self.stdout.write(self.style.ERROR('✗ SOME TESTS FAILED'))
                self.stdout.write(self.style.ERROR('='*80))
                sys.exit(1)
