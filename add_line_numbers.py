"""
Add line_number to all BankStatementLine creations in integration tests
"""

file_path = 'Finance/cash_management/tests/test_integration_payment_reconciliation.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add line_number to the first line_data (test_complete_outgoing_payment_reconciliation_flow)
content = content.replace(
    """        line_data = {
            'bank_statement_id': statement_id,
            'transaction_date': '2026-01-15',
            'value_date': '2026-01-15',
            'amount': '-1500.00',  # Negative for outgoing
            'transaction_type': 'DEBIT',
            'description': 'Wire Transfer to Test Supplier Inc',
            'reference_number': 'WR20260115001'
        }""",
    """        line_data = {
            'bank_statement_id': statement_id,
            'line_number': 1,
            'transaction_date': '2026-01-15',
            'value_date': '2026-01-15',
            'amount': '-1500.00',  # Negative for outgoing
            'transaction_type': 'DEBIT',
            'description': 'Wire Transfer to Test Supplier Inc',
            'reference_number': 'WR20260115001'
        }"""
)

# Add line_number to the second line_data (test_complete_incoming_receipt_reconciliation_flow)  
content = content.replace(
    """        line_data = {
            'bank_statement_id': statement_id,
            'transaction_date': '2026-01-20',
            'value_date': '2026-01-20',
            'amount': '2500.00',  # Positive for incoming
            'transaction_type': 'CREDIT',
            'description': 'Check deposit from Test Customer Corp',
            'reference_number': 'CHK20260120001'
        }""",
    """        line_data = {
            'bank_statement_id': statement_id,
            'line_number': 1,
            'transaction_date': '2026-01-20',
            'value_date': '2026-01-20',
            'amount': '2500.00',  # Positive for incoming
            'transaction_type': 'CREDIT',
            'description': 'Check deposit from Test Customer Corp',
            'reference_number': 'CHK20260120001'
        }"""
)

# Add line_number to the third line_data (test_multiple_payments_one_statement_line)
content = content.replace(
    """        line_data = {
            'bank_statement_id': statement_id,
            'transaction_date': '2026-01-25',
            'value_date': '2026-01-25',
            'amount': '-3000.00',
            'transaction_type': 'DEBIT',
            'description': 'Batch payment to suppliers',
            'reference_number': 'BATCH001'
        }""",
    """        line_data = {
            'bank_statement_id': statement_id,
            'line_number': 1,
            'transaction_date': '2026-01-25',
            'value_date': '2026-01-25',
            'amount': '-3000.00',
            'transaction_type': 'DEBIT',
            'description': 'Batch payment to suppliers',
            'reference_number': 'BATCH001'
        }"""
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Added line_number to all BankStatementLine creations in {file_path}")
