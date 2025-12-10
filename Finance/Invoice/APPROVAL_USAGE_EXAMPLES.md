# Approval Workflow API Usage Examples

This file demonstrates how to use the approval workflow API endpoints for invoices.

## Example 1: Complete AP Invoice Approval Workflow

```python
import requests

BASE_URL = "http://localhost:8000/invoices"

# Step 1: Create an AP Invoice
response = requests.post(f"{BASE_URL}/ap/", json={
    "date": "2025-12-10",
    "supplier_id": 1,
    "currency_id": 1,
    "country_id": 1,
    "description": "Office Supplies",
    "subtotal": 1000.00,
    "tax_amount": 150.00,
    "total": 1150.00,
    "items": [
        {
            "description": "Printer Paper",
            "quantity": 10,
            "unit_price": 50.00,
            "amount": 500.00
        },
        {
            "description": "Toner Cartridges",
            "quantity": 5,
            "unit_price": 100.00,
            "amount": 500.00
        }
    ],
    "gl_distributions": {
        "journal_entry_id": 1
    }
})
invoice_id = response.json()['id']
print(f"Created invoice: {invoice_id}")

# Step 2: Submit for approval
response = requests.post(f"{BASE_URL}/ap/{invoice_id}/submit-for-approval/")
workflow_data = response.json()
print(f"Submitted for approval: workflow_id={workflow_data['workflow_id']}")
print(f"Status: {workflow_data['approval_status']}")

# Step 3: Accountant checks pending approvals
response = requests.get(f"{BASE_URL}/ap/pending-approvals/")
pending = response.json()
print(f"Accountant has {len(pending)} invoices to approve")

# Step 4: Accountant approves (Stage 1)
response = requests.post(f"{BASE_URL}/ap/{invoice_id}/approval-action/", json={
    "action": "approve",
    "comment": "Verified receipts and budget allocation"
})
print(f"Accountant approved: {response.json()['message']}")

# Step 5: Manager approves (Stage 2)
response = requests.post(f"{BASE_URL}/ap/{invoice_id}/approval-action/", json={
    "action": "approve",
    "comment": "Within budget, approved"
})
print(f"Manager approved: {response.json()['message']}")

# Step 6: Director/CFO approves (Stage 3)
response = requests.post(f"{BASE_URL}/ap/{invoice_id}/approval-action/", json={
    "action": "approve",
    "comment": "Final approval granted"
})
print(f"Director approved: {response.json()['message']}")
print(f"Final status: {response.json()['approval_status']}")  # Should be "APPROVED"

# Step 7: Post to GL (now that it's approved)
response = requests.post(f"{BASE_URL}/ap/{invoice_id}/post-to-gl/")
print(f"Posted to GL: {response.json()['message']}")
```

## Example 2: AR Invoice with Rejection

```python
import requests

BASE_URL = "http://localhost:8000/invoices"

# Create AR Invoice
response = requests.post(f"{BASE_URL}/ar/", json={
    "date": "2025-12-10",
    "customer_id": 1,
    "currency_id": 1,
    "country_id": 1,
    "description": "Consulting Services",
    "subtotal": 5000.00,
    "tax_amount": 750.00,
    "total": 5750.00,
    "items": [
        {
            "description": "Q4 Consulting",
            "quantity": 1,
            "unit_price": 5000.00,
            "amount": 5000.00
        }
    ],
    "gl_distributions": {
        "journal_entry_id": 2
    }
})
invoice_id = response.json()['id']

# Submit for approval
requests.post(f"{BASE_URL}/ar/{invoice_id}/submit-for-approval/")

# Accountant approves Stage 1
requests.post(f"{BASE_URL}/ar/{invoice_id}/approval-action/", json={
    "action": "approve",
    "comment": "Verified contract terms"
})

# Manager rejects Stage 2 (e.g., customer credit issue)
response = requests.post(f"{BASE_URL}/ar/{invoice_id}/approval-action/", json={
    "action": "reject",
    "comment": "Customer has outstanding invoices, hold until resolved"
})
print(f"Invoice rejected: {response.json()['approval_status']}")  # "REJECTED"
```

