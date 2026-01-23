"""
Script to update test files with proper user creation
"""
import re
import os

test_dir = 'Finance/budget_control/tests'
test_files = [
    'test_budget_check.py',
    'test_segments_amounts_crud.py',
    'test_budget_summary.py',
    'test_budget_integration.py',
    'test_budget_excel.py',
    'test_budget_permissions.py'
]

for filename in test_files:
    filepath = os.path.join(test_dir, filename)
    if not os.path.exists(filepath):
        print(f'Skipped: {filename} (not found)')
        continue
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace imports - remove User = get_user_model()
    old_import = """from django.contrib.auth import get_user_model

User = get_user_model()"""
    
    new_import = "from Finance.budget_control.tests.test_utils import create_test_user, create_admin_user"
    
    content = content.replace(old_import, new_import)
    
    # Replace simple User.objects.create_user calls
    content = re.sub(
        r"""User\.objects\.create_user\(\s*username='(\w+)',\s*email='([^']+)',\s*password='([^']+)'\s*\)""",
        r"create_test_user(username='\1', email='\2', password='\3')",
        content
    )
    
    # Replace User.objects.create_user with is_staff=True
    content = re.sub(
        r"""User\.objects\.create_user\(\s*username='(\w+)',\s*email='([^']+)',\s*password='([^']+)',\s*is_staff=True\s*\)""",
        r"create_admin_user(username='\1', email='\2', password='\3')",
        content
    )
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f'Updated: {filename}')

print('\nAll test files updated successfully!')
