"""
Script to fix PR test files to match actual response format.

Fixes:
1. Adds authentication to catalog PR tests
2. Updates response.data['xxx'] to response.data['data']['xxx']
3. Preserves response.data['status'] and response.data['message'] (not nested)
"""

import re
import os

def fix_test_file(filepath):
    """Fix a single test file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Fix 1: Add authentication to CatalogPRCreateTests if missing
    if 'CatalogPRCreateTests' in content and 'force_authenticate' not in content:
        # Find the setUp method in CatalogPRCreateTests
        pattern = r'(class CatalogPRCreateTests.*?def setUp\(self\):.*?"""Set up test data""".*?self\.client = APIClient\(\))'
        replacement = r'\1\n        \n        # Create test user\n        self.user = get_or_create_test_user()\n        self.client.force_authenticate(user=self.user)'
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    # Fix 2: Add authentication to all other test classes that are missing it
    # Pattern: class XXXTests(TestCase): ... def setUp(self): ... self.client = APIClient()
    # But NOT if force_authenticate is already there
    test_class_pattern = r'(class \w+Tests\(TestCase\):.*?def setUp\(self\):.*?""".*?""".*?self\.client = APIClient\(\))'
    
    def add_auth_if_missing(match):
        matched_text = match.group(0)
        if 'force_authenticate' not in matched_text:
            # Insert after APIClient()
            return matched_text + '\n        \n        # Create test user\n        self.user = get_or_create_test_user()\n        self.client.force_authenticate(user=self.user)'
        return matched_text
    
    content = re.sub(test_class_pattern, add_auth_if_missing, content, flags=re.DOTALL)
    
    # Fix 3: Replace response.data['field'] with response.data['data']['field']
    # BUT NOT for 'status' and 'message' which are at top level
    # Pattern: response.data['anything_except_status_or_message']
    
    # First, let's find all response.data['xxx'] patterns
    patterns_to_fix = [
        (r"response\.data\['pr_id'\]", r"response.data['data']['pr_id']"),
        (r"response\.data\['pr_number'\]", r"response.data['data']['pr_number']"),
        (r"response\.data\['requester_name'\]", r"response.data['data']['requester_name']"),
        (r"response\.data\['requester_department'\]", r"response.data['data']['requester_department']"),
        (r"response\.data\['items'\]", r"response.data['data']['items']"),
        (r"response\.data\['total'\]", r"response.data['data']['total']"),
        (r"response\.data\['date'\]", r"response.data['data']['date']"),
        (r"response\.data\['required_date'\]", r"response.data['data']['required_date']"),
        (r"response\.data\['priority'\]", r"response.data['data']['priority']"),
        (r"response\.data\['description'\]", r"response.data['data']['description']"),
        (r"response\.data\['notes'\]", r"response.data['data']['notes']"),
        (r"response\.data\['created_at'\]", r"response.data['data']['created_at']"),
        (r"response\.data\['updated_at'\]", r"response.data['data']['updated_at']"),
        (r"response\.data\['approved_at'\]", r"response.data['data']['approved_at']"),
        (r"response\.data\['rejected_at'\]", r"response.data['data']['rejected_at']"),
        (r"response\.data\['rejection_reason'\]", r"response.data['data']['rejection_reason']"),
    ]
    
    for pattern, replacement in patterns_to_fix:
        content = re.sub(pattern, replacement, content)
    
    # Fix 4: Also need to fix the assertIn checks
    # assertIn('pr_id', response.data) should become assertIn('data', response.data)
    # followed by assertIn('pr_id', response.data['data'])
    # But for simplicity, let's just change the assertion
    content = re.sub(
        r"self\.assertIn\('pr_id', response\.data\)",
        r"self.assertIn('data', response.data)\n        self.assertIn('pr_id', response.data['data'])",
        content
    )
    content = re.sub(
        r"self\.assertIn\('pr_number', response\.data\)",
        r"self.assertIn('pr_number', response.data['data'])",
        content
    )
    
    # Save if changed
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✓ Fixed {os.path.basename(filepath)}")
        return True
    else:
        print(f"- No changes needed for {os.path.basename(filepath)}")
        return False


# Fix all three test files
test_files = [
    r'c:\Users\samys\OneDrive\Documents\GitHub\ERP\procurement\PR\tests\test_catalog_pr.py',
    r'c:\Users\samys\OneDrive\Documents\GitHub\ERP\procurement\PR\tests\test_noncatalog_pr.py',
    r'c:\Users\samys\OneDrive\Documents\GitHub\ERP\procurement\PR\tests\test_service_pr.py',
]

print("Fixing PR test files...")
print("=" * 60)

fixed_count = 0
for filepath in test_files:
    if fix_test_file(filepath):
        fixed_count += 1

print("=" * 60)
print(f"Complete! Fixed {fixed_count} file(s).")
