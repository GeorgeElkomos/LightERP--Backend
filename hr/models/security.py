from django.db import models

class UserDataScope(models.Model):
    """
    Defines which Business Groups a user can access.
    
    Security Pattern:
    - JobRole: "You can Edit Departments"
    - DataScope: "...but only in 'Egypt Operations' BG"
    
    Requirements: All C.X.6 (Permissions & Security)
    """
    user = models.ForeignKey(
        'user_accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='hr_data_scopes'
    )
    business_group = models.ForeignKey(
        'hr.BusinessGroup',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    is_global = models.BooleanField(
        default=False,
        help_text="If true, user can access ALL Business Groups"
    )
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'business_group'],
                name='unique_user_bg_scope'
            )
        ]

