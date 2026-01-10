#!/usr/bin/env python
"""Fix BankStatementLineMatch field names - replace updated_by with matched_by."""

import re

file_path = r'Finance\cash_management\tests\test_comprehensive_api.py'

# Read the file
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Count occurrences
count_before = content.count('updated_by=self.user')

# Replace updated_by with matched_by in BankStatementLineMatch.objects.create contexts
# We need to be careful to only replace within BankStatementLineMatch contexts
lines = content.split('\n')
result_lines = []
in_match_create = False

for i, line in enumerate(lines):
    if 'BankStatementLineMatch.objects.create(' in line:
        in_match_create = True
        result_lines.append(line)
    elif in_match_create:
        if 'updated_by=self.user' in line:
            line = line.replace('updated_by=self.user', 'matched_by=self.user')
        result_lines.append(line)
        if ')' in line and not line.strip().endswith(','):
            in_match_create = False
    else:
        result_lines.append(line)

content = '\n'.join(result_lines)

# Write the changes back
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Fixed {count_before} instances of updated_by in BankStatementLineMatch creations")
