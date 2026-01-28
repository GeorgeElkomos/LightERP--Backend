# * Deprecated: UserDataScope views are no longer used
# from rest_framework.decorators import api_view
# from rest_framework.response import Response
# from rest_framework import status
# from django.shortcuts import get_object_or_404
# from django.db import transaction
# from django.core.exceptions import ValidationError

# from HR.work_structures.models import BusinessGroup, Department
# from HR.work_structures.models.security import UserDataScope
# from HR.work_structures.serializers.security_serializers import (
#     UserDataScopeSerializer, 
#     UserDataScopeCreateSerializer,
#     BulkScopeAssignmentSerializer
# )
# from core.job_roles.decorators import require_page_action


# @api_view(['GET', 'POST'])
# @require_page_action('hr_data_scope')
# def user_scope_list(request):
#     """
#     List all user data scopes or create scope(s) (single or bulk).
    
#     GET /hr/user-scopes/
#     - Optional query param: user (filter by user ID)
#     - Returns list of all user data scopes
    
#     POST /hr/user-scopes/ (Single Scope)
#     - Create a single user data scope
#     - Required: (user OR email), either business_group OR is_global=True
#     - Request body examples:
#         By user_id: {"user": 1, "business_group": 1, "is_global": false}
#         By email: {"email": "user@example.com", "business_group_id": 1, "is_global": false}
    
#     POST /hr/user-scopes/ (Bulk Assignment)
#     - Bulk assign multiple data scopes to a user
#     - Detected by presence of "business_groups" or "departments" arrays
#     - Request body:
#         {
#             "user_email": "user@company.com",  // or "user": 123
#             "business_groups": ["EGY", "UAE"],  // list of codes or IDs
#             "departments": ["IT", "SALES"],     // list of codes or IDs (optional)
#             "is_global": false                  // set to true for global access (optional)
#         }
#     - All operations wrapped in transaction (all-or-nothing)
#     - Duplicate scopes are skipped automatically
#     """
#     if request.method == 'GET':
#         # Optional filtering by user
#         user_id = request.query_params.get('user')
        
#         if user_id:
#             scopes = UserDataScope.objects.filter(user_id=user_id).select_related(
#                 'user', 'business_group', 'department'
#             )
#         else:
#             scopes = UserDataScope.objects.all().select_related(
#                 'user', 'business_group', 'department'
#             )
        
#         serializer = UserDataScopeSerializer(scopes, many=True)
#         return Response(serializer.data, status=status.HTTP_200_OK)
    
#     elif request.method == 'POST':
#         # Detect if this is a bulk assignment (has business_groups or departments array)
#         is_bulk = 'business_groups' in request.data or 'departments' in request.data
        
#         if is_bulk:
#             return _handle_bulk_scope_assignment(request)
#         else:
#             return _handle_single_scope_creation(request)


# def _handle_single_scope_creation(request):
#     """Handle creation of a single user data scope."""
#     from core.user_accounts.models import UserAccount
    
#     # Handle both email and user_id
#     email = request.data.get('email')
#     user_id = request.data.get('user')
    
#     # If email provided, convert to user_id
#     if email and not user_id:
#         try:
#             user = UserAccount.objects.get(email=email)
#             user_id = user.id
#         except UserAccount.DoesNotExist:
#             return Response(
#                 {'error': f'User with email {email} not found'},
#                 status=status.HTTP_404_NOT_FOUND
#             )
    
#     # Build scope data, normalizing field names
#     scope_data = {
#         'user': user_id,
#         'is_global': request.data.get('is_global', False),
#         'business_group': request.data.get('business_group') or request.data.get('business_group_id'),
#         'department': request.data.get('department') or request.data.get('department_id')
#     }
    
#     serializer = UserDataScopeCreateSerializer(data=scope_data)
#     if serializer.is_valid():
#         scope = serializer.save()
#         # Return using read serializer for full details
#         response_serializer = UserDataScopeSerializer(scope)
#         return Response(response_serializer.data, status=status.HTTP_201_CREATED)
#     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# def _handle_bulk_scope_assignment(request):
#     """Handle bulk assignment of multiple data scopes to a user."""
#     serializer = BulkScopeAssignmentSerializer(data=request.data)
    