## Example 3: Delegation

```python
import requests

BASE_URL = "http://localhost:8000/invoices"

# Create invoice
response = requests.post(f"{BASE_URL}/ap/", json={...})
invoice_id = response.json()['id']

# Submit for approval
requests.post(f"{BASE_URL}/ap/{invoice_id}/submit-for-approval/")

# Accountant delegates to senior accountant
response = requests.post(f"{BASE_URL}/ap/{invoice_id}/approval-action/", json={
    "action": "delegate",
    "comment": "On vacation, delegating to John",
    "target_user_id": 5  # John's user ID
})
print(f"Delegated successfully: {response.json()['message']}")

# Now user 5 can approve
response = requests.post(f"{BASE_URL}/ap/{invoice_id}/approval-action/", json={
    "action": "approve",
    "comment": "Reviewed on behalf of Jane, approved"
})
```

## Example 4: Add Comment Without Action

```python
import requests

BASE_URL = "http://localhost:8000/invoices"

# Add a comment to track discussion
response = requests.post(f"{BASE_URL}/ap/{invoice_id}/approval-action/", json={
    "action": "comment",
    "comment": "Need to verify vendor tax ID before final approval"
})
print(f"Comment added: {response.json()['message']}")
```

## Example 5: Check Pending Approvals for Current User

```python
import requests

BASE_URL = "http://localhost:8000/invoices"

# Get all AP invoices pending for current user
response = requests.get(f"{BASE_URL}/ap/pending-approvals/")
pending_invoices = response.json()

for invoice in pending_invoices:
    print(f"Invoice {invoice['invoice_id']}:")
    print(f"  Supplier: {invoice['supplier_name']}")
    print(f"  Amount: {invoice['currency']} {invoice['total']}")
    print(f"  Current Stage: {invoice['current_stage']}")
    print(f"  Can Approve: {invoice['can_approve']}")
    print(f"  Can Reject: {invoice['can_reject']}")
    print(f"  Can Delegate: {invoice['can_delegate']}")
    print()

# Get AR invoices pending
response = requests.get(f"{BASE_URL}/ar/pending-approvals/")
ar_pending = response.json()

# Get one-time supplier invoices pending
response = requests.get(f"{BASE_URL}/one-time-supplier/pending-approvals/")
ots_pending = response.json()

total_pending = len(pending_invoices) + len(ar_pending) + len(ots_pending)
print(f"Total invoices pending your approval: {total_pending}")
```

## Example 6: Error Handling

```python
import requests

BASE_URL = "http://localhost:8000/invoices"

# Try to approve without assignment
response = requests.post(f"{BASE_URL}/ap/{invoice_id}/approval-action/", json={
    "action": "approve"
})
if response.status_code == 400:
    print(f"Error: {response.json()['error']}")
    # Output: "User has no assignment in this active stage"

# Try to submit already submitted invoice
response = requests.post(f"{BASE_URL}/ap/{invoice_id}/submit-for-approval/")
if response.status_code == 400:
    print(f"Error: {response.json()['error']}")
    # Output: "Workflow already in progress"

# Try to delegate without target_user_id
response = requests.post(f"{BASE_URL}/ap/{invoice_id}/approval-action/", json={
    "action": "delegate",
    "comment": "Delegating..."
})
if response.status_code == 400:
    print(f"Error: {response.json()['error']}")
    # Output: "target_user_id required for delegation"
```

## Example 7: One-Time Supplier Invoice Approval

