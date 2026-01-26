import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_project.settings')
django.setup()

from Finance.budget_control.models import BudgetHeader
from Finance.budget_control.excel_utils import create_budget_template

# Check if budget ID 2 exists
try:
    budget = BudgetHeader.objects.get(id=2)
    print(f"✓ Budget found: {budget.budget_code} - {budget.budget_name}")
    print(f"  Status: {budget.status}")
    print(f"  Start: {budget.start_date}, End: {budget.end_date}")
    
    # Test template generation
    response = create_budget_template(budget)
    print(f"\n✓ Template generated successfully")
    print(f"  Content-Type: {response['Content-Type']}")
    print(f"  Content-Disposition: {response['Content-Disposition']}")
    print(f"  Response size: {len(response.content)} bytes")
    print(f"  First 10 bytes: {response.content[:10]}")
    
except BudgetHeader.DoesNotExist:
    print("✗ Budget with ID 2 not found")
    print("\nAvailable budgets:")
    for b in BudgetHeader.objects.all()[:5]:
        print(f"  ID {b.id}: {b.budget_code} - {b.budget_name}")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
