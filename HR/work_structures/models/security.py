# * hold off on this model for now - not in use
# from django.db import models
# from django.db.models import Q
# from core.base.models import AuditMixin
#
#
# class UserDataScope(AuditMixin, models.Model):
#     """
#     Hierarchical data scope for users.
#
#     Scope Levels (most specific to broadest):
#     1. Global: sees everything (is_global=True)
#     2. Business Group: sees all departments/locations/positions in BG
#     3. Department: sees only specific departments and their locations/positions
#
#     Security Pattern:
#     - JobRole: "You can Edit Departments"
#     - DataScope: "...but only in 'Egypt Operations' BG" OR "...only in IT Department"
#
#     Examples:
#     - BG scope: UserDataScope(user=u, business_group=bg1) → all depts in BG1
#     - Dept scope: UserDataScope(user=u, business_group=bg2, department=dept3) → only dept3
#     - Mixed: User can have multiple scopes (additive OR logic)
#     """
#     user = models.ForeignKey(
#         'user_accounts.UserAccount',
#         on_delete=models.CASCADE,
#         related_name='hr_data_scopes'
#     )
#     is_global = models.BooleanField(
#         default=False,
#         help_text="If true, user can access ALL Business Groups"
#     )
#
#     # Hierarchical scope - null = broader access
#     business_group = models.ForeignKey(
#         'BusinessGroup',
#         on_delete=models.CASCADE,
#         null=True,
#         blank=True,
#         help_text="Business Group scope. If department is null, grants access to all departments in BG"
#     )
#     department = models.ForeignKey(
#         'Department',
#         on_delete=models.CASCADE,
#         null=True,
#         blank=True,
#         help_text="If set, restricts access to only this department within the BG"
#     )
#
#     class Meta:
#         db_table = 'hr_user_data_scope'
#         verbose_name = 'User Data Scope'
#         verbose_name_plural = 'User Data Scopes'
#         constraints = [
#             # Must have either global flag or business_group
#             models.CheckConstraint(
#                 check=Q(is_global=True) | Q(business_group__isnull=False),
#                 name='scope_requires_bg_or_global'
#             ),
#             # Department scope requires business_group
#             models.CheckConstraint(
#                 check=Q(department__isnull=True) | Q(business_group__isnull=False),
#                 name='dept_scope_requires_bg'
#             ),
#             # Unique combination of user, BG, and department
#             models.UniqueConstraint(
#                 fields=['user', 'business_group', 'department'],
#                 name='unique_user_scope_combination'
#             )
#         ]
#         indexes = [
#             models.Index(fields=['user', 'is_global']),
#             models.Index(fields=['user', 'business_group']),
#             models.Index(fields=['user', 'department']),
#         ]
#
#     def clean(self):
#         """
#         Validate that global scope doesn't conflict with specific scopes.
#
#         Business Rule: If a user has is_global=True, they shouldn't have
#         other scope entries as they would be redundant and contradictory.
#         """
#         from django.core.exceptions import ValidationError
#
#         if self.is_global:
#             # Check for other scopes for this user
#             other_scopes = UserDataScope.objects.filter(
#                 user=self.user
#             ).exclude(pk=self.pk)
#
#             if other_scopes.exists():
#                 raise ValidationError(
#                     "Cannot create global scope: user already has specific scopes. "
#                     "Delete existing scopes first or remove is_global flag."
#                 )
#         else:
#             # Check if user already has global scope
#             if UserDataScope.objects.filter(user=self.user, is_global=True).exclude(pk=self.pk).exists():
#                 raise ValidationError(
#                     "Cannot create specific scope: user already has global scope. "
#                     "Remove global scope first to add specific scopes."
#                 )
#
#     def __str__(self):
#         if self.is_global:
#             return f"{self.user.email} - Global Access"
#         elif self.department:
#             return f"{self.user.email} - {self.business_group.code} → {self.department.code}"
#         elif self.business_group:
#             return f"{self.user.email} - {self.business_group.code} (Full)"
#         return f"{self.user.email} - No Scope"
#
