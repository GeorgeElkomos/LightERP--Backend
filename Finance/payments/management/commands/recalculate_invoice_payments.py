"""
Django management command to recalculate all invoice paid_amount values.

This command will:
1. Find all invoices
2. Calculate their paid_amount from payment allocations
3. Fix any inconsistencies
4. Report the results

Usage:
    python manage.py recalculate_invoice_payments
    python manage.py recalculate_invoice_payments --dry-run
    python manage.py recalculate_invoice_payments --verbose
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from decimal import Decimal

from Finance.Invoice.models import Invoice


class Command(BaseCommand):
    help = 'Recalculate paid_amount for all invoices based on payment allocations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without actually updating the database',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output for each invoice',
        )
        parser.add_argument(
            '--invoice-id',
            type=int,
            help='Process only a specific invoice by ID',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']
        invoice_id = options.get('invoice_id')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be saved'))
        
        # Get invoices to process
        if invoice_id:
            invoices = Invoice.objects.filter(id=invoice_id)
            if not invoices.exists():
                raise CommandError(f'Invoice with ID {invoice_id} does not exist')
        else:
            invoices = Invoice.objects.all()
        
        total_count = invoices.count()
        fixed_count = 0
        error_count = 0
        
        self.stdout.write(f'Processing {total_count} invoice(s)...\n')
        
        for invoice in invoices:
            try:
                # Get validation data
                is_valid, expected, actual, difference = invoice.validate_paid_amount()
                
                if not is_valid:
                    fixed_count += 1
                    
                    if verbose or not dry_run:
                        self.stdout.write(
                            self.style.WARNING(
                                f'Invoice {invoice.id}: '
                                f'Expected={expected}, Actual={actual}, Diff={difference}'
                            )
                        )
                    
                    if not dry_run:
                        # Fix the inconsistency
                        old, new, changed = invoice.recalculate_paid_amount()
                        
                        if changed:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'  ✓ Fixed: {old} → {new}'
                                )
                            )
                        else:
                            self.stdout.write(
                                self.style.ERROR(
                                    f'  ✗ Failed to fix (this should not happen)'
                                )
                            )
                            error_count += 1
                elif verbose:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Invoice {invoice.id}: OK (paid_amount={actual})'
                        )
                    )
            
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'Invoice {invoice.id}: Error - {str(e)}'
                    )
                )
        
        # Summary
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(f'Total invoices processed: {total_count}')
        self.stdout.write(f'Inconsistencies found: {fixed_count}')
        self.stdout.write(f'Errors: {error_count}')
        
        if dry_run and fixed_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'\nRun without --dry-run to fix {fixed_count} invoice(s)'
                )
            )
        elif not dry_run and fixed_count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Successfully fixed {fixed_count} invoice(s)'
                )
            )
        elif fixed_count == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    '\n✓ All invoices have correct paid_amount values'
                )
            )
