# * hold off on this file until needed *
# from rest_framework import serializers
# from HR.work_structures.models.security import UserDataScope
# from HR.work_structures.models import BusinessGroup, Department
# from core.user_accounts.models import UserAccount
#
# class UserDataScopeSerializer(serializers.ModelSerializer):
#     """Serializer for UserDataScope - defines which business groups/departments a user can access"""
#     user_email = serializers.EmailField(source='user.email', read_only=True)
#     user_name = serializers.CharField(source='user.get_full_name', read_only=True)
#     business_group_name = serializers.CharField(source='business_group.name', read_only=True, allow_null=True)
#     department_name = serializers.CharField(source='department.name', read_only=True, allow_null=True)
#
#     class Meta:
#         model = UserDataScope
#         fields = [
#             'id',
#             'user',
#             'user_email',
#             'user_name',
#             'business_group',
#             'business_group_name',
#             'department',
#             'department_name',
#             'is_global'
#         ]
#         read_only_fields = ['id']
#
#     def validate(self, data):
#         """Validate hierarchical scope rules"""
#         is_global = data.get('is_global', False)
#         business_group = data.get('business_group')
#         department = data.get('department')
#         user = data.get('user')
#
#         # Rule 1: Global scope cannot have BG or department
#         if is_global and (business_group or department):
#             raise serializers.ValidationError(
#                 "Global scope cannot have business_group or department. Global scope applies to all."
#             )
#
#         # Rule 2: Must have either global or BG
#         if not is_global and not business_group:
#             raise serializers.ValidationError(
#                 "Must specify either business_group or set is_global to True."
#             )
#
#         # Rule 3: Department scope requires BG
#         if department and not business_group:
#             raise serializers.ValidationError(
#                 "Department scope requires business_group to be set."
#             )
#
#         # Rule 4: Check for duplicate (user, BG, dept) combination
#         # This handles SQLite's NULL != NULL behavior
#         if user:
#             existing_query = UserDataScope.objects.filter(
#                 user=user,
#                 business_group=business_group,
#                 department=department
#             )
#
#             # Exclude current instance if updating
#             if self.instance:
#                 existing_query = existing_query.exclude(pk=self.instance.pk)
#
#             if existing_query.exists():
#                 if department:
#                     raise serializers.ValidationError(
#                         f"This user already has access to department {department.code} in {business_group.code}."
#                     )
#                 elif business_group:
#                     raise serializers.ValidationError(
#                         f"This user already has full access to business group {business_group.code}."
#                     )
#                 else:
#                     raise serializers.ValidationError(
#                         "This user already has global access."
#                     )
#
#         return data
#
#
# class UserDataScopeCreateSerializer(serializers.Serializer):
#     """
#     Create serializer for UserDataScope with hierarchical support.
#     Supports flexible lookups:
#     - user (ID) or user_email (string)
#     - business_group (ID) or business_group_code (string)
#     - department (ID) or department_code (string)
#     """
#     # User - ID or email lookup
#     user = serializers.IntegerField(required=False, allow_null=True)
#     user_email = serializers.EmailField(required=False, allow_null=True, write_only=True)
#
#     # Business Group - ID or code lookup
#     business_group = serializers.IntegerField(required=False, allow_null=True)
#     business_group_code = serializers.CharField(max_length=50, required=False, allow_null=True, write_only=True)
#
#     # Department - ID or code lookup
#     department = serializers.IntegerField(required=False, allow_null=True)
#     department_code = serializers.CharField(max_length=50, required=False, allow_null=True, write_only=True)
#
#     is_global = serializers.BooleanField(default=False)
#
#     def validate(self, data):
#         """Validate hierarchical scope rules and convert lookups to IDs"""
#
#         # User: email → ID
#         user_email = data.pop('user_email', None)
#         if user_email and not data.get('user'):
#             try:
#                 user = UserAccount.objects.get(email=user_email)
#                 data['user'] = user.id
#             except UserAccount.DoesNotExist:
#                 raise serializers.ValidationError({
#                     'user_email': f"No user found with email '{user_email}'"
#                 })
#
#         if not data.get('user'):
#             raise serializers.ValidationError({'user': 'Either user or user_email is required.'})
#
#         # Business Group: code → ID
#         business_group_code = data.pop('business_group_code', None)
#         if business_group_code and not data.get('business_group'):
#             try:
#                 from django.utils import timezone
#                 bg = BusinessGroup.objects.filter(code=business_group_code).active_on(timezone.now().date()).first()
#                 if not bg:
#                     raise BusinessGroup.DoesNotExist
#                 data['business_group'] = bg.id
#             except BusinessGroup.DoesNotExist:
#                 raise serializers.ValidationError({
#                     'business_group_code': f"No active business group found with code '{business_group_code}'"
#                 })
#
#         # Department: code → ID
#         department_code = data.pop('department_code', None)
#         if department_code and not data.get('department'):
#             # If business_group provided, filter by it for better error messages
#             bg_id = data.get('business_group')
#             dept_filter = {'code': department_code, 'effective_end_date__isnull': True}
#             if bg_id:
#                 dept_filter['business_group_id'] = bg_id
#
#             try:
#                 dept = Department.objects.filter(**dept_filter).first()
#                 if not dept:
#                     raise Department.DoesNotExist
#                 data['department'] = dept.id
#             except Department.DoesNotExist:
#                 if bg_id:
#                     raise serializers.ValidationError({
#                         'department_code': f"No active department with code '{department_code}' found in the specified business group."
#                     })
#                 else:
#                     raise serializers.ValidationError({
#                         'department_code': f"No active department found with code '{department_code}'"
#                     })
#
#         is_global = data.get('is_global', False)
#         business_group = data.get('business_group')
#         department = data.get('department')
#         user = data.get('user')
#
#         # Rule 1: Global scope cannot have BG or department
#         if is_global and (business_group or department):
#             raise serializers.ValidationError(
#                 "Global scope cannot have business_group or department. Global scope applies to all."
#             )
#
#         # Rule 2: Must have either global or BG
#         if not is_global and not business_group:
#             raise serializers.ValidationError(
#                 "Must specify either business_group/business_group_code or set is_global to True."
#             )
#
#         # Rule 3: Department scope requires BG
#         if department and not business_group:
#             raise serializers.ValidationError(
#                 "Department scope requires business_group to be set."
#             )
#
#         # Rule 4: Check for duplicate (user, BG, dept) combination
#         if user:
#             existing = UserDataScope.objects.filter(
#                 user_id=user,
#                 business_group_id=business_group,
#                 department_id=department
#             ).exists()
#
#             if existing:
#                 if department:
#                     dept_obj = Department.objects.get(id=department)
#                     bg_obj = BusinessGroup.objects.get(id=business_group)
#                     raise serializers.ValidationError(
#                         f"This user already has access to department {dept_obj.code} in {bg_obj.code}."
#                     )
#                 elif business_group:
#                     bg_obj = BusinessGroup.objects.get(id=business_group)
#                     raise serializers.ValidationError(
#                         f"This user already has full access to business group {bg_obj.code}."
#                     )
#                 else:
#                     raise serializers.ValidationError(
#                         "This user already has global access."
#                     )
#
#         return data
#
#     def create(self, validated_data):
#         # Map IDs to _id fields for creation
#         if 'user' in validated_data:
#             validated_data['user_id'] = validated_data.pop('user')
#         if 'business_group' in validated_data:
#             validated_data['business_group_id'] = validated_data.pop('business_group')
#         if 'department' in validated_data:
#             validated_data['department_id'] = validated_data.pop('department')
#
#         return UserDataScope.objects.create(**validated_data)
#
#
# class BulkScopeAssignmentSerializer(serializers.Serializer):
#     """
#     Bulk assign multiple scopes to a user at once.
#
#     Request format:
#     {
#         "user_email": "user@company.com",  // or "user": 123
#         "business_groups": ["EGY", "UAE"],  // codes or IDs
#         "departments": ["IT", "SALES"],     // codes (optional)
#         "is_global": false                  // (optional)
#     }
#
#     Creates multiple UserDataScope entries in a single transaction.
#     """
#     # User - ID or email lookup
#     user = serializers.IntegerField(required=False, allow_null=True)
#     user_email = serializers.EmailField(required=False, allow_null=True, write_only=True)
#
#     # Lists of business groups (IDs or codes)
#     business_groups = serializers.ListField(
#         child=serializers.CharField(max_length=50),
#         required=False,
#         allow_empty=True,
#         help_text="List of business group IDs or codes"
#     )
#
#     # Lists of departments (IDs or codes)
#     departments = serializers.ListField(
#         child=serializers.CharField(max_length=50),
#         required=False,
#         allow_empty=True,
#         help_text="List of department IDs or codes"
#     )
#
#     is_global = serializers.BooleanField(default=False)
#
#     def validate(self, data):
#         """Validate user and convert codes to IDs"""
#         # User: email → ID
#         user_email = data.pop('user_email', None)
#         if user_email and not data.get('user'):
#             try:
#                 user = UserAccount.objects.get(email=user_email)
#                 data['user'] = user.id
#             except UserAccount.DoesNotExist:
#                 raise serializers.ValidationError({
#                     'user_email': f"No user found with email '{user_email}'"
#                 })
#
#         if not data.get('user'):
#             raise serializers.ValidationError({'user': 'Either user or user_email is required.'})
#
#         is_global = data.get('is_global', False)
#         business_groups = data.get('business_groups', [])
#         departments = data.get('departments', [])
#
#         # Validation: Must provide at least one scope type
#         if not is_global and not business_groups and not departments:
#             raise serializers.ValidationError(
#                 "Must provide at least one of: is_global=True, business_groups, or departments."
#             )
#
#         # Validation: Global scope cannot have BG or departments
#         if is_global and (business_groups or departments):
#             raise serializers.ValidationError(
#                 "Global scope cannot have business_groups or departments. Set is_global=True only."
#             )
#
#         # Convert business group codes/IDs to IDs
#         if business_groups:
#             from django.utils import timezone
#             today = timezone.now().date()
#             resolved_bgs = []
#             for bg_value in business_groups:
#                 # Try as ID first, then as code
#                 try:
#                     if str(bg_value).isdigit():
#                         bg = BusinessGroup.objects.filter(id=int(bg_value)).active_on(today).first()
#                         if not bg:
#                             raise BusinessGroup.DoesNotExist
#                     else:
#                         bg = BusinessGroup.objects.filter(code=bg_value).active_on(today).first()
#                         if not bg:
#                             raise BusinessGroup.DoesNotExist
#                     resolved_bgs.append(bg.id)
#                 except BusinessGroup.DoesNotExist:
#                     raise serializers.ValidationError({
#                         'business_groups': f"Business group '{bg_value}' not found or not active."
#                     })
#             data['business_groups_ids'] = resolved_bgs
#
#         # Convert department codes/IDs to IDs
#         if departments:
#             from django.utils import timezone
#             today = timezone.now().date()
#             resolved_depts = []
#             for dept_value in departments:
#                 # Try as ID first, then as code
#                 try:
#                     if str(dept_value).isdigit():
#                         dept = Department.objects.active_on(today).get(id=int(dept_value))
#                     else:
#                         dept = Department.objects.active_on(today).get(code=dept_value)
#                     resolved_depts.append({'id': dept.id, 'bg_id': dept.business_group_id})
#                 except Department.DoesNotExist:
#                     raise serializers.ValidationError({
#                         'departments': f"Department '{dept_value}' not found or not active."
#                     })
#             data['departments_ids'] = resolved_depts
#
#         return data
