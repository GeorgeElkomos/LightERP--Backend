# Invoice Approval Workflow API Endpoints

This document describes the new approval workflow endpoints added to the Invoice module for AP, AR, and One-Time Supplier invoices.

## Overview

The approval workflow system is based on:
- **ApprovalManager** - Central manager for handling approval workflows
- **ApprovalWorkflowInstance** - Workflow instance attached to each invoice
- **ApprovalAssignment** - User assignments for each stage based on roles
- **ApprovalAction** - Audit log of approve/reject/delegate/comment actions

## Common Workflow

1. **Create Invoice** → Invoice is in DRAFT status
2. **Submit for Approval** → Starts workflow, creates assignments based on user roles
3. **Users Approve/Reject** → Process moves through stages (Accountant → Manager → Director)
4. **Workflow Completes** → Invoice status becomes APPROVED or REJECTED
5. **Post to GL** → Only if APPROVED

## AP Invoice Endpoints

### Submit for Approval
```
POST /invoices/ap/{id}/submit-for-approval/
```
**Description:** Starts the approval workflow for an AP invoice.

**Request:** No body required

**Response:**
```json
{
    "message": "Invoice submitted for approval",
    "invoice_id": 123,
    "workflow_id": 45,
    "status": "in_progress",
    "approval_status": "PENDING_APPROVAL"
}
```

### List Pending Approvals
```
GET /invoices/ap/pending-approvals/
```
**Description:** Lists all AP invoices pending approval for the current user based on their role assignments.

**Query Parameters:** None (uses authenticated user)

**Response:**
```json
[
    {
        "invoice_id": 123,
        "supplier_name": "ABC Supplier",
        "date": "2025-12-10",
        "total": "1500.00",
        "currency": "USD",
        "approval_status": "PENDING_APPROVAL",
        "workflow_id": 45,
        "current_stage": "Finance Manager Review",
        "can_approve": true,
        "can_reject": true,
        "can_delegate": true
    }
]
```

### Approval Action
```
POST /invoices/ap/{id}/approval-action/
```
**Description:** Perform an approval action (approve, reject, delegate, or comment).

**Request Body:**
```json
{
    "action": "approve",  // "approve" | "reject" | "delegate" | "comment"
    "comment": "Looks good, approved",  // Optional
    "target_user_id": 5  // Required only for delegation
}
```

**Response:**
```json
{
    "message": "Action approve completed successfully",
    "invoice_id": 123,
    "workflow_id": 45,
    "workflow_status": "in_progress",
    "approval_status": "PENDING_APPROVAL"
}
```

## AR Invoice Endpoints

### Submit for Approval
```
POST /invoices/ar/{id}/submit-for-approval/
```
**Description:** Starts the approval workflow for an AR invoice.

**Request:** No body required

**Response:**
```json
{
    "message": "Invoice submitted for approval",
    "invoice_id": 456,
    "workflow_id": 67,
    "status": "in_progress",
    "approval_status": "PENDING_APPROVAL"
}
```

### List Pending Approvals
```
GET /invoices/ar/pending-approvals/
```
**Description:** Lists all AR invoices pending approval for the current user.

**Response:**
```json
[
    {
        "invoice_id": 456,
        "customer_name": "XYZ Corp",
        "date": "2025-12-10",
        "total": "2500.00",
        "currency": "USD",
        "approval_status": "PENDING_APPROVAL",
        "workflow_id": 67,
        "current_stage": "Accountant Review",
        "can_approve": true,
        "can_reject": true,
        "can_delegate": false
    }
]
```

### Approval Action
```
POST /invoices/ar/{id}/approval-action/
```
**Description:** Perform an approval action on an AR invoice.

**Request Body:**
```json
{
    "action": "reject",
    "comment": "Missing supporting documentation"
}
```

