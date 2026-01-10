"""
Add created_by to remaining BankAccount creations
"""

file_path = 'Finance/cash_management/tests/test_comprehensive_api.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace all instances where BankAccount is created without created_by
content = content.replace(
    """            cash_clearing_GL_combination_id=self.clearing_combo,
            updated_by=self.user
        )""",
    """            cash_clearing_GL_combination_id=self.clearing_combo,
            created_by=self.user,
            updated_by=self.user
        )"""
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Added created_by to all BankAccount creations in {file_path}")
