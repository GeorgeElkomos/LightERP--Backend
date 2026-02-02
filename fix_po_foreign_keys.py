"""Fix PO records with invalid foreign keys"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_project.settings')
django.setup()

from procurement.po.models import POHeader
from core.user_accounts.models import UserAccount

# Get a valid user to use as replacement
valid_user = UserAccount.objects.first()
if not valid_user:
    print("✗ No valid users found in the system!")
    exit(1)

print(f"Using user {valid_user.id} as replacement")

# Find and fix POs with invalid user references
count_updated = 0

# Fix created_by
pos_with_invalid_created_by = POHeader.objects.filter(created_by_id=6)
if pos_with_invalid_created_by.exists():
    count = pos_with_invalid_created_by.count()
    pos_with_invalid_created_by.update(created_by_id=valid_user.id)
    print(f"✓ Fixed {count} POs with invalid created_by_id")
    count_updated += count

# Fix submitted_by
pos_with_invalid_submitted_by = POHeader.objects.filter(submitted_by_id=6)
if pos_with_invalid_submitted_by.exists():
    count = pos_with_invalid_submitted_by.count()
    pos_with_invalid_submitted_by.update(submitted_by_id=valid_user.id)
    print(f"✓ Fixed {count} POs with invalid submitted_by_id")
    count_updated += count

if count_updated == 0:
    print("✓ No problematic POs found")
else:
    print(f"\n✓ Total: Fixed {count_updated} foreign key references")
