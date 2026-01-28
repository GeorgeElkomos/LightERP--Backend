"""
Initialize Core System Data

This management command populates the database with core system data:
- Actions (view, create, edit, delete)
- Pages (user_management, job_role_management, permission_override_management)
- Job Role (admin with access to all pages)

Usage:
    python manage.py init_core_data

This is idempotent - safe to run multiple times.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from core.job_roles.models import Action, Page, JobRole, PageAction, JobRolePage
from core.job_roles.core_config import CORE_ACTIONS, CORE_PAGES, CORE_JOB_ROLES


class Command(BaseCommand):
    help = 'Initialize core system data (actions, pages, job roles)'

    def handle(self, *args, **options):
        self.stdout.write('Starting core data initialization...\n')

        try:
            with transaction.atomic():
                # 1. Create Actions
                self.stdout.write('Creating actions...')
                actions_created = 0
                for action_data in CORE_ACTIONS:
                    action, created = Action.objects.get_or_create(
                        code=action_data['code'],
                        defaults={
                            'name': action_data['name'],
                            'description': action_data['description']
                        }
                    )
                    if created:
                        actions_created += 1
                        self.stdout.write(f"  ✓ Created action: {action.code}")
                    else:
                        self.stdout.write(f"  - Action already exists: {action.code}")

                self.stdout.write(self.style.SUCCESS(f"\n✓ Actions: {actions_created} created, {len(CORE_ACTIONS) - actions_created} already existed\n"))

                # 2. Create Pages
                self.stdout.write('Creating pages...')
                pages_created = 0
                for page_data in CORE_PAGES:
                    page, created = Page.objects.get_or_create(
                        code=page_data['code'],
                        defaults={
                            'name': page_data['name'],
                            'description': page_data['description'],
                            'module_code': page_data['module_code'],
                            'sort_order': page_data['sort_order'],
                            'parent_page': None
                        }
                    )
                    if created:
                        pages_created += 1
                        self.stdout.write(f"  ✓ Created page: {page.code}")
                    else:
                        self.stdout.write(f"  - Page already exists: {page.code}")

                    # Assign actions to page
                    page_actions_created = 0
                    for action_code in page_data['actions']:
                        action = Action.objects.get(code=action_code)
                        page_action, pa_created = PageAction.objects.get_or_create(
                            page=page,
                            action=action
                        )
                        if pa_created:
                            page_actions_created += 1

                    if page_actions_created > 0:
                        self.stdout.write(f"    → Assigned {page_actions_created} actions to {page.code}")

                self.stdout.write(self.style.SUCCESS(f"\n✓ Pages: {pages_created} created, {len(CORE_PAGES) - pages_created} already existed\n"))

                # 3. Create Job Roles
                self.stdout.write('Creating job roles...')
                roles_created = 0
                for role_data in CORE_JOB_ROLES:
                    role, created = JobRole.objects.get_or_create(
                        code=role_data['code'],
                        defaults={
                            'name': role_data['name'],
                            'description': role_data['description'],
                            'priority': role_data['priority'],
                            'parent_role': None
                        }
                    )
                    if created:
                        roles_created += 1
                        self.stdout.write(f"  ✓ Created role: {role.code}")
                    else:
                        self.stdout.write(f"  - Role already exists: {role.code}")

                    # Assign pages to role
                    if role_data['pages'] == 'ALL':
                        # Assign all pages to admin
                        all_pages = Page.objects.all()
                        role_pages_created = 0
                        for page in all_pages:
                            role_page, rp_created = JobRolePage.objects.get_or_create(
                                job_role=role,
                                page=page,
                                defaults={'inherit_to_children': True}
                            )
                            if rp_created:
                                role_pages_created += 1

                        if role_pages_created > 0:
                            self.stdout.write(f"    → Assigned ALL pages ({role_pages_created}) to {role.code}")
                        else:
                            self.stdout.write(f"    - All pages already assigned to {role.code}")

                self.stdout.write(self.style.SUCCESS(f"\n✓ Job Roles: {roles_created} created, {len(CORE_JOB_ROLES) - roles_created} already existed\n"))

                # Summary
                self.stdout.write(self.style.SUCCESS('\n' + '='*60))
                self.stdout.write(self.style.SUCCESS('CORE DATA INITIALIZATION COMPLETE'))
                self.stdout.write(self.style.SUCCESS('='*60))
                self.stdout.write(f"\n📋 Actions: {len(CORE_ACTIONS)} total")
                self.stdout.write(f"📄 Pages: {len(CORE_PAGES)} total")
                self.stdout.write(f"👥 Job Roles: {len(CORE_JOB_ROLES)} total")

                # Show what was created vs existed
                if actions_created + pages_created + roles_created > 0:
                    self.stdout.write(f"\n✨ Created: {actions_created} actions, {pages_created} pages, {roles_created} roles")
                else:
                    self.stdout.write(f"\n✓ All data already exists - no changes made")

                self.stdout.write(self.style.SUCCESS('\n✅ Success!\n'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error: {str(e)}\n'))
            raise

