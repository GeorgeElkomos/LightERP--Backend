#!/usr/bin/env python
"""Add match_type='MANUAL' to all BankStatementLineMatch creations."""

import re

file_path = r'Finance\cash_management\tests\test_comprehensive_api.py'

# Read the file
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find all BankStatementLineMatch.objects.create blocks and add match_type if missing
lines = content.split('\n')
result_lines = []
in_match_create = False
match_create_lines = []
indent_level = 0

for i, line in enumerate(lines):
    if 'BankStatementLineMatch.objects.create(' in line:
        in_match_create = True
        match_create_lines = [line]
        # Get the indentation level
        indent_level = len(line) - len(line.lstrip())
    elif in_match_create:
        match_create_lines.append(line)
        # Check if this is the closing parenthesis
        if ')' in line and not line.strip().endswith(','):
            # Check if match_type is already present
            block_text = '\n'.join(match_create_lines)
            if 'match_type' not in block_text:
                # Find the line before the closing paren and add match_type
                insert_index = len(match_create_lines) - 1
                indent = ' ' * (indent_level + 4)  # Match indentation of other fields
                match_create_lines.insert(insert_index, f"{indent}match_type='MANUAL',")
            
            result_lines.extend(match_create_lines)
            in_match_create = False
            match_create_lines = []
    else:
        result_lines.append(line)

content = '\n'.join(result_lines)

# Write the changes back
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Added match_type='MANUAL' to BankStatementLineMatch creations in {file_path}")