#     if not serializer.is_valid():
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
#     validated_data = serializer.validated_data
#     user_id = validated_data['user']
#     is_global = validated_data.get('is_global', False)
    
#     created_scopes = []
#     skipped_scopes = []
    
#     try:
#         with transaction.atomic():
#             # Handle global scope
#             if is_global:
#                 # Check if already exists
#                 if not UserDataScope.objects.filter(user_id=user_id, is_global=True).exists():
#                     scope = UserDataScope.objects.create(
#                         user_id=user_id,
#                         is_global=True
#                     )
#                     created_scopes.append({
#                         'business_group': None,
#                         'department': None,
#                         'is_global': True,
#                         'status': 'created'
#                     })
#                 else:
#                     skipped_scopes.append({
#                         'business_group': None,
#                         'department': None,
#                         'is_global': True,
#                         'status': 'already_exists'
#                     })
            
#             # Handle business group scopes
#             business_groups_ids = validated_data.get('business_groups_ids', [])
#             for bg_id in business_groups_ids:
#                 # Check if already exists
#                 if not UserDataScope.objects.filter(
#                     user_id=user_id,
#                     business_group_id=bg_id,
#                     department_id__isnull=True
#                 ).exists():
#                     scope = UserDataScope.objects.create(
#                         user_id=user_id,
#                         business_group_id=bg_id
#                     )
#                     created_scopes.append({
#                         'business_group': scope.business_group.code,
#                         'department': None,
#                         'status': 'created'
#                     })
#                 else:
#                     bg = BusinessGroup.objects.get(id=bg_id)
#                     skipped_scopes.append({
#                         'business_group': bg.code,
#                         'department': None,
#                         'status': 'already_exists'
#                     })
            
#             # Handle department scopes
#             departments_ids = validated_data.get('departments_ids', [])
#             for dept_info in departments_ids:
#                 dept_id = dept_info['id']
#                 bg_id = dept_info['bg_id']
                
#                 # Check if already exists
#                 if not UserDataScope.objects.filter(
#                     user_id=user_id,
#                     business_group_id=bg_id,
#                     department_id=dept_id
#                 ).exists():
#                     scope = UserDataScope.objects.create(
#                         user_id=user_id,
#                         business_group_id=bg_id,
#                         department_id=dept_id
#                     )
#                     created_scopes.append({
#                         'business_group': scope.business_group.code,
#                         'department': scope.department.code,
#                         'status': 'created'
#                     })
#                 else:
#                     bg = BusinessGroup.objects.get(id=bg_id)
#                     dept = Department.objects.get(id=dept_id)
#                     skipped_scopes.append({
#                         'business_group': bg.code,
#                         'department': dept.code,
#                         'status': 'already_exists'
#                     })
        
#         # Success response
#         return Response({
#             'success': True,
#             'message': f"Successfully assigned {len(created_scopes)} scope(s) to user",
#             'scopes_created': len(created_scopes),
#             'scopes_skipped': len(skipped_scopes),
#             'details': created_scopes + skipped_scopes
#         }, status=status.HTTP_201_CREATED)
        
#     except ValidationError as e:
#         return Response({
#             'success': False,
#             'error': str(e)
#         }, status=status.HTTP_400_BAD_REQUEST)
#     except Exception as e:
#         return Response({
#             'success': False,
#             'error': f"Failed to assign scopes: {str(e)}"
#         }, status=status.HTTP_400_BAD_REQUEST)


# @api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
# @require_page_action('hr_data_scope')
# def user_scope_detail(request, pk):
#     """
#     Retrieve, update (single or bulk), or delete a user data scope.
    
#     GET /hr/user-scopes/{id}/
#     - Returns details of a specific user data scope
    
#     PUT/PATCH /hr/user-scopes/{id}/ (Single Update)
#     - Update a single user data scope
#     - Request body: {"business_group": 2, "is_global": false}
    
