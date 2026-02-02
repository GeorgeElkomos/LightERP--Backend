"""Fix ALL foreign key references to non-existent user_id=6"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_project.settings')
django.setup()

from django.apps import apps
from core.user_accounts.models import UserAccount

# Get a valid user
valid_user = UserAccount.objects.first()
if not valid_user:
    print("✗ No valid users found!")
    exit(1)

print(f"Using user_id={valid_user.id} as replacement for user_id=6\n")

# Find all models with user_id fields
total_fixed = 0

for model in apps.get_models():
    for field in model._meta.fields:
        if field.name in ['user_id', 'created_by_id', 'submitted_by_id', 'approved_by_id', 'rejected_by_id']:
            try:
                # Check if any records reference user_id=6
                queryset = model.objects.filter(**{field.name: 6})
                count = queryset.count()
                
                if count > 0:
                    print(f"Fixing {count} records in {model._meta.db_table}.{field.name}")
                    queryset.update(**{field.name: valid_user.id})
                    total_fixed += count
            except Exception as e:
                # Skip if field doesn't support this operation
                pass

print(f"\n✓ Fixed {total_fixed} total foreign key references")