```python
import requests

BASE_URL = "http://localhost:8000/invoices"

# Create one-time supplier invoice
response = requests.post(f"{BASE_URL}/one-time-supplier/", json={
    "date": "2025-12-10",
    "currency_id": 1,
    "country_id": 1,
    "description": "Emergency plumbing repair",
    "subtotal": 850.00,
    "tax_amount": 0.00,
    "total": 850.00,
    "one_time_supplier": {
        "name": "Quick Fix Plumbing",
        "tax_id": "12-3456789",
        "address": "123 Main St, City"
    },
    "items": [
        {
            "description": "Pipe repair",
            "quantity": 1,
            "unit_price": 850.00,
            "amount": 850.00
        }
    ],
    "gl_distributions": {
        "journal_entry_id": 3
    }
})
invoice_id = response.json()['id']

# Submit and approve
requests.post(f"{BASE_URL}/one-time-supplier/{invoice_id}/submit-for-approval/")

# Accountant approves
requests.post(f"{BASE_URL}/one-time-supplier/{invoice_id}/approval-action/", json={
    "action": "approve",
    "comment": "Emergency repair verified"
})

# Manager approves
requests.post(f"{BASE_URL}/one-time-supplier/{invoice_id}/approval-action/", json={
    "action": "approve",
    "comment": "Approved"
})

# Director approves
response = requests.post(f"{BASE_URL}/one-time-supplier/{invoice_id}/approval-action/", json={
    "action": "approve",
    "comment": "Final approval"
})
print(f"One-time supplier invoice approved: {response.json()['approval_status']}")

# Post to GL
requests.post(f"{BASE_URL}/one-time-supplier/{invoice_id}/post-to-gl/")
```

## Django ORM Examples

If you're working directly with Django models:

```python
from Finance.Invoice.models import AP_Invoice
from core.approval.managers import ApprovalManager
from core.user_accounts.models import User

# Get an invoice
ap_invoice = AP_Invoice.objects.get(pk=1)

# Submit for approval
workflow = ap_invoice.submit_for_approval()
print(f"Workflow started: {workflow.status}")

# Get user
user = User.objects.get(username='john.accountant')

# Approve
ap_invoice.approve(user, comment='Looks good')

# Reject
# ap_invoice.reject(user, comment='Missing documentation')

# Or use ApprovalManager directly
ApprovalManager.process_action(
    ap_invoice.invoice,  # Note: use invoice.invoice (parent)
    user=user,
    action='approve',
    comment='Approved via direct API'
)

# Get pending approvals for user
pending_workflows = ApprovalManager.get_user_pending_approvals(user)
for workflow in pending_workflows:
    invoice = workflow.content_object
    print(f"Pending: {invoice} - Total: {invoice.total}")

# Check workflow status
is_finished, status = ApprovalManager.is_workflow_finished(ap_invoice.invoice)
print(f"Workflow finished: {is_finished}, Status: {status}")
```

## Testing with curl

```bash
# Submit AP invoice for approval
curl -X POST http://localhost:8000/invoices/ap/1/submit-for-approval/

# Get pending approvals
curl http://localhost:8000/invoices/ap/pending-approvals/

# Approve invoice
curl -X POST http://localhost:8000/invoices/ap/1/approval-action/ \
  -H "Content-Type: application/json" \
  -d '{"action": "approve", "comment": "Approved"}'

# Reject invoice
curl -X POST http://localhost:8000/invoices/ap/1/approval-action/ \
  -H "Content-Type: application/json" \
  -d '{"action": "reject", "comment": "Budget exceeded"}'

# Delegate invoice
curl -X POST http://localhost:8000/invoices/ap/1/approval-action/ \
  -H "Content-Type: application/json" \
  -d '{"action": "delegate", "comment": "Out of office", "target_user_id": 5}'
```

## Notes

1. **Authentication**: All endpoints require authentication. The current implementation uses the authenticated user from the request.

2. **Role Requirements**: Users must have the appropriate role assigned to approve at each stage:
   - Stage 1: accountant role
   - Stage 2: manager role
   - Stage 3: director role

3. **Sequential Approval**: Stages must be approved in order. You cannot skip stages.

4. **Rejection**: When any stage is rejected, the entire workflow is rejected and stops.

5. **Assignment-Based**: Users can only approve invoices where they have an active assignment in the current stage.
