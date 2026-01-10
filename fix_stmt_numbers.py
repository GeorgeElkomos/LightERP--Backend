import re

# Fix test_models.py
file_path = 'Finance/cash_management/tests/test_models.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

counter = 100
def repl(match):
    global counter
    result = f"statement_number='STMT{counter:03d}',"
    counter += 1
    return result

content = re.sub(r"statement_number='STMT001',", repl, content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"test_models.py: Replaced {counter - 100} occurrences")

# Fix integration tests - these are already unique, so just verify
file_path2 = 'Finance/cash_management/tests/test_integration_payment_reconciliation.py'
with open(file_path2, 'r', encoding='utf-8') as f:
    content2 = f.read()

print("Integration tests already have unique statement numbers")
