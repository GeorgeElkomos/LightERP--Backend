#!/usr/bin/env python
"""Fix match creation field names in integration tests."""

import re

file_path = r'Finance\cash_management\tests\test_integration_payment_reconciliation.py'

# Read the file
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace statement_line_id with statement_line in match_data dictionaries
content = re.sub(
    r"'statement_line_id':",
    "'statement_line':",
    content
)

# Replace payment_id with payment in match_data dictionaries (only in match creation contexts)
content = re.sub(
    r"'payment_id':\s*(\w+_id)",
    r"'payment': \1",
    content
)

# Write the changes back
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Fixed match field names in {file_path}")