#     PUT/PATCH /hr/user-scopes/{id}/ (Bulk Update)
#     - Update multiple user data scopes at once
#     - Request body must be a list:
#         [
#             {"id": 1, "business_group": 2},
#             {"id": 3, "department": 5},
#             {"id": 7, "is_global": true}
#         ]
#     - All operations wrapped in transaction (all-or-nothing)
#     - Returns summary of updated scopes
    
#     DELETE /hr/user-scopes/{id}/
#     - Delete a user data scope
#     """
#     if request.method == 'GET':
#         scope = get_object_or_404(UserDataScope, pk=pk)
#         serializer = UserDataScopeSerializer(scope)
#         return Response(serializer.data, status=status.HTTP_200_OK)
    
#     elif request.method in ['PUT', 'PATCH']:
#         # Check if request data is a list (bulk update) or single object
#         is_bulk = isinstance(request.data, list)
        
#         if is_bulk:
#             return _handle_bulk_scope_update(request)
#         else:
#             return _handle_single_scope_update(request, pk)
    
#     elif request.method == 'DELETE':
#         scope = get_object_or_404(UserDataScope, pk=pk)
#         scope.delete()
#         return Response(status=status.HTTP_204_NO_CONTENT)


# def _handle_single_scope_update(request, pk):
#     """Handle update of a single user data scope."""
#     scope = get_object_or_404(UserDataScope, pk=pk)
#     partial = request.method == 'PATCH'
#     serializer = UserDataScopeSerializer(scope, data=request.data, partial=partial)
#     if serializer.is_valid():
#         serializer.save()
#         return Response(serializer.data, status=status.HTTP_200_OK)
#     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# def _handle_bulk_scope_update(request):
#     """Handle bulk update of multiple user data scopes."""
#     if not isinstance(request.data, list):
#         return Response(
#             {'error': 'Bulk update requires a list of scope objects'},
#             status=status.HTTP_400_BAD_REQUEST
#         )
    
#     updated_scopes = []
#     failed_updates = []
#     partial = request.method == 'PATCH'
    
#     try:
#         with transaction.atomic():
#             for scope_data in request.data:
#                 scope_id = scope_data.get('id')
#                 if not scope_id:
#                     failed_updates.append({
#                         'data': scope_data,
#                         'error': 'Missing id field'
#                     })
#                     continue
                
#                 try:
#                     scope = UserDataScope.objects.get(pk=scope_id)
#                     serializer = UserDataScopeSerializer(
#                         scope, 
#                         data=scope_data, 
#                         partial=partial
#                     )
                    
#                     if serializer.is_valid():
#                         serializer.save()
#                         updated_scopes.append({
#                             'id': scope_id,
#                             'status': 'updated',
#                             'data': serializer.data
#                         })
#                     else:
#                         failed_updates.append({
#                             'id': scope_id,
#                             'errors': serializer.errors
#                         })
#                         # Rollback transaction if any update fails
#                         raise ValidationError(f"Validation failed for scope {scope_id}")
                
#                 except UserDataScope.DoesNotExist:
#                     failed_updates.append({
#                         'id': scope_id,
#                         'error': f'Scope with id {scope_id} not found'
#                     })
#                     raise ValidationError(f"Scope {scope_id} not found")
        
#         return Response({
#             'success': True,
#             'message': f"Successfully updated {len(updated_scopes)} scope(s)",
#             'updated_count': len(updated_scopes),
#             'updated_scopes': updated_scopes
#         }, status=status.HTTP_200_OK)
        
#     except ValidationError as e:
#         return Response({
#             'success': False,
#             'error': str(e),
#             'failed_updates': failed_updates
#         }, status=status.HTTP_400_BAD_REQUEST)
#     except Exception as e:
#         return Response({
#             'success': False,
#             'error': f"Failed to update scopes: {str(e)}",
#             'failed_updates': failed_updates
#         }, status=status.HTTP_400_BAD_REQUEST)


