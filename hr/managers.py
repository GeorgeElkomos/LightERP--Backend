from django.db import models

class ScopedQuerySet(models.QuerySet):
    """QuerySet with scoping logic for chainability"""
    
    def scoped(self, user):
        from hr.models.security import UserDataScope
        
        if user.is_super_admin():
            return self.all()
        
        if UserDataScope.objects.filter(user=user, is_global=True).exists():
            return self.all()
        
        allowed_bg_ids = UserDataScope.objects.filter(
            user=user,
            is_global=False
        ).values_list('business_group_id', flat=True)
        
        if not allowed_bg_ids:
            return self.none()
        
        # Determine how to filter based on model type
        model_name = self.model.__name__
        if model_name == 'Department':
            return self.filter(business_group_id__in=allowed_bg_ids)
        elif model_name == 'Position':
            return self.filter(department__business_group_id__in=allowed_bg_ids)
        elif model_name == 'Location':
            return self.filter(business_group_id__in=allowed_bg_ids)
        elif model_name == 'Grade':
            return self.filter(business_group_id__in=allowed_bg_ids)
        
        return self.all()


class DateTrackedQuerySet(ScopedQuerySet):
    """QuerySet for date-tracked records"""
    
    def active_on(self, date):
        from django.db.models import Q
        return self.filter(
            Q(effective_start_date__lte=date) &
            (Q(effective_end_date__gte=date) | Q(effective_end_date__isnull=True))
        )
    
    def currently_active(self):
        from django.utils import timezone
        return self.active_on(timezone.now().date())


class ScopedManagerMixin:
    """Mixin for filtering by user's Business Group scope"""
    def scoped(self, user):
        return self.get_queryset().scoped(user)


class DateTrackedModelManager(models.Manager.from_queryset(DateTrackedQuerySet)):
    """Manager for querying date-tracked records"""
    pass


class DepartmentManager(ScopedManagerMixin, DateTrackedModelManager):
    pass


class PositionManager(ScopedManagerMixin, DateTrackedModelManager):
    pass


class LocationManager(ScopedManagerMixin, models.Manager.from_queryset(ScopedQuerySet)):
    pass


class GradeManager(ScopedManagerMixin, DateTrackedModelManager):
    pass
