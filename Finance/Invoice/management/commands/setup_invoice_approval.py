"""
Management command to create Invoice approval workflow template.

This creates a 3-stage workflow:
1. Accountant Review - Basic validation and verification
2. Finance Manager Review - Financial approval
3. CFO Review - Final executive approval

Usage:
    python manage.py setup_invoice_approval
    python manage.py setup_invoice_approval --delete  # Delete and recreate
"""

from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from core.approval.models import (
    ApprovalWorkflowTemplate,
    ApprovalWorkflowStageTemplate,
)
from Finance.Invoice.models import Invoice


class Command(BaseCommand):
    help = 'Create Invoice approval workflow template with 3 stages'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Delete existing Invoice workflow templates before creating new one',
        )

    def handle(self, *args, **options):
        with transaction.atomic():
            invoice_ct = ContentType.objects.get_for_model(Invoice)
            
            # Delete existing if requested
            if options['delete']:
                deleted_count = ApprovalWorkflowTemplate.objects.filter(
                    content_type=invoice_ct
                ).delete()[0]
                if deleted_count > 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Deleted {deleted_count} existing Invoice workflow templates'
                        )
                    )
            
            # Check if template already exists
            existing = ApprovalWorkflowTemplate.objects.filter(
                content_type=invoice_ct,
                name='Invoice Approval Workflow'
            ).first()
            
            if existing:
                self.stdout.write(
                    self.style.WARNING(
                        f'Invoice workflow template already exists (ID: {existing.id}). '
                        'Use --delete to recreate.'
                    )
                )
                return
            
            # Create workflow template
            template = ApprovalWorkflowTemplate.objects.create(
                content_type=invoice_ct,
                name='Invoice Approval Workflow',
                description='Standard 3-stage approval workflow for all invoices (AP, AR, OneTime)',
            )
            
            # Stage 1: Accountant Review
            stage1 = ApprovalWorkflowStageTemplate.objects.create(
                workflow_template=template,
                name='Accountant Review',
                order_index=1,
                decision_policy=ApprovalWorkflowStageTemplate.POLICY_ALL,
                # TODO: Uncomment and set required_role after creating Role objects
                # required_role=accountant_role,  # Only accountants can approve this stage
            )
            
            # Stage 2: Finance Manager Review
            stage2 = ApprovalWorkflowStageTemplate.objects.create(
                workflow_template=template,
                name='Finance Manager Review',
                order_index=2,
                decision_policy=ApprovalWorkflowStageTemplate.POLICY_ALL,
                # TODO: Uncomment and set required_role after creating Role objects
                # required_role=finance_manager_role,  # Only finance managers can approve
            )
            
            # Stage 3: CFO Review (Final Approval)
            stage3 = ApprovalWorkflowStageTemplate.objects.create(
                workflow_template=template,
                name='CFO Review',
                order_index=3,
                decision_policy=ApprovalWorkflowStageTemplate.POLICY_ALL,
                # TODO: Uncomment and set required_role after creating Role objects
                # required_role=cfo_role,  # Only CFO can approve
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully created Invoice approval workflow template (ID: {template.id})'
                )
            )
            self.stdout.write(f'  Stage 1: {stage1.name} (order_index={stage1.order_index})')
            self.stdout.write(f'  Stage 2: {stage2.name} (order_index={stage2.order_index})')
            self.stdout.write(f'  Stage 3: {stage3.name} (order_index={stage3.order_index})')
            self.stdout.write('')
            self.stdout.write(
                self.style.WARNING(
                    'TODO: Configure required_role in each stage after creating Role objects!'
                )
            )
            self.stdout.write('')
            self.stdout.write('Next steps:')
            self.stdout.write('  1. Create Role objects (accountant, finance_manager, cfo)')
            self.stdout.write('  2. Update stage templates with required_role')
            self.stdout.write('  3. Assign users to roles')
            self.stdout.write('  4. Test workflow with sample invoice')