**Response:**
```json
{
    "message": "Action reject completed successfully",
    "invoice_id": 456,
    "workflow_id": 67,
    "workflow_status": "rejected",
    "approval_status": "REJECTED"
}
```

## One-Time Supplier Invoice Endpoints

### Submit for Approval
```
POST /invoices/one-time-supplier/{id}/submit-for-approval/
```
**Description:** Starts the approval workflow for a one-time supplier invoice.

**Request:** No body required

**Response:**
```json
{
    "message": "Invoice submitted for approval",
    "invoice_id": 789,
    "workflow_id": 89,
    "status": "in_progress",
    "approval_status": "PENDING_APPROVAL"
}
```

### List Pending Approvals
```
GET /invoices/one-time-supplier/pending-approvals/
```
**Description:** Lists all one-time supplier invoices pending approval for the current user.

**Response:**
```json
[
    {
        "invoice_id": 789,
        "supplier_name": "Temp Contractor LLC",
        "date": "2025-12-10",
        "total": "850.00",
        "currency": "USD",
        "approval_status": "PENDING_APPROVAL",
        "workflow_id": 89,
        "current_stage": "CFO Review",
        "can_approve": true,
        "can_reject": true,
        "can_delegate": true
    }
]
```

### Approval Action
```
POST /invoices/one-time-supplier/{id}/approval-action/
```
**Description:** Perform an approval action on a one-time supplier invoice.

**Request Body:**
```json
{
    "action": "delegate",
    "comment": "Delegating to senior accountant",
    "target_user_id": 12
}
```

**Response:**
```json
{
    "message": "Action delegate completed successfully",
    "invoice_id": 789,
    "workflow_id": 89,
    "workflow_status": "in_progress",
    "approval_status": "PENDING_APPROVAL"
}
```

## Workflow Stage Configuration

The approval workflow uses a 3-stage process (configured in database):

1. **Stage 1: Accountant Review**
   - Required Role: `accountant`
   - Users with accountant role can approve/reject

2. **Stage 2: Finance Manager Review**
   - Required Role: `manager`
   - Users with manager role can approve/reject

3. **Stage 3: CFO Review**
   - Required Role: `director`
   - Users with director role can approve/reject

## Key Features

### Role-Based Assignments
- Assignments are created automatically based on user roles
- Only users with the required role for a stage receive assignments
- Users can only act on stages where they have assignments

### Actions
- **Approve**: Move to next stage or complete workflow
- **Reject**: Reject the entire workflow
- **Delegate**: Delegate approval to another user
- **Comment**: Add a comment without taking action

### Audit Trail
- All actions are logged in `ApprovalAction` table
- Full history of who approved/rejected and when
- Comments are preserved for compliance

### Status Tracking
- Invoice `approval_status` syncs with workflow status
- Workflow `status`: pending, in_progress, approved, rejected, cancelled
- Stage `status`: pending, active, completed, skipped, cancelled

## Error Handling

All endpoints return appropriate HTTP status codes:
- `200 OK` - Successful action
- `400 Bad Request` - Invalid action or business rule violation
- `401 Unauthorized` - No authenticated user
- `404 Not Found` - Invoice or user not found
- `500 Internal Server Error` - Unexpected error

Common error scenarios:
- Trying to approve without assignment
- Acting on a stage that's not active
- Delegating without providing target_user_id
- Submitting an invoice that's already in workflow
- Invalid action parameter

## Integration Notes

### Authentication
All endpoints use Django's authentication system. For testing purposes, if no authenticated user is found, the first user in the database is used.

### Content Type
The approval system works with the parent `Invoice` model, not the child models directly. The views handle the conversion automatically:
```python
# Views internally use invoice.invoice to access the parent
workflow_instance = ApprovalManager.process_action(
    ap_invoice.invoice,  # Parent Invoice object
    user=user,
    action=action
)
```

### Permissions
Currently, permission checking is done by the approval system based on role assignments. Additional Django permissions can be added to the views as needed.
