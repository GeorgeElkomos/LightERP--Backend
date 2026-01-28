from django.core.management import call_command
from django.utils import timezone
from core.job_roles.models import JobRole, UserJobRole
import io

def setup_core_data():
    """Initialize core system data for tests once and suppressing print output"""
    # Check if already setup in this transaction to minimize calls
    if JobRole.objects.filter(code='admin').exists():
        return

    # Suppress output using a dummy buffer
    buffer = io.StringIO()
    call_command('init_core_data', verbosity=0, stdout=buffer)

def setup_admin_permissions(user):
    """Helper to grant admin role to a user"""
    # Ensure core data exists
    if not JobRole.objects.filter(code='admin').exists():
        setup_core_data()

    admin_role = JobRole.objects.get(code='admin')
    UserJobRole.objects.get_or_create(
        user=user,
        job_role=admin_role,
        defaults={'effective_start_date': timezone.now().date()}
    )

