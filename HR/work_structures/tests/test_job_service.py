"""
Unit tests for Job Service
Tests job CRUD operations with versioning and M2M relationships
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from datetime import date, timedelta

from HR.work_structures.models import Job, Organization, Grade, Location
from HR.work_structures.services.job_service import JobService
from HR.work_structures.dtos import JobCreateDTO, JobUpdateDTO, CompetencyRequirementDTO
from HR.person.models import Competency
from core.lookups.models import LookupType, LookupValue

User = get_user_model()


class JobServiceTest(TestCase):
    """Test JobService business logic"""

    @classmethod
    def setUpTestData(cls):
        """Set up test data once for all tests"""
        # Create test user
        cls.user = User.objects.create_user(
            email='test@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass123'
        )

        # Create lookup types
        org_type_lookup = LookupType.objects.create(name='Organization Type')
        org_name_type = LookupType.objects.create(name='Organization Name')
        grade_name_type = LookupType.objects.create(name='Grade Name')
        job_category_type = LookupType.objects.create(name='Job Category')
        job_title_type = LookupType.objects.create(name='Job Title')
        functional_area_type = LookupType.objects.create(name='Functional Area')
        proficiency_level_type = LookupType.objects.create(name='Proficiency Level')
        comp_category_type = LookupType.objects.create(name='Competency Category')
        country_type = LookupType.objects.create(name='Country')
        city_type = LookupType.objects.create(name='City')

        # Create lookups
        cls.org_type_hq = LookupValue.objects.create(
            lookup_type=org_type_lookup, name='Business Group', is_active=True
        )
        cls.org_name = LookupValue.objects.create(
            lookup_type=org_name_type, name='Headquarters', is_active=True
        )
        cls.grade_name_1 = LookupValue.objects.create(
            lookup_type=grade_name_type, name='Grade 1', is_active=True
        )
        cls.grade_name_2 = LookupValue.objects.create(
            lookup_type=grade_name_type, name='Grade 2', is_active=True
        )
        cls.job_category_tech = LookupValue.objects.create(
            lookup_type=job_category_type, name='Technical', is_active=True
        )
        cls.job_title_dev = LookupValue.objects.create(
            lookup_type=job_title_type, name='Software Developer', is_active=True
        )
        cls.functional_area_ops = LookupValue.objects.create(
            lookup_type=functional_area_type, name='Operations', is_active=True
        )
        cls.proficiency_expert = LookupValue.objects.create(
            lookup_type=proficiency_level_type, name='Expert', is_active=True
        )
        cls.proficiency_intermediate = LookupValue.objects.create(
            lookup_type=proficiency_level_type, name='Intermediate', is_active=True
        )

        country = LookupValue.objects.create(
            lookup_type=country_type, name='Egypt', is_active=True
        )
        city = LookupValue.objects.create(
            lookup_type=city_type, name='Cairo', parent=country, is_active=True
        )

        # Create root organization without location first
        cls.root_org = Organization.objects.create(
            organization_name='BG001',
            organization_type=cls.org_type_hq,
            effective_start_date=date.today() - timedelta(days=365),
            created_by=cls.user,
            updated_by=cls.user
        )

        # Create location
        cls.location = Location.objects.create(
            business_group=cls.root_org,
            location_name='Cairo Office',
            country=country,
            city=city,
            created_by=cls.user,
            updated_by=cls.user
        )

        # Update org with location
        Organization.objects.filter(pk=cls.root_org.pk).update(location=cls.location)
        cls.root_org.refresh_from_db()

        # Create grades
        cls.grade1 = Grade.objects.create(
            organization=cls.root_org,
            sequence=1,
            grade_name=cls.grade_name_1,
            created_by=cls.user,
            updated_by=cls.user
        )
        cls.grade2 = Grade.objects.create(
            organization=cls.root_org,
            sequence=2,
            grade_name=cls.grade_name_2,
            created_by=cls.user,
            updated_by=cls.user
        )

        # Create competencies
        comp_category = LookupValue.objects.create(
            lookup_type=comp_category_type, name='Technical', is_active=True
        )
        cls.comp_python = Competency.objects.create(
            code='PYTHON',
            name='Python Programming',
            category=comp_category,
            created_by=cls.user,
            updated_by=cls.user
        )
        cls.comp_java = Competency.objects.create(
            code='JAVA',
            name='Java Programming',
            category=comp_category,
            created_by=cls.user,
            updated_by=cls.user
        )

    def test_create_job_success(self):
        """Test successful job creation"""
        dto = JobCreateDTO(
            code='JOB001',
            business_group_id=self.root_org.id,
            job_category_id=self.job_category_tech.id,
            job_title_id=self.job_title_dev.id,
            job_description='Develop and maintain software applications',
            responsibilities=[
                'Write clean, maintainable code',
                'Review code from peers',
                'Participate in agile ceremonies'
            ],
            competency_requirements=[
                CompetencyRequirementDTO(
                    competency_id=self.comp_python.id,
                    proficiency_level_id=self.proficiency_expert.id
                ),
                CompetencyRequirementDTO(
                    competency_id=self.comp_java.id,
                    proficiency_level_id=self.proficiency_intermediate.id
                )
            ],
            grade_ids=[self.grade1.id, self.grade2.id]
        )

        job = JobService.create(self.user, dto)

        self.assertIsNotNone(job.id)
        self.assertEqual(job.code, 'JOB001')
        self.assertEqual(job.business_group.id, self.root_org.id)
        self.assertEqual(len(job.responsibilities), 3)
        self.assertEqual(job.competency_requirements.count(), 2)
        self.assertEqual(job.grades.count(), 2)

    def test_create_job_duplicate_code_same_date_fails(self):
        """Test creation fails with duplicate code+business_group+effective_start_date"""
        # Create first job
        start_date = date.today()
        Job.objects.create(
            code='DUP001',
            business_group=self.root_org,
            job_category=self.job_category_tech,
            job_title=self.job_title_dev,
            job_description='Test',
            responsibilities=[],
            effective_start_date=start_date,
            created_by=self.user,
            updated_by=self.user
        )

        # Try to create another with same code+bg+start_date (should fail)
        dto = JobCreateDTO(
            code='DUP001',
            business_group_id=self.root_org.id,
            job_category_id=self.job_category_tech.id,
            job_title_id=self.job_title_dev.id,
            job_description='Another job',
            responsibilities=[],
            effective_start_date=start_date
        )

        with self.assertRaises(Exception):  # Will raise IntegrityError
            JobService.create(self.user, dto)

    def test_create_job_grade_from_different_bg_fails(self):
        """Test that grades must belong to same business group"""
        # Create second business group
        root_org_2 = Organization.objects.create(
            organization_name='BG002',
            organization_type=self.org_type_hq,
            location=self.location,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        # Create grade in second BG
        grade_other = Grade.objects.create(
            organization=root_org_2,
            sequence=3,
            grade_name=self.grade_name_1,
            created_by=self.user,
            updated_by=self.user
        )

        # Try to create job with grade from different BG
        dto = JobCreateDTO(
            code='JOB002',
            business_group_id=self.root_org.id,
            job_category_id=self.job_category_tech.id,
            job_title_id=self.job_title_dev.id,
            job_description='Test',
            responsibilities=[],
            grade_ids=[grade_other.id]  # Grade from different BG
        )

        with self.assertRaises(ValidationError) as context:
            JobService.create(self.user, dto)

        error_msg = str(context.exception).lower()
        self.assertTrue('grade' in error_msg and 'business group' in error_msg)

    def test_create_job_responsibilities_not_list_fails(self):
        """Test that responsibilities must be a list"""
        dto = JobCreateDTO(
            code='JOB003',
            business_group_id=self.root_org.id,
            job_category_id=self.job_category_tech.id,
            job_title_id=self.job_title_dev.id,
            job_description='Test',
            responsibilities="Not a list"  # Should be list
        )

        with self.assertRaises(ValidationError) as context:
            JobService.create(self.user, dto)

        self.assertIn('responsibilities', str(context.exception).lower())

    def test_create_job_with_effective_end_date(self):
        """Test creating job with effective end date"""
        start_date = date(2024, 1, 1)
        end_date = date(2025, 12, 31)
        dto = JobCreateDTO(
            code='JOB_WITH_END',
            business_group_id=self.root_org.id,
            job_category_id=self.job_category_tech.id,
            job_title_id=self.job_title_dev.id,
            job_description='Test Description',
            responsibilities=['Task 1'],
            effective_start_date=start_date,
            effective_end_date=end_date
        )
        job = JobService.create(self.user, dto)
        
        self.assertEqual(job.effective_end_date, end_date)

    def test_update_job_correction_mode(self):
        """Test updating job in correction mode (same effective_start_date)"""
        # Create job
        job = Job.objects.create(
            code='JOB004',
            business_group=self.root_org,
            job_category=self.job_category_tech,
            job_title=self.job_title_dev,
            job_description='Original description',
            responsibilities=['Task 1', 'Task 2'],
            effective_start_date=date.today() - timedelta(days=10),
            created_by=self.user,
            updated_by=self.user
        )

        # Update in correction mode (no new_start_date)
        dto = JobUpdateDTO(
            job_id=job.id,
            job_description='Updated description',
            responsibilities=['Task 1', 'Task 2', 'Task 3']
        )

        updated = JobService.update(self.user, dto)

        self.assertEqual(updated.id, job.id)  # Same record
        self.assertEqual(updated.job_description, 'Updated description')
        self.assertEqual(len(updated.responsibilities), 3)

    def test_update_job_new_version_mode(self):
        """Test creating new version of job"""
        # Create job
        job = Job.objects.create(
            code='JOB005',
            business_group=self.root_org,
            job_category=self.job_category_tech,
            job_title=self.job_title_dev,
            job_description='Original',
            responsibilities=['Task 1'],
            effective_start_date=date.today() - timedelta(days=30),
            created_by=self.user,
            updated_by=self.user
        )

        # Update with new version (new_start_date provided)
        new_start = date.today() + timedelta(days=10)
        dto = JobUpdateDTO(
            job_id=job.id,
            job_description='New version description',
            new_start_date=new_start
        )

        updated = JobService.update(self.user, dto)

        self.assertNotEqual(updated.id, job.id)  # New record
        self.assertEqual(updated.effective_start_date, new_start)
        self.assertEqual(updated.job_description, 'New version description')

        # Old version should be end-dated
        job.refresh_from_db()
        self.assertIsNotNone(job.effective_end_date)

    def test_deactivate_job(self):
        """Test deactivating a job"""
        job = Job.objects.create(
            code='JOB006',
            business_group=self.root_org,
            job_category=self.job_category_tech,
            job_title=self.job_title_dev,
            job_description='Test',
            responsibilities=[],
            effective_start_date=date.today() - timedelta(days=10),
            created_by=self.user,
            updated_by=self.user
        )

        deactivated = JobService.deactivate(self.user, job.id)

        self.assertEqual(deactivated.id, job.id)
        self.assertIsNotNone(deactivated.effective_end_date)

        # Should not be in active queryset
        active_jobs = Job.objects.active_on(date.today()).filter(code='JOB006')
        self.assertEqual(active_jobs.count(), 0)

    def test_get_jobs_by_business_group(self):
        """Test retrieving jobs by business group"""
        # Create multiple jobs
        Job.objects.create(
            code='JOB007',
            business_group=self.root_org,
            job_category=self.job_category_tech,
            job_title=self.job_title_dev,
            job_description='Job 1',
            responsibilities=[],
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )
        Job.objects.create(
            code='JOB008',
            business_group=self.root_org,
            job_category=self.job_category_tech,
            job_title=self.job_title_dev,
            job_description='Job 2',
            responsibilities=[],
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        jobs = JobService.get_jobs_by_business_group(self.root_org.id)

        self.assertEqual(jobs.count(), 2)

    def test_get_job_by_code(self):
        """Test retrieving job by code"""
        job = Job.objects.create(
            code='JOB009',
            business_group=self.root_org,
            job_category=self.job_category_tech,
            job_title=self.job_title_dev,
            job_description='Test',
            responsibilities=[],
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        found = JobService.get_job_by_code('JOB009')

        self.assertIsNotNone(found)
        self.assertEqual(found.id, job.id)

    def test_get_job_versions(self):
        """Test retrieving all versions of a job"""
        # Create original version
        job1 = Job.objects.create(
            code='JOB010',
            business_group=self.root_org,
            job_category=self.job_category_tech,
            job_title=self.job_title_dev,
            job_description='Version 1',
            responsibilities=[],
            effective_start_date=date.today() - timedelta(days=60),
            effective_end_date=date.today() - timedelta(days=30),
            created_by=self.user,
            updated_by=self.user
        )

        # Create new version
        job2 = Job.objects.create(
            code='JOB010',
            business_group=self.root_org,
            job_category=self.job_category_tech,
            job_title=self.job_title_dev,
            job_description='Version 2',
            responsibilities=[],
            effective_start_date=date.today() - timedelta(days=29),
            created_by=self.user,
            updated_by=self.user
        )

        versions = JobService.get_job_versions(job1.id)

        self.assertEqual(versions.count(), 2)
        # Should be ordered by effective_start_date (newest first)
        self.assertEqual(versions[0].id, job2.id)
        self.assertEqual(versions[1].id, job1.id)

    def test_update_m2m_relationships(self):
        """Test updating M2M competencies and grades"""
        from HR.person.models import JobCompetencyRequirement
        
        job = Job.objects.create(
            code='JOB011',
            business_group=self.root_org,
            job_category=self.job_category_tech,
            job_title=self.job_title_dev,
            job_description='Test',
            responsibilities=[],
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )
        # Create initial competency requirement
        JobCompetencyRequirement.objects.create(
            job=job,
            competency=self.comp_python,
            proficiency_level=self.proficiency_expert,
            created_by=self.user,
            updated_by=self.user
        )
        job.grades.set([self.grade1])

        # Update M2M relationships
        dto = JobUpdateDTO(
            job_id=job.id,
            competency_requirements=[
                CompetencyRequirementDTO(
                    competency_id=self.comp_java.id,
                    proficiency_level_id=self.proficiency_intermediate.id
                )
            ],  # Changed from Python to Java
            grade_ids=[self.grade1.id, self.grade2.id]  # Added grade2
        )

        updated = JobService.update(self.user, dto)

        self.assertEqual(updated.competency_requirements.count(), 1)
        self.assertEqual(updated.competency_requirements.first().competency.code, 'JAVA')
        self.assertEqual(updated.grades.count(), 2)
