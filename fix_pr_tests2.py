"""
Script to fix remaining PR test assertion issues
"""

import re

def fix_remaining_test_issues(filepath):
    """Fix remaining test assertion issues."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Fix 1: response.data['status'] assertions that expect PR status should use response.data['data']['status']
    # BUT NOT response.data['status'] == status.HTTP_200_OK (that's HTTP status code)
    # Pattern: self.assertEqual(response.data['status'], 'DRAFT') or 'APPROVED' etc
    content = re.sub(
        r"self\.assertEqual\(response\.data\['status'\], '(DRAFT|APPROVED|PENDING|REJECTED|CANCELLED)'\)",
        r"self.assertEqual(response.data['data']['status'], '\1')",
        content
    )
    
    # Fix 2: self.assertIn('items', response.data) should be assertIn('items', response.data['data'])
    content = re.sub(
        r"self\.assertIn\('items', response\.data\)",
        r"self.assertIn('items', response.data['data'])",
        content
    )
    
    # Fix 3: self.assertIn('error', response.data) should check response.data['status'] == 'error'
    content = re.sub(
        r"self\.assertIn\('error', response\.data\)",
        r"self.assertEqual(response.data['status'], 'error')",
        content
    )
    
    # Fix 4: response.data['detail'] in error responses should be response.data['data']['detail']
    # But only in contexts where we're checking error details
    content = re.sub(
        r"response\.data\['detail'\]",
        r"response.data['data']['detail']",
        content
    )
    
    # Save if changed
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False


# Fix all three test files
test_files = [
    r'c:\Users\samys\OneDrive\Documents\GitHub\ERP\procurement\PR\tests\test_catalog_pr.py',
    r'c:\Users\samys\OneDrive\Documents\GitHub\ERP\procurement\PR\tests\test_noncatalog_pr.py',
    r'c:\Users\samys\OneDrive\Documents\GitHub\ERP\procurement\PR\tests\test_service_pr.py',
]

print("Fixing remaining PR test assertion issues...")
print("=" * 60)

fixed_count = 0
for filepath in test_files:
    import os
    if fix_remaining_test_issues(filepath):
        print(f"✓ Fixed {os.path.basename(filepath)}")
        fixed_count += 1
    else:
        print(f"- No changes needed for {os.path.basename(filepath)}")

print("=" * 60)
print(f"Complete! Fixed {fixed_count} file(s).")
