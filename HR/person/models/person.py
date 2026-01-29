from django.db import models
from datetime import date
from Finance.core.base_models import ManagedParentModel, ManagedParentManager
from core.base.models import AuditMixin

class Person(ManagedParentModel, AuditMixin, models.Model):
    """
    Core person identity - MANAGED PARENT

    ⚠️ CRITICAL: Do NOT create Person instances directly!
    Create Employee, Applicant, ContingentWorker, or Contact instead.

    Person type is INFERRED from active child records.
    NO person_type FK stored - computed dynamically.

    Usage:
        # WRONG ❌
        person = Person.objects.create(...)  # Raises PermissionDenied

        # CORRECT ✅
        employee = Employee.objects.create(
            first_name="Donia",
            email_address="donia@company.com",
            employee_type=perm_emp_type,
            effective_start_date=date.today(),
            employee_number="E001"
        )
        # Person automatically created, all fields proxied!
    """

    # Name fields
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    first_name_arabic = models.CharField(max_length=100, blank=True)
    middle_name_arabic = models.CharField(max_length=100, blank=True)
    last_name_arabic = models.CharField(max_length=100, blank=True)

    # Identifiers
    national_id = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        help_text="National ID / SSN"
    )
    email_address = models.EmailField(unique=True)

    # Demographics
    title = models.CharField(
        max_length=10,
        choices=[
            ('Mr', 'Mr'),
            ('Mrs', 'Mrs'),
            ('Ms', 'Ms'),
            ('Dr', 'Dr'),
            ('Prof', 'Prof'),
            ('Eng', 'Eng')
        ],
        blank=True
    )
    gender = models.CharField(
        max_length=10,
        choices=[('Male', 'Male'), ('Female', 'Female')]
    )
    date_of_birth = models.DateField()
    nationality = models.CharField(max_length=100)
    marital_status = models.CharField(
        max_length=20,
        choices=[
            ('Single', 'Single'),
            ('Married', 'Married'),
            ('Divorced', 'Divorced'),
            ('Widowed', 'Widowed')
        ]
    )

    # Additional Info
    religion = models.CharField(max_length=50, blank=True)
    blood_type = models.CharField(max_length=5, blank=True)

    objects = ManagedParentManager()

    class Meta:
        db_table = 'person'
        indexes = [
            models.Index(fields=['email_address']),
            models.Index(fields=['national_id']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        """Full name in English"""
        parts = [self.first_name, self.middle_name, self.last_name]
        return ' '.join(p for p in parts if p)

    @property
    def full_name_arabic(self):
        """Full name in Arabic"""
        parts = [self.first_name_arabic, self.middle_name_arabic, self.last_name_arabic]
        return ' '.join(p for p in parts if p)

    @property
    def age(self):
        """Calculate age from date of birth"""
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    # ==================== TYPE INFERENCE METHODS ====================

    def get_type_on_date(self, reference_date):
        """
        Infer person type from child records active on specific date.

        Priority: EMP > CWK > APL > CON

        Returns:
            PersonType or None
        """
        # ! pending model creation
        from .employee import Employee
        from .applicant import Applicant
        from .contingent_worker import ContingentWorker
        from .contact import Contact

        # Check Employee periods (highest priority) using VersionedManager
        emp = Employee.objects.active_on(reference_date).filter(person=self).first()
        if emp:
            return emp.employee_type

        # Check ContingentWorker periods
        cwk = ContingentWorker.objects.active_on(reference_date).filter(person=self).first()
        if cwk:
            return cwk.worker_type

        # Check Applicant periods
        apl = Applicant.objects.active_on(reference_date).filter(person=self).first()
        if apl:
            return apl.applicant_type

        # Check Contact periods (lowest priority)
        con = Contact.objects.active_on(reference_date).filter(person=self).first()
        if con:
            return con.contact_type

        return None  # No active role on this date

    @property
    def current_type(self):
        """Current person type (today). COMPUTED, not stored."""
        return self.get_type_on_date(date.today())

    @property
    def current_base_type(self):
        """Current base type code (EMP/APL/CWK/CON). COMPUTED."""
        current = self.current_type
        return current.base_type if current else None

    def get_all_types_in_period(self, start_date, end_date):
        """
        Get all types person had during a period.

        Returns:
            List of PersonType objects
        """
        from .employee import Employee
        from .applicant import Applicant
        from .contingent_worker import ContingentWorker
        from .contact import Contact

        types = set()

        # Check each child model for overlapping periods using VersionedManager
        for emp in Employee.objects.active_between(start_date, end_date).filter(person=self):
            types.add(emp.employee_type)

        for cwk in ContingentWorker.objects.active_between(start_date, end_date).filter(person=self):
            types.add(cwk.worker_type)

        for apl in Applicant.objects.active_between(start_date, end_date).filter(person=self):
            types.add(apl.applicant_type)

        for con in Contact.objects.active_between(start_date, end_date).filter(person=self):
            types.add(con.contact_type)

        return list(types)

    def get_active_roles(self):
        """
        Get all current roles (for multi-role scenarios).
        Returns:
            List of base type codes: ['EMP', 'APL', ...]
        """
        today = date.today()
        types = self.get_all_types_in_period(today, today)
        return [t.base_type for t in types if t]
