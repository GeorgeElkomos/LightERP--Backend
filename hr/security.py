from django.core.exceptions import PermissionDenied
from hr.models.security import UserDataScope

def validate_data_scope_on_create(user, business_group_id):
    """
    Validate that the user has permission to create/update data in the given Business Group.
    """
    if user.is_super_admin():
        return
    
    # Check for global scope
    if UserDataScope.objects.filter(user=user, is_global=True).exists():
        return
    
    # Check specific scope
    if not UserDataScope.objects.filter(user=user, business_group_id=business_group_id).exists():
        raise PermissionDenied("You do not have access to this Business Group")
