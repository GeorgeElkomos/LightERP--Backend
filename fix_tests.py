import re

# Fix test_models.py
with open('Finance/cash_management/tests/test_models.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace segment_code with code
content = content.replace("segment_code='1000'", "code='1000'")
# Replace segment_name with alias  
content = content.replace("segment_name='Cash'", "alias='Cash'")
# Add node_type field
content = re.sub(
    r"(code='1000',\s*\n\s*alias='Cash',\s*\n\s*is_active=True)",
    r"code='1000',\n            alias='Cash',\n            node_type='child',\n            is_active=True",
    content
)
# Remove created_by from XX_Segment_combination
content = content.replace("XX_Segment_combination.objects.create(created_by=self.user)", 
                         "XX_Segment_combination.objects.create()")

# Fix BankAccount field names
content = content.replace("available_balance=", "# available_balance=")
content = content.replace("gl_cash_account=self.gl_account", "cash_GL_combination=self.gl_account")
content = content.replace("gl_bank_charges_account=self.gl_account", "cash_clearing_GL_combination=self.gl_account")

with open('Finance/cash_management/tests/test_models.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed test_models.py")

# Fix test_reconciliation.py
with open('Finance/cash_management/tests/test_reconciliation.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace segment_code with code
content = content.replace("segment_code='1000'", "code='1000'")
# Replace segment_name with alias  
content = content.replace("segment_name='Cash'", "alias='Cash'")
# Add node_type field
content = re.sub(
    r"(code='1000',\s*\n\s*alias='Cash',\s*\n\s*is_active=True)",
    r"code='1000',\n            alias='Cash',\n            node_type='child',\n            is_active=True",
    content
)
# Remove created_by from XX_Segment_combination
content = content.replace("XX_Segment_combination.objects.create(created_by=self.user)", 
                         "XX_Segment_combination.objects.create()")

# Fix BankAccount field names
content = content.replace("available_balance=", "# available_balance=")
content = content.replace("gl_cash_account=self.gl_account", "cash_GL_combination=self.gl_account")
content = content.replace("gl_bank_charges_account=self.gl_account", "cash_clearing_GL_combination=self.gl_account")

# Fix BusinessPartner to use Supplier
content = content.replace("from Finance.BusinessPartner.models import BusinessPartner", "from Finance.BusinessPartner.models import Supplier")
content = content.replace("self.bp = BusinessPartner.objects.create(", "self.bp = Supplier.objects.create(")
content = content.replace("bp_type=BusinessPartner.SUPPLIER,", "")

with open('Finance/cash_management/tests/test_reconciliation.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed test_reconciliation.py")
