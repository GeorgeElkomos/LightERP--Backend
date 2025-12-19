"""
Service PR Views - API Endpoints

These views handle Service PRs (service requests).
Follows the same pattern as Catalog and Non-Catalog PR views.
"""

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError

from erp_project.pagination import auto_paginate

from procurement.PR.models import Service_PR, PR
from procurement.PR.serializers import (
    ServicePRCreateSerializer,
    ServicePRListSerializer,
    ServicePRDetailSerializer
)


@api_view(['GET', 'POST'])
@auto_paginate
def service_pr_list(request):
    """
    List all Service PRs or create a new Service PR.
    
    GET /pr/service/
    - Returns list of all Service PRs
    - Query params:
        - status: Filter by status (DRAFT/PENDING_APPROVAL/APPROVED/REJECTED/CANCELLED)
        - priority: Filter by priority (LOW/MEDIUM/HIGH/URGENT)
        - requester_department: Filter by department
        - date_from: Filter by date range start
        - date_to: Filter by date range end
    
    POST /pr/service/
    - Create a new Service PR with service items
    - Request body: ServicePRCreateSerializer fields
    """
    if request.method == 'GET':
        service_prs = Service_PR.objects.select_related(
            'pr'
        ).all()
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            service_prs = service_prs.filter(pr__status=status_filter.upper())
        
        priority = request.query_params.get('priority')
        if priority:
            service_prs = service_prs.filter(pr__priority=priority.upper())
        
        requester_department = request.query_params.get('requester_department')
        if requester_department:
            service_prs = service_prs.filter(pr__requester_department__icontains=requester_department)
        
        date_from = request.query_params.get('date_from')
        if date_from:
            service_prs = service_prs.filter(pr__date__gte=date_from)
        
        date_to = request.query_params.get('date_to')
        if date_to:
            service_prs = service_prs.filter(pr__date__lte=date_to)
        
        serializer = ServicePRListSerializer(service_prs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = ServicePRCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                service_pr = serializer.save()
                response_serializer = ServicePRDetailSerializer(service_pr)
                return Response(
                    response_serializer.data,
                    status=status.HTTP_201_CREATED
                )
            except ValidationError as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                return Response(
                    {'error': f'An error occurred: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'DELETE'])
def service_pr_detail(request, pk):
    """
    Retrieve or delete a specific Service PR.
    
    GET /pr/service/{id}/
    - Returns detailed information about a Service PR
    
    DELETE /pr/service/{id}/
    - Delete a Service PR (if not approved or converted to PO)
    """
    service_pr = get_object_or_404(
        Service_PR.objects.select_related('pr'),
        pr_id=pk
    )
    
    if request.method == 'GET':
        serializer = ServicePRDetailSerializer(service_pr)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'DELETE':
        # Check if PR can be deleted
        if service_pr.pr.status in ['APPROVED', 'CONVERTED_TO_PO']:
            return Response(
                {'error': f'Cannot delete PR in {service_pr.pr.status} status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            pr_number = service_pr.pr.pr_number
            service_pr.delete()
            return Response(
                {'message': f'Service PR {pr_number} deleted successfully'},
                status=status.HTTP_204_NO_CONTENT
            )
        except Exception as e:
            return Response(
                {'error': f'Cannot delete PR: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )


@api_view(['POST'])
def service_pr_submit_for_approval(request, pk):
    """
    Submit a Service PR for approval workflow.
    
    POST /pr/service/{id}/submit-for-approval/
    
    Starts the approval workflow for the PR.
    """
    service_pr = get_object_or_404(Service_PR, pr_id=pk)
    
    try:
        workflow_instance = service_pr.submit_for_approval()
        
        return Response({
            'message': 'Service PR submitted for approval',
            'pr_id': service_pr.pr_id,
            'pr_number': service_pr.pr.pr_number,
            'workflow_id': workflow_instance.id,
            'status': workflow_instance.status,
            'approval_status': service_pr.pr.status
        }, status=status.HTTP_200_OK)
    except (ValueError, ValidationError) as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'An error occurred: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@auto_paginate
def service_pr_pending_approvals(request):
    """
    List Service PRs pending approval for the current user.
    
    GET /pr/service/pending-approvals/
    
    Returns only PRs where the current user has an active approval assignment.
    """
    from django.contrib.auth import get_user_model
    from core.approval.managers import ApprovalManager
    from core.approval.models import ApprovalAssignment
    from django.contrib.contenttypes.models import ContentType
    
    # Get user from request
    User = get_user_model()
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        user = User.objects.first()
    
    if not user:
        return Response(
            {'error': 'No authenticated user'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # Use ApprovalManager to get all pending workflows for this user
    pending_workflows = ApprovalManager.get_user_pending_approvals(user)
    
    # Filter to only PR content type
    pr_content_type = ContentType.objects.get_for_model(PR)
    pr_workflows = pending_workflows.filter(content_type=pr_content_type)
    
    pr_ids = [wf.object_id for wf in pr_workflows]
    service_prs = Service_PR.objects.filter(
        pr_id__in=pr_ids
    ).select_related('pr')
    
    # Build response with approval info
    result = []
    for service_pr in service_prs:
        workflow = ApprovalManager.get_workflow_instance(service_pr.pr)
        if workflow:
            active_stage = workflow.stage_instances.filter(status='active').first()
            assignment = None
            
            if active_stage:
                assignment = active_stage.assignments.filter(
                    user=user,
                    status=ApprovalAssignment.STATUS_PENDING
                ).first()
            
            result.append({
                'pr_id': service_pr.pr_id,
                'pr_number': service_pr.pr.pr_number,
                'requester_name': service_pr.pr.requester_name,
                'requester_department': service_pr.pr.requester_department,
                'date': service_pr.pr.date,
                'required_date': service_pr.pr.required_date,
                'total': str(service_pr.pr.total),
                'priority': service_pr.pr.priority,
                'approval_status': service_pr.pr.status,
                'workflow_id': workflow.id,
                'current_stage': active_stage.stage_template.name if active_stage else None,
                'can_approve': assignment is not None,
                'can_reject': active_stage.stage_template.allow_reject if active_stage else False,
                'can_delegate': active_stage.stage_template.allow_delegate if active_stage else False,
            })
    
    return Response(result)


@api_view(['POST'])
def service_pr_approval_action(request, pk):
    """
    Perform an approval action on a Service PR.
    
    POST /pr/service/{id}/approval-action/
    
    Request body:
        {
            "action": "approve" | "reject" | "delegate" | "comment",
            "comment": "Optional comment",
            "target_user_id": 123  // Required for delegation
        }
    """
    from django.contrib.auth import get_user_model
    from core.approval.managers import ApprovalManager
    
    service_pr = get_object_or_404(Service_PR, pr_id=pk)
    
    # Get user from request
    User = get_user_model()
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        user = User.objects.first()
    
    if not user:
        return Response(
            {'error': 'No authenticated user'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    action = request.data.get('action', 'approve').lower()
    comment = request.data.get('comment', '')
    target_user_id = request.data.get('target_user_id')
    
    # Map action strings
    action_mapping = {
        'approved': 'approve',
        'rejected': 'reject',
        'approve': 'approve',
        'reject': 'reject',
        'delegate': 'delegate',
        'comment': 'comment'
    }
    
    action = action_mapping.get(action)
    if not action:
        return Response(
            {'error': 'Invalid action. Must be approve, reject, delegate, or comment'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get target user for delegation
    target_user = None
    if action == 'delegate':
        if not target_user_id:
            return Response(
                {'error': 'target_user_id required for delegation'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            target_user = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            return Response(
                {'error': f'User with id {target_user_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    try:
        # Perform the action using process_action - pass the child object (service_pr)
        ApprovalManager.process_action(service_pr, user, action, comment, target_user)
        
        # Refresh from DB
        service_pr.refresh_from_db()
        
        return Response({
            'message': f'Action {action} completed successfully',
            'pr_id': service_pr.pr_id,
            'pr_number': service_pr.pr.pr_number,
            'approval_status': service_pr.pr.status
        }, status=status.HTTP_200_OK)
        
    except (ValueError, ValidationError) as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'An error occurred: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def service_pr_cancel(request, pk):
    """
    Cancel a Service PR.
    
    POST /pr/service/{id}/cancel/
    
    Request body (optional):
        {
            "reason": "Cancellation reason"
        }
    """
    service_pr = get_object_or_404(Service_PR, pr_id=pk)
    
    reason = request.data.get('reason', '')
    
    try:
        service_pr.pr.cancel(reason=reason)
        
        return Response({
            'message': 'Service PR cancelled successfully',
            'pr_id': service_pr.pr_id,
            'pr_number': service_pr.pr.pr_number,
            'status': service_pr.pr.status
        }, status=status.HTTP_200_OK)
        
    except ValidationError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'An error occurred: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
