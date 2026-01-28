from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from datetime import date, time
from decimal import Decimal
from core.lookups.models import LookupType, LookupValue
from core.user_accounts.models import UserAccount
from HR.work_structures.models import (
    Organization, Location, Grade, Job, Position, GradeRate, GradeRateType,
    JobQualificationRequirement, PositionQualificationRequirement
)
from HR.person.models import (
    Competency, PersonType, Person, Employee, Address, Assignment, Contract,
    JobCompetencyRequirement, PositionCompetencyRequirement, Qualification, Contact,
    CompetencyProficiency
)
from core.job_roles.models import (
JobRole, UserJobRole
)

class Command(BaseCommand):
    help = 'Generate all fixture data programmatically'

    def populate_lookup_types(self):
        self.stdout.write(f'\n* Creating Lookup Types...')
        lookup_types_data = [
            (100, 'Country', 'Countries for addresses and locations'),
            (101, 'City', 'Cities for addresses and locations'),
            (102, 'Address Type', 'Types of addresses'),
            (103, 'Organization Type', 'Organization type lookup'),
            (105, 'Job Category', 'Job categories'),
            (106, 'Job Title', 'Job titles'),
            (109, 'Proficiency Level', 'Skill/competency proficiency levels'),
            (112, 'Position Title', 'Position titles'),
            (113, 'Position Type', 'Position types'),
            (114, 'Position Status', 'Position status'),
            (115, 'Payroll', 'Payroll frequency types'),
            (116, 'Salary Basis', 'Salary basis types'),
            (117, 'Grade Name', 'Grades within organizations'),
            (118, 'Qualification Type', 'Types of qualifications/education'),
            (119, 'Qualification Title', 'Qualification degree/certificate titles'),
            (120, 'Qualification Status', 'Status of educational qualifications'),
            (121, 'Tuition Method', 'Methods of education delivery'),
            (122, 'Currency', 'Currency codes'),
            (123, 'Competency Category', 'Categories of competencies'),
            (124, 'Proficiency Source', 'Sources of competency proficiency assessment'),
            (125, 'Contract Status', 'Statuses for employee contracts'),
            (126, 'Contract End Reason', 'Reasons for ending a contract'),
            (127, 'Assignment Action Reason', 'Reasons for assignment changes/actions'),
            (128, 'Assignment Status', 'Statuses for employee assignments'),
            (129, 'Probation Period', 'Durations for probation periods'),
            (130, 'Termination Notice Period', 'Notice periods required for termination'),
            (131, 'Awarding Entity', 'Institutions or bodies that grant qualifications'),
        ]

        for pk, name, desc in lookup_types_data:
            LookupType.objects.update_or_create(
                pk=pk,
                defaults={
                    'name': name,
                    'description': desc
                }
            )
        self.stdout.write(f'  ✓ Created {len(lookup_types_data)} lookup types')

    def populate_lookup_values(self):
        self.stdout.write(f'\n* Creating Lookup Values...')
        # Countries
        countries = [
            (1000, 100, 'Egypt', 'Arab Republic of Egypt', 10),
            (1001, 100, 'United Arab Emirates', '', 20),
            (1002, 100, 'Saudi Arabia', 'Kingdom of Saudi Arabia', 30),
            (1003, 100, 'United States', 'United States of America', 40),
            (1004, 100, 'United Kingdom', '', 50),
        ]

        for pk, lt, name, desc, seq in countries:
            LookupValue.objects.update_or_create(
                pk=pk,
                defaults={
                    'lookup_type_id': lt,
                    'name': name,
                    'description': desc,
                    'sequence': seq,
                    'is_active': True
                }
            )

        # Cities (with parent country)
        cities = [
            (1010, 101, 'Cairo', '', 10, 1000),
            (1011, 101, 'Alexandria', '', 20, 1000),
            (1012, 101, 'Giza', '', 30, 1000),
            (1013, 101, 'Dubai', '', 40, 1001),
            (1014, 101, 'Abu Dhabi', '', 50, 1001),
            (1015, 101, 'Riyadh', '', 60, 1002),
        ]

        for pk, lt, name, desc, seq, parent in cities:
            LookupValue.objects.update_or_create(
                pk=pk,
                defaults={
                    'lookup_type_id': lt,
                    'name': name,
                    'description': desc,
                    'sequence': seq,
                    'is_active': True,
                    'parent_id': parent
                }
            )

        # Address Types
        address_types = [
            (1020, 102, 'Home Address', 'Primary residential address', 10),
            (1021, 102, 'Residential Address', 'Current residential address', 20),
            (1022, 102, 'Work Address', 'Office/workplace address', 30),
            (1023, 102, 'Mailing Address', 'Correspondence mailing address', 40),
        ]

        for pk, lt, name, desc, seq in address_types:
            LookupValue.objects.update_or_create(
                pk=pk,
                defaults={
                    'lookup_type_id': lt,
                    'name': name,
                    'description': desc,
                    'sequence': seq,
                    'is_active': True
                }
            )

        # Organization Types
        org_types = [
            (1031, 103, 'Business Groups', 'Business Groups within the enterprise', 20),
            (1032, 103, 'Department', '', 30),
            (1033, 103, 'Unit', '', 40),
            (1034, 103, 'Team', '', 50),
        ]

        for pk, lt, name, desc, seq in org_types:
            LookupValue.objects.update_or_create(
                pk=pk,
                defaults={
                    'lookup_type_id': lt,
                    'name': name,
                    'description': desc,
                    'sequence': seq,
                    'is_active': True
                }
            )

        # Job Categories
        job_cats = [
            (1050, 105, 'Finance', 'Finance and accounting roles', 10),
            (1051, 105, 'IT', 'Information Technology roles', 20),
            (1052, 105, 'Human Resources', 'Human resources roles', 30),
            (1053, 105, 'Sales', 'Sales and business development roles', 40),
            (1054, 105, 'Operations', 'Operations and logistics roles', 50),
            (1055, 105, 'Engineering', 'Engineering and technical roles', 60),
        ]

        for pk, lt, name, desc, seq in job_cats:
            LookupValue.objects.update_or_create(
                pk=pk,
                defaults={
                    'lookup_type_id': lt,
                    'name': name,
                    'description': desc,
                    'sequence': seq,
                    'is_active': True
                }
            )

        # Job Titles (Generic)
        job_titles = [
            (1062, 106, 'Specialist', 'Specialist Role', 30),
            (1063, 106, 'Analyst', 'Analyst Role', 40),
            (1064, 106, 'Executive', 'Executive Role', 50),
            (1065, 106, 'Engineer', 'Engineering Role', 60),
            (1066, 106, 'Manager', 'Management Role', 70),
        ]

        for pk, lt, name, desc, seq in job_titles:
            LookupValue.objects.update_or_create(
                pk=pk,
                defaults={
                    'lookup_type_id': lt,
                    'name': name,
                    'description': desc,
                    'sequence': seq,
                    'is_active': True
                }
            )

        # Proficiency Levels
        prof_levels = [
            (1090, 109, 'Beginner', 'Basic level proficiency', 10),
            (1091, 109, 'Intermediate', 'Intermediate level proficiency', 20),
            (1092, 109, 'Advanced', 'Advanced level proficiency', 30),
            (1093, 109, 'Expert', 'Expert level proficiency', 40),
            (1094, 109, 'Master', 'Master level proficiency', 50),
        ]

        for pk, lt, name, desc, seq in prof_levels:
            LookupValue.objects.update_or_create(
                pk=pk,
                defaults={
                    'lookup_type_id': lt,
                    'name': name,
                    'description': desc,
                    'sequence': seq,
                    'is_active': True
                }
            )

        # Position Titles (Specific)
        pos_titles = [
            (1120, 112, 'IT Analyst', 'IT Analyst Position', 10),
            (1121, 112, 'Operations Executive', 'Operations Executive Position', 20),
            (1122, 112, 'HR Specialist', 'HR Specialist Position', 30),
            (1123, 112, 'HR Manager', 'HR Manager Position', 40),
            (1124, 112, 'Finance Analyst', 'Finance Analyst Position', 50),
            (1125, 112, 'Senior Software Engineer', 'Senior Software Engineer Position', 60),
            (1126, 112, 'Product Manager', 'Product Manager Position', 70),
        ]

        for pk, lt, name, desc, seq in pos_titles:
            LookupValue.objects.update_or_create(
                pk=pk,
                defaults={
                    'lookup_type_id': lt,
                    'name': name,
                    'description': desc,
                    'sequence': seq,
                    'is_active': True
                }
            )

        # Position Types
        pos_types = [
            (1130, 113, 'Permanent', 'Permanent employment', 10),
            (1131, 113, 'Temporary', 'Temporary employment', 20),
            (1132, 113, 'Contract', 'Contract-based employment', 30),
            (1133, 113, 'Internship', 'Internship/trainee position', 40),
        ]

        for pk, lt, name, desc, seq in pos_types:
            LookupValue.objects.update_or_create(
                pk=pk,
                defaults={
                    'lookup_type_id': lt,
                    'name': name,
                    'description': desc,
                    'sequence': seq,
                    'is_active': True
                }
            )

        # Position Statuses
        pos_statuses = [
            (1140, 114, 'Active', 'Position is active and can be filled', 10),
            (1141, 114, 'Proposed', 'Position is proposed, not yet approved', 20),
            (1142, 114, 'Frozen', 'Position is frozen, cannot be filled', 30),
            (1143, 114, 'Closed', 'Position is closed', 40),
        ]

        for pk, lt, name, desc, seq in pos_statuses:
            LookupValue.objects.update_or_create(
                pk=pk,
                defaults={
                    'lookup_type_id': lt,
                    'name': name,
                    'description': desc,
                    'sequence': seq,
                    'is_active': True
                }
            )

        # Payroll
        payrolls = [
            (1150, 115, 'Monthly', 'Monthly payroll frequency', 10),
            (1151, 115, 'Bi-Weekly', 'Every two weeks payroll', 20),
            (1152, 115, 'Weekly', 'Weekly payroll frequency', 30),
            (1153, 115, 'Hourly', 'Hourly payroll', 40),
        ]

        for pk, lt, name, desc, seq in payrolls:
            LookupValue.objects.update_or_create(
                pk=pk,
                defaults={
                    'lookup_type_id': lt,
                    'name': name,
                    'description': desc,
                    'sequence': seq,
                    'is_active': True
                }
            )

        # Salary Basis
        salary_basis = [
            (1160, 116, 'Annual', 'Annual salary basis', 10),
            (1161, 116, 'Monthly', 'Monthly salary basis', 20),
            (1162, 116, 'Hourly', 'Hourly salary basis', 30),
            (1163, 116, 'Daily', 'Daily salary basis', 40),
        ]

        for pk, lt, name, desc, seq in salary_basis:
            LookupValue.objects.update_or_create(
                pk=pk,
                defaults={
                    'lookup_type_id': lt,
                    'name': name,
                    'description': desc,
                    'sequence': seq,
                    'is_active': True
                }
            )

        # Grade Names
        grade_names = [
            (1170, 117, 'Grade 1', 'Entry level grade', 10),
            (1171, 117, 'Grade 2', '', 20),
            (1172, 117, 'Grade 3', '', 30),
            (1173, 117, 'Grade 4', '', 40),
            (1174, 117, 'Grade 5', '', 50),
            (1175, 117, 'Junior', 'Junior level', 60),
            (1176, 117, 'Mid-Level', 'Mid-level', 70),
            (1177, 117, 'Senior', 'Senior level', 80),
            (1178, 117, 'Principal', 'Principal level', 90),
            (1179, 117, 'Executive', 'Executive level', 100),
        ]

        for pk, lt, name, desc, seq in grade_names:
            LookupValue.objects.update_or_create(
                pk=pk,
                defaults={
                    'lookup_type_id': lt,
                    'name': name,
                    'description': desc,
                    'sequence': seq,
                    'is_active': True
                }
            )

        # Qualification Types
        qual_types = [
            (1180, 118, 'High School', 'High school diploma', 10),
            (1181, 118, 'Bachelor', "Bachelor's degree", 20),
            (1182, 118, 'Master', "Master's degree", 30),
            (1183, 118, 'Doctorate', 'Doctorate/PhD degree', 40),
            (1184, 118, 'Diploma', 'Diploma or associate degree', 50),
            (1185, 118, 'Certificate', 'Certificate program', 60),
            (1186, 118, 'Professional Certification', 'Professional certification', 70),
        ]

        for pk, lt, name, desc, seq in qual_types:
            LookupValue.objects.update_or_create(
                pk=pk,
                defaults={
                    'lookup_type_id': lt,
                    'name': name,
                    'description': desc,
                    'sequence': seq,
                    'is_active': True
                }
            )

        # Qualification Titles
        qual_titles = [
            (1190, 119, 'Computer Science', '', 10),
            (1191, 119, 'Engineering', '', 20),
            (1192, 119, 'Business Administration', '', 30),
            (1193, 119, 'Accounting', '', 40),
            (1194, 119, 'Medicine', '', 50),
            (1195, 119, 'Law', '', 60),
        ]

        for pk, lt, name, desc, seq in qual_titles:
            LookupValue.objects.update_or_create(
                pk=pk,
                defaults={
                    'lookup_type_id': lt,
                    'name': name,
                    'description': desc,
                    'sequence': seq,
                    'is_active': True
                }
            )

        # Qualification Statuses
        qual_statuses = [
            (1200, 120, 'In Progress', 'Currently pursuing qualification', 10),
            (1201, 120, 'Completed', 'Qualification completed', 20),
            (1202, 120, 'Deferred', 'Qualification deferred/postponed', 30),
            (1203, 120, 'Withdrawn', 'Withdrawn from qualification', 40),
        ]

        for pk, lt, name, desc, seq in qual_statuses:
            LookupValue.objects.update_or_create(
                pk=pk,
                defaults={
                    'lookup_type_id': lt,
                    'name': name,
                    'description': desc,
                    'sequence': seq,
                    'is_active': True
                }
            )

        # Tuition Methods
        tuition_methods = [
            (1210, 121, 'Online', 'Online/distance learning', 10),
            (1211, 121, 'In-Person', 'In-person classroom learning', 20),
            (1212, 121, 'Hybrid', 'Mixed online and in-person', 30),
            (1213, 121, 'Correspondence', 'Correspondence learning', 40),
            (1214, 121, 'Self-Study', 'Self-directed learning', 50),
        ]

        for pk, lt, name, desc, seq in tuition_methods:
            LookupValue.objects.update_or_create(
                pk=pk,
                defaults={
                    'lookup_type_id': lt,
                    'name': name,
                    'description': desc,
                    'sequence': seq,
                    'is_active': True
                }
            )

        # Currencies
        currencies = [
            (1220, 122, 'EGP', 'Egyptian Pound', 10),
            (1221, 122, 'USD', 'United States Dollar', 20),
            (1222, 122, 'EUR', 'Euro', 30),
            (1223, 122, 'GBP', 'British Pound', 40),
            (1224, 122, 'SAR', 'Saudi Riyal', 50),
            (1225, 122, 'AED', 'UAE Dirham', 60),
        ]

        for pk, lt, name, desc, seq in currencies:
            LookupValue.objects.update_or_create(
                pk=pk,
                defaults={
                    'lookup_type_id': lt,
                    'name': name,
                    'description': desc,
                    'sequence': seq,
                    'is_active': True
                }
            )

        # Competency Categories
        comp_cats = [
            (1230, 123, 'Technical Skills', 'Technical and technology skills', 10),
            (1231, 123, 'Soft Skills', 'Interpersonal and soft skills', 20),
            (1232, 123, 'Leadership', 'Leadership and management skills', 30),
            (1233, 123, 'Communication', 'Communication skills', 40),
            (1234, 123, 'Problem-Solving', 'Problem-solving and analytical skills', 50),
            (1235, 123, 'Domain Knowledge', 'Industry or domain specific knowledge', 60),
        ]

        for pk, lt, name, desc, seq in comp_cats:
            LookupValue.objects.update_or_create(
                pk=pk,
                defaults={
                    'lookup_type_id': lt,
                    'name': name,
                    'description': desc,
                    'sequence': seq,
                    'is_active': True
                }
            )

        # Proficiency Sources
        prof_sources = [
            (1240, 124, 'Appraisal', 'Performance appraisal assessment', 10),
            (1241, 124, 'Course Attended', 'Course or training completion', 20),
            (1242, 124, 'Manager Assessment', "Manager's assessment", 30),
            (1243, 124, 'Self-Assessment', "Employee's self-assessment", 40),
            (1244, 124, 'Certification', 'Professional certification', 50),
            (1245, 124, 'Project Experience', 'Demonstrated through project work', 60),
        ]

        for pk, lt, name, desc, seq in prof_sources:
            LookupValue.objects.update_or_create(
                pk=pk,
                defaults={
                    'lookup_type_id': lt,
                    'name': name,
                    'description': desc,
                    'sequence': seq,
                    'is_active': True
                }
            )

        # Contract Statuses
        contract_statuses = [
            (1500, 125, 'Active', 'Contract is currently active', 10),
            (1501, 125, 'Ended', 'Contract has ended', 20),
        ]

        for pk, lt, name, desc, seq in contract_statuses:
            LookupValue.objects.update_or_create(
                pk=pk,
                defaults={
                    'lookup_type_id': lt,
                    'name': name,
                    'description': desc,
                    'sequence': seq,
                    'is_active': True
                }
            )
            # Contract End Reasons
            contract_end_reasons = [
                (1510, 126, 'Expired', 'Contract reached its end date', 10),
                (1511, 126, 'Terminated', 'Contract terminated before end date', 20),
                (1512, 126, 'Resigned', 'Employee resigned', 30),
            ]

            for pk, lt, name, desc, seq in contract_end_reasons:
                LookupValue.objects.update_or_create(
                    pk=pk,
                    defaults={
                        'lookup_type_id': lt,
                        'name': name,
                        'description': desc,
                        'sequence': seq,
                        'is_active': True
                    }
                )

            # Assignment Action Reasons
            assignment_reasons = [
                (1520, 127, 'Hire', 'Initial hire assignment', 10),
                (1521, 127, 'Promotion', 'Promotion to a new position/grade', 20),
                (1522, 127, 'Internal Transfer', 'Transfer between departments/units', 30),
            ]

            for pk, lt, name, desc, seq in assignment_reasons:
                LookupValue.objects.update_or_create(
                    pk=pk,
                    defaults={
                        'lookup_type_id': lt,
                        'name': name,
                        'description': desc,
                        'sequence': seq,
                        'is_active': True
                    }
                )

            # Assignment Statuses
            assignment_statuses = [
                (1530, 128, 'Active Assignment', 'Assignment is currently active', 10),
                (1531, 128, 'Suspended Assignment', 'Assignment is temporarily suspended', 20),
                (1532, 128, 'Terminated Assignment', 'Assignment has been terminated', 30),
            ]

            for pk, lt, name, desc, seq in assignment_statuses:
                LookupValue.objects.update_or_create(
                    pk=pk,
                    defaults={
                        'lookup_type_id': lt,
                        'name': name,
                        'description': desc,
                        'sequence': seq,
                        'is_active': True
                    }
                )

            # Probation Periods
            probation_periods = [
                (1540, 129, '2 Weeks', '', 10),
                (1541, 129, '1 Month', '', 20),
                (1542, 129, '2 Months', '', 30),
                (1543, 129, '3 Months', '', 40),
            ]

            for pk, lt, name, desc, seq in probation_periods:
                LookupValue.objects.update_or_create(
                    pk=pk,
                    defaults={
                        'lookup_type_id': lt,
                        'name': name,
                        'description': desc,
                        'sequence': seq,
                        'is_active': True
                    }
                )

            # Termination Notice Periods
            notice_periods = [
                (1550, 130, '2 Weeks', '', 10),
                (1551, 130, '1 Month', '', 20),
                (1552, 130, '2 Months', '', 30),
            ]

            for pk, lt, name, desc, seq in notice_periods:
                LookupValue.objects.update_or_create(
                    pk=pk,
                    defaults={
                        'lookup_type_id': lt,
                        'name': name,
                        'description': desc,
                        'sequence': seq,
                        'is_active': True
                    }
                )

            # Awarding Entities
            awarding_entities = [
                (1560, 131, 'University of Oxford', 'University of Oxford', 10),
                (1561, 131, 'University of Cambridge', 'University of Cambridge', 20),
                (1562, 131, 'Massachusetts Institute of Technology', 'MIT', 30),
            ]

            for pk, lt, name, desc, seq in awarding_entities:
                LookupValue.objects.update_or_create(
                    pk=pk,
                    defaults={
                        'lookup_type_id': lt,
                        'name': name,
                        'description': desc,
                        'sequence': seq,
                        'is_active': True
                    }
                )

        self.stdout.write(f'  ✓ Created all lookup values')

    def populate_users(self):
        self.stdout.write(f'\n* Creating Users...')
        # Password: "password123"
        hashed_password = make_password('password123')

        users_data = [
            (1, 'superadmin@lightidea.com', 'Amr Elsayed', '+20 100 111 2222'),
            (2, 'admin1@lightidea.com', 'Omar Hassan', '+20 100 333 4444'),
            (3, 'admin2@lightidea.com', 'Layla Mansour', '+20 100 555 6666'),
            (4, 'manager.egypt@lightidea.com', 'Fatima Ahmed', '+20 100 777 8888'),
            (5, 'manager.levant@lightidea.com', 'Karim Khouri', '+961 70 999 0000')
        ]

        for pk, email, name, phone in users_data:
            UserAccount.objects.update_or_create(
                pk=pk,
                defaults={
                    'email': email,
                    'name': name,
                    'phone_number': phone,
                    'password': hashed_password
                }
            )
        
        # create job role 'admin' and give it to user with pk=1
        admin_role, created = JobRole.objects.get_or_create(
            code='admin',
            defaults={
                'name': 'Administrator',
                'description': 'System Administrator with full access'
            }
        )
        if created:
            self.stdout.write('  ✓ Created Job Role: admin')
        admin_user = UserAccount.objects.get(pk=1)
        UserJobRole.objects.update_or_create(
            user=admin_user,
            job_role=admin_role,
            effective_start_date=str(date.today())
        )
        self.stdout.write('  ✓ Assigned admin role to superadmin user')


        self.stdout.write(f'  ✓ Created {len(users_data)} users')

    def populate_competencies(self):
        self.stdout.write('\n* Creating Competencies...')

        competencies = [
            (1, 'PYTHON', 'Python Development', 1230, 'Competency for Python Development'),
            (2, 'DJANGO', 'Django Framework', 1230, 'Competency for Django Framework'),
            (3, 'SQL', 'SQL & Databases', 1230, 'Competency for SQL & Databases'),
            (4, 'LEADERSHIP', 'Team Leadership', 1230, 'Competency for Team Leadership'),
            (5, 'COMM', 'Effective Communication', 1230, 'Competency for Effective Communication'),
        ]

        for pk, code, name, cat, desc in competencies:
            Competency.objects.update_or_create(
                pk=pk,
                defaults={
                    'name': name,
                    'code': code,
                    'category_id': cat,
                    'description': desc,
                    'status': 'active'
                }
            )

        self.stdout.write(f'  ✓ Created {len(competencies)} competencies')

    def populate_work_structure(self):
        self.stdout.write('\n* Creating Work Structure...')

        # Business Groups (3)
        for i in range(1, 4):
            Organization.objects.update_or_create(
                pk=i,
                defaults={
                    'organization_name': f'Business Group {i}',
                    'organization_type_id': 1031,  # BG
                    'effective_start_date': date(2020, 1, 1),
                    'work_start_time': time(9, 0),
                    'work_end_time': time(17, 0)
                }
            )

        # Locations (3 per BG = 9 total)
        loc_id = 1
        # Map of (city_id, country_id) to rotate through
        city_country_map = [
            (1010, 1000), # Cairo, Egypt
            (1011, 1000), # Alexandria, Egypt
            (1012, 1000), # Giza, Egypt
            (1013, 1001), # Dubai, UAE
            (1014, 1001), # Abu Dhabi, UAE
            (1015, 1002), # Riyadh, Saudi Arabia
        ]

        for bg in range(1, 4):
            for office in range(1, 4):
                city_id, country_id = city_country_map[(loc_id - 1) % len(city_country_map)]
                Location.objects.update_or_create(
                    pk=loc_id,
                    defaults={
                        'business_group_id': bg,
                        'location_name': f'Office {office} for BG {bg}',
                        'description': f'Main office location {office} for Business Group {bg}',
                        'country_id': country_id,
                        'city_id': city_id,
                        'zone': f'Zone {office}',
                        'street': f'{10 * office} Main Street',
                        'building': f'Building {office}',
                        'floor': f'{office}',
                        'office': f'{100 + office}',
                        'po_box': f'PO-{1000 + loc_id}',
                        'effective_from': timezone.now(),
                        'status': 'active'
                    }
                )
                loc_id += 1

        # Business Groups (3)
        for i in range(1, 4):
            loc_id = (i-1) * 3 + 1 
            Organization.objects.update_or_create(
                pk=i,
                defaults={
                    'organization_name': f'Business Group {i}',
                    'organization_type_id': 1031,  # BG
                    'location_id': loc_id,
                    'effective_start_date': date(2020, 1, 1),
                    'work_start_time': time(9, 0),
                    'work_end_time': time(17, 0)
                }
            )

        # Departments (3 per BG = 9 total)
        dept_id = 4
        loc_id = 1
        for bg in range(1, 4):
            for dept in range(1, 4):
                Organization.objects.update_or_create(
                    pk=dept_id,
                    defaults={
                        'organization_name': f'Department {dept} of BG {bg}',
                        'business_group_id': bg,
                        'organization_type_id': 1032,  # DEPT
                        'location_id': loc_id,
                        'effective_start_date': date(2020, 1, 1),
                        'work_start_time': time(9, 0),
                        'work_end_time': time(17, 0)
                    }
                )
                dept_id += 1
                loc_id += 1

        # Grades (3 per BG = 9 total)
        grade_id = 1
        for bg in range(1, 4):
            for seq in range(1, 4):
                Grade.objects.update_or_create(
                    pk=grade_id,
                    defaults={
                        'organization_id': bg,
                        'sequence': seq,
                        'grade_name_id': 1169 + seq,  # 1170, 1171, 1172
                        'effective_from': timezone.now(),
                        'status': 'active'
                    }
                )
                grade_id += 1

        # Jobs (3 per BG = 9 total)
        job_id = 1
        for bg in range(1, 4):
            for j in range(1, 4):
                # j=1: Engineer (1065), j=2: Manager (1066), j=3: Specialist (1062)
                job_type = "ENGINEER" if j == 1 else "MANAGER" if j == 2 else "SPECIALIST"
                job_title_lookup_id = 1065 if j == 1 else 1066 if j == 2 else 1062
                
                # Assign different categories based on job type
                # 1051: IT, 1054: Operations, 1052: HR
                job_cat_id = 1051 if j == 1 else 1054 if j == 2 else 1052
                
                responsibilities = []
                if j == 1:
                    responsibilities = [
                        "Design and develop software solutions",
                        "Write clean, maintainable code",
                        "Participate in code reviews",
                        "Debug and resolve technical issues"
                    ]
                elif j == 2:
                    responsibilities = [
                        "Define product vision and strategy",
                        "Manage product roadmap",
                        "Work with stakeholders",
                        "Analyze market trends"
                    ]
                else:
                    responsibilities = [
                        "Manage recruitment processes",
                        "Handle employee relations",
                        "Maintain HR records",
                        "Support performance management"
                    ]

                job, created = Job.objects.update_or_create(
                    pk=job_id,
                    defaults={
                        'code': f'BG{bg}-JOB-{j}',
                        'business_group_id': bg,
                        'job_title_id': job_title_lookup_id,
                        'job_category_id': job_cat_id,
                        'job_description': f'Standard {job_type} role for {["IT", "Operations", "HR"][j-1]} department',
                        'responsibilities': responsibilities,
                        'effective_start_date': date(2020, 1, 1)
                    }
                )

                # Populate M2M relationships
                # 1. Grades (Assign grades specific to the Business Group)
                # BG1: 1-3, BG2: 4-6, BG3: 7-9
                start_grade = (bg - 1) * 3 + 1
                job.grades.add(start_grade, start_grade + 1, start_grade + 2)

                # 2. Competencies & Qualifications based on Job Type
                if j == 1:  # Software Engineer
                    # Python (Advanced), SQL (Intermediate)
                    JobCompetencyRequirement.objects.get_or_create(
                        job=job, competency_id=1, defaults={'proficiency_level_id': 1092}
                    )
                    JobCompetencyRequirement.objects.get_or_create(
                        job=job, competency_id=3, defaults={'proficiency_level_id': 1091}
                    )
                    # Bachelor in CS
                    JobQualificationRequirement.objects.get_or_create(
                        job=job, qualification_type_id=1181, qualification_title_id=1190
                    )
                elif j == 2:  # Product Manager
                    # Leadership (Advanced), Communication (Advanced)
                    JobCompetencyRequirement.objects.get_or_create(
                        job=job, competency_id=4, defaults={'proficiency_level_id': 1092}
                    )
                    JobCompetencyRequirement.objects.get_or_create(
                        job=job, competency_id=5, defaults={'proficiency_level_id': 1092}
                    )
                    # Master in Business
                    JobQualificationRequirement.objects.get_or_create(
                        job=job, qualification_type_id=1182, qualification_title_id=1192
                    )
                else:  # HR Specialist
                    # Communication (Advanced)
                    JobCompetencyRequirement.objects.get_or_create(
                        job=job, competency_id=5, defaults={'proficiency_level_id': 1092}
                    )
                    # Bachelor in Business
                    JobQualificationRequirement.objects.get_or_create(
                        job=job, qualification_type_id=1181, qualification_title_id=1192
                    )

                job_id += 1

        # Positions (3 per BG = 9 total)
        pos_id = 1
        dept_id = 4
        loc_id = 1
        grade_id = 1
        job_id = 1
        for bg in range(1, 4):
            for p in range(1, 4):
                # 1125: Senior Software Engineer, 1126: Product Manager, 1122: HR Specialist
                pos_title_lookup_id = 1125 if p == 1 else 1126 if p == 2 else 1122

                position, created = Position.objects.update_or_create(
                    pk=pos_id,
                    defaults={
                        'code': f'POS-{bg}-{p}',
                        'organization_id': dept_id,
                        'job_id': job_id,
                        'location_id': loc_id,
                        'grade_id': grade_id,
                        'position_title_id': pos_title_lookup_id,
                        'position_type_id': 1130,
                        'position_status_id': 1140,
                        'payroll_id': 1150,  # Monthly
                        'salary_basis_id': 1160,  # Monthly basis
                        'position_sync': False,
                        'full_time_equivalent': Decimal('1.00'),
                        'head_count': 1,
                        'effective_start_date': date(2020, 1, 1)
                    }
                )

                # Populate M2M relationships
                if p == 1:  # Senior Software Engineer Position
                    # Django (Intermediate)
                    PositionCompetencyRequirement.objects.get_or_create(
                        position=position, competency_id=2, defaults={'proficiency_level_id': 1091}
                    )
                    # Engineering Degree (Optional)
                    PositionQualificationRequirement.objects.get_or_create(
                        position=position, qualification_type_id=1181, qualification_title_id=1191
                    )
                elif p == 2:  # Product Manager Position
                    # Communication (Intermediate)
                    PositionCompetencyRequirement.objects.get_or_create(
                        position=position, competency_id=5, defaults={'proficiency_level_id': 1091}
                    )
                    # Business Degree (Optional)
                    PositionQualificationRequirement.objects.get_or_create(
                        position=position, qualification_type_id=1181, qualification_title_id=1192
                    )
                else:  # HR Specialist Position
                    # Leadership (Intermediate)
                    PositionCompetencyRequirement.objects.get_or_create(
                        position=position, competency_id=4, defaults={'proficiency_level_id': 1091}
                    )
                    # Law Degree (Optional)
                    PositionQualificationRequirement.objects.get_or_create(
                        position=position, qualification_type_id=1181, qualification_title_id=1195
                    )

                pos_id += 1
                dept_id += 1
                loc_id += 1
                grade_id += 1
                job_id += 1

        self.stdout.write('  ✓ Created work structure')

    def populate_persons_and_employees(self):
        self.stdout.write('\n* Creating Persons and Employees...')

        # Person Type
        PersonType.objects.update_or_create(
            pk=1,
            defaults={
                'code': 'PERM_EMP',
                'name': 'Permanent Employee',
                'base_type': 'EMP',
                'is_active': True
            }
        )

        # Applicant Type
        PersonType.objects.update_or_create(
            pk=2,
            defaults={
                'code': 'EXT_APL',
                'name': 'External Applicant',
                'base_type': 'APL',
                'is_active': True
            }
        )

        # Contingent Worker Type
        PersonType.objects.update_or_create(
            pk=3,
            defaults={
                'code': 'AGENCY_CWK',
                'name': 'Agency Worker',
                'base_type': 'CWK',
                'is_active': True
            }
        )

        # Contact Type
        PersonType.objects.update_or_create(
            pk=4,
            defaults={
                'code': 'EMERG_CON',
                'name': 'Emergency Contact',
                'base_type': 'CON',
                'is_active': True
            }
        )

        persons_data = [
            (1, 'Ahmed', 'Mohamed', 'Ali', 'أحمد', 'محمد', 'علي', 'Mr', 'Male', 'ahmed.ali@test.com', 'EGY001', 'A+', 'Islam'),
            (2, 'Fatima', 'Omar', 'Hassan', 'فاطمة', 'عمر', 'حسن', 'Ms', 'Female', 'fatima.hassan@test.com', 'EGY002', 'B+', 'Islam'),
            (3, 'Mahmoud', 'Ibrahim', 'Mostafa', 'محمود', 'إبراهيم', 'مصطفى', 'Mr', 'Male', 'mahmoud.mostafa@test.com', 'EGY003', 'O+', 'Islam'),
            (4, 'Sarah', 'Khaled', 'Youssef', 'سارة', 'خالد', 'يوسف', 'Mrs', 'Female', 'sarah.youssef@test.com', 'EGY004', 'AB+', 'Christianity'),
            (5, 'Omar', 'Amr', 'Hussein', 'عمر', 'عمرو', 'حسين', 'Mr', 'Male', 'omar.hussein@test.com', 'EGY005', 'A-', 'Islam'),
        ]

        for pk, first, middle, last, first_ar, middle_ar, last_ar, title, gender, email, national_id, blood_type, religion in persons_data:
            # Create/Update Employee and Person together
            # Note: update_or_create doesn't work with proxied fields because Django validates field names.
            # We must handle update/create manually.
            
            # Try to find existing employee
            try:
                employee = Employee.objects.get(pk=pk)
                # Update existing
                employee.first_name = first
                employee.middle_name = middle
                employee.last_name = last
                employee.first_name_arabic = first_ar
                employee.middle_name_arabic = middle_ar
                employee.last_name_arabic = last_ar
                employee.title = title
                employee.gender = gender
                employee.email_address = email
                employee.national_id = national_id
                employee.date_of_birth = date(1990, 1, 1)
                employee.nationality = 'Egyptian'
                employee.marital_status = 'Married' if pk % 2 == 0 else 'Single'
                employee.religion = religion
                employee.blood_type = blood_type

                employee.employee_number = f'E{99 + pk}'
                employee.employee_type_id = 1
                employee.hire_date = date(2020, 1, 1)
                employee.effective_start_date = date(2020, 1, 1)
                employee.save()
            except Employee.DoesNotExist:
                # Create new using Manager.create (which handles parent creation)
                # We pass 'id': pk to ensure Person gets the correct ID
                Employee.objects.create(
                    # Person fields
                    id=pk,
                    first_name=first,
                    middle_name=middle,
                    last_name=last,
                    first_name_arabic=first_ar,
                    middle_name_arabic=middle_ar,
                    last_name_arabic=last_ar,
                    title=title,
                    gender=gender,
                    email_address=email,
                    national_id=national_id,
                    date_of_birth=date(1990, 1, 1),
                    nationality='Egyptian',
                    marital_status='Married' if pk % 2 == 0 else 'Single',
                    religion=religion,
                    blood_type=blood_type,

                    # Employee fields
                    pk=pk,
                    employee_number=f'E{99 + pk}',
                    employee_type_id=1,
                    hire_date=date(2020, 1, 1),
                    effective_start_date=date(2020, 1, 1)
                )

        self.stdout.write(f'  ✓ Created {len(persons_data)} persons and employees')

    def populate_addresses(self):
        self.stdout.write('\n* Creating Addresses...')

        addresses_data = [
            (1, 1, 1000, 1010, '123 Main St', 'Apt 4B', '', '', '12', '4B', True),
            (2, 2, 1000, 1010, '456 Oak Ave', '', '', '', '34', '', False),
            (3, 3, 1000, 1010, '789 Pine Rd', 'Suite 5', '', '', '56', '5', True),
            (4, 4, 1000, 1010, '321 Maple St', '', '', '', '78', '', False),
            (5, 5, 1000, 1010, '654 Cedar Blvd', 'Unit 2A', '', '', '90', '2A', True),
        ]
        for pk, person, country, city, street, line1, line2, line3, building, apartment, is_primary in addresses_data:
            Address.objects.update_or_create(
                pk=pk,
                defaults={
                    'person_id': person,
                    'address_type_id': 1020,  # HOME
                    'country_id': country,
                    'city_id': city,
                    'street': street,
                    'address_line_1': line1,
                    'address_line_2': line2,
                    'address_line_3': line3,
                    'building_number': building,
                    'apartment_number': apartment,
                    'is_primary': is_primary,
                    'status': 'active',
                }
            )

        self.stdout.write(f'  ✓ Created {len(addresses_data)} addresses')

    def populate_assignments(self):
        self.stdout.write('\n* Creating Assignments...')

        assignments_data = [
            (1, 1, 1, 4, 1, 1, 1),  # Person 1, BG 1, Dept 4, Job 1, Pos 1, Grade 1
            (2, 2, 2, 7, 4, 4, 4),  # Person 2, BG 2, Dept 7, Job 4, Pos 4, Grade 4
            (3, 3, 3, 10, 7, 7, 7),  # Person 3, BG 3, Dept 10, Job 7, Pos 7, Grade 7
            (4, 4, 1, 4, 1, 1, 1),  # Person 4, BG 1, Dept 4, Job 1, Pos 1, Grade 1
            (5, 5, 2, 7, 4, 4, 4),  # Person 5, BG 2, Dept 7, Job 4, Pos 4, Grade 4
        ]

        for pk, person, bg, dept, job, pos, grade in assignments_data:
            Assignment.objects.update_or_create(
                pk=pk,
                defaults={
                    'person_id': person,
                    'business_group_id': bg,
                    'assignment_no': f'ASG-{99 + pk}',
                    'department_id': dept,
                    'job_id': job,
                    'position_id': pos,
                    'grade_id': grade,
                    'payroll_id': 1150,  # Monthly
                    'salary_basis_id': 1160,  # Monthly basis
                    'line_manager_id': None,  # No manager for now
                    'assignment_action_reason_id': 1520,  # Hire
                    'primary_assignment': True,
                    'contract_id': None,  # Will be linked later after contracts are created
                    'assignment_status_id': 1530,  # Active
                    'project_manager_id': None,
                    'probation_period_start': date(2020, 1, 1),
                    'probation_period_id': 1540,  # 3 months
                    'probation_period_end': date(2020, 4, 1),
                    'effective_start_date': date(2020, 1, 1)
                }
            )

        self.stdout.write(f'  ✓ Created {len(assignments_data)} assignments')

    def populate_grade_rates(self):
        self.stdout.write('\n* Creating Grade Rates...')

        # Grade Rate Types
        rate_types = [
            ('BASIC', 'Basic Salary'),
            ('HOUSING', 'Housing Allowance'),
            ('TRANS', 'Transportation Allowance'),
            ('OVERTIME', 'Overtime Rate'),
        ]

        created_types = {}
        for code, desc in rate_types:
            rt, _ = GradeRateType.objects.update_or_create(
                code=code,
                defaults={'description': desc}
            )
            created_types[code] = rt

        # Grade Rates
        # Grades 1-9 created in populate_work_structure
        rates_data = []
        today = date(2020, 1, 1)

        # Junior Grades (1-3)
        for g_id in range(1, 4):
            # Basic Salary (Range)
            rates_data.append({
                'grade_id': g_id,
                'rate_type': created_types['BASIC'],
                'min_amount': Decimal('5000.00'),
                'max_amount': Decimal('10000.00'),
                'fixed_amount': None,
            })
            # Housing (Fixed)
            rates_data.append({
                'grade_id': g_id,
                'rate_type': created_types['HOUSING'],
                'min_amount': None,
                'max_amount': None,
                'fixed_amount': Decimal('1000.00'),
            })

        # Mid Grades (4-6)
        for g_id in range(4, 7):
            # Basic Salary (Range)
            rates_data.append({
                'grade_id': g_id,
                'rate_type': created_types['BASIC'],
                'min_amount': Decimal('12000.00'),
                'max_amount': Decimal('20000.00'),
                'fixed_amount': None,
            })
            # Housing (Fixed)
            rates_data.append({
                'grade_id': g_id,
                'rate_type': created_types['HOUSING'],
                'min_amount': None,
                'max_amount': None,
                'fixed_amount': Decimal('2000.00'),
            })
             # Transportation (Fixed)
            rates_data.append({
                'grade_id': g_id,
                'rate_type': created_types['TRANS'],
                'min_amount': None,
                'max_amount': None,
                'fixed_amount': Decimal('1500.00'),
            })

        # Senior Grades (7-9)
        for g_id in range(7, 10):
            # Basic Salary (Range)
            rates_data.append({
                'grade_id': g_id,
                'rate_type': created_types['BASIC'],
                'min_amount': Decimal('25000.00'),
                'max_amount': Decimal('50000.00'),
                'fixed_amount': None,
            })
            # Housing (Fixed)
            rates_data.append({
                'grade_id': g_id,
                'rate_type': created_types['HOUSING'],
                'min_amount': None,
                'max_amount': None,
                'fixed_amount': Decimal('5000.00'),
            })
             # Transportation (Fixed)
            rates_data.append({
                'grade_id': g_id,
                'rate_type': created_types['TRANS'],
                'min_amount': None,
                'max_amount': None,
                'fixed_amount': Decimal('3000.00'),
            })

        for rate in rates_data:
            GradeRate.objects.update_or_create(
                grade_id=rate['grade_id'],
                rate_type=rate['rate_type'],
                effective_start_date=today,
                defaults={
                    'min_amount': rate['min_amount'],
                    'max_amount': rate['max_amount'],
                    'fixed_amount': rate['fixed_amount'],
                    'currency_id': 1220,  # EGP
                }
            )

        self.stdout.write(f'  ✓ Created {len(rates_data)} grade rates')

    def populate_contracts(self):
        self.stdout.write('\n* Creating Contracts...')

        for pk in range(1, 6):
            Contract.objects.update_or_create(
                pk=pk,
                defaults={
                    'person_id': pk,
                    'contract_reference': f'CON-{99 + pk}',
                    'contract_status_id': 1500,  # Active
                    'contract_end_reason_id': None,
                    'description': f'Employment contract for employee {pk}',
                    'contract_duration': Decimal('1.00'),
                    'contract_period': 'Years',
                    'contract_start_date': date(2020, 1, 1),
                    'contract_end_date': date(2021, 1, 1),
                    'contractual_job_position': 'Software Engineer',
                    'extension_duration': None,
                    'extension_period': None,
                    'extension_start_date': None,
                    'extension_end_date': None,
                    'basic_salary': Decimal('10000.00'),
                    'effective_start_date': date(2020, 1, 1)
                }
            )

        self.stdout.write(f'  ✓ Created 5 contracts')

    def populate_qualifications(self):
        self.stdout.write('\n* Creating Qualifications...')

        qualifications_data = [
            # person_id, type_id, title_id, status_id, grade, awarding_entity_id, start_date, end_date
            (1, 1181, 1190, 1201, '3.8 GPA', 1560, date(2015, 9, 1), date(2019, 6, 30)),
            (2, 1182, 1192, 1200, None, 1561, date(2020, 9, 1), None),
            (3, 1181, 1193, 1201, 'Good', 1560, date(2016, 9, 1), date(2020, 6, 30)),
            (4, 1181, 1191, 1201, 'Very Good', 1562, date(2014, 9, 1), date(2018, 6, 30)),
            (5, 1184, 1190, 1201, 'Pass', 1560, date(2018, 9, 1), date(2020, 6, 30)),
        ]

        for i, (pid, q_type, q_title, status, grade, entity, start, end) in enumerate(qualifications_data, 1):
            Qualification.objects.update_or_create(
                pk=i,
                defaults={
                    'person_id': pid,
                    'qualification_type_id': q_type,
                    'qualification_title_id': q_title,
                    'qualification_status_id': status,
                    'grade': grade or '',
                    'awarding_entity_id': entity,
                    'study_start_date': start,
                    'study_end_date': end,
                    'awarded_date': end if status == 1201 else None,
                    'projected_completion_date': date(2022, 6, 30) if status == 1200 else None,
                    'tuition_method_id': 1211, # In-Person
                    'tuition_fees': Decimal('10000.00'),
                    'tuition_fees_currency_id': 1220, # EGP
                    'effective_start_date': start,
                    'effective_end_date': None
                }
            )

        self.stdout.write(f'  ✓ Created {len(qualifications_data)} qualifications')

    def populate_contacts(self):
        self.stdout.write('\n* Creating Contacts...')

        # Create 5 contact persons (IDs 6-10)
        contacts_data = [
            (6, 'Father', 'Ahmed', 'Ali', 1, 'Father', 'Retired'),
            (7, 'Spouse', 'Fatima', 'Omar', 2, 'Spouse', 'Teacher'),
            (8, 'Brother', 'Mahmoud', 'Ibrahim', 3, 'Brother', 'Engineer'),
            (9, 'Sister', 'Sarah', 'Khaled', 4, 'Sister', 'Doctor'),
            (10, 'Mother', 'Omar', 'Amr', 5, 'Mother', 'Housewife'),
        ]

        for pk, first, middle, last, emp_id, relation, job in contacts_data:
            # Create Contact via Manager (which handles Person creation)
            # We assume ChildModelManagerMixin handles separating Person fields
            Contact.objects.create(
                # Person fields
                first_name=first,
                middle_name=middle,
                last_name=last,
                gender='Male' if relation in ['Father', 'Brother'] else 'Female',
                email_address=f'contact{pk}@test.com',
                national_id=f'CON{pk}',
                date_of_birth=date(1960, 1, 1),
                nationality='Egyptian',
                marital_status='Married',
                religion='Islam',
                
                # Contact fields
                contact_type_id=4, # Emergency Contact
                contact_number=f'CN-{pk}',
                organization_name='External',
                job_title=job,
                relationship_to_company='Family',
                emergency_for_employee_id=emp_id,
                emergency_relationship=relation,
                is_primary_contact=True,
                effective_start_date=date(2020, 1, 1),
                effective_end_date=None,
            )

        self.stdout.write(f'  ✓ Created {len(contacts_data)} contacts')

    def populate_competency_proficiencies(self):
        self.stdout.write('\n* Creating Competency Proficiencies...')

        proficiencies_data = [
            (1, 1, 1093, 1243), # Person 1, Python, Expert, Self-Assessment
            (1, 2, 1092, 1245), # Person 1, Django, Advanced, Project Exp
            (2, 4, 1093, 1242), # Person 2, Leadership, Expert, Manager Assessment
            (2, 5, 1092, 1240), # Person 2, Comm, Advanced, Appraisal
            (3, 3, 1091, 1244), # Person 3, SQL, Intermediate, Certification
            (4, 1, 1091, 1241), # Person 4, Python, Intermediate, Course
            (5, 5, 1091, 1243), # Person 5, Comm, Intermediate, Self-Assessment
        ]
        
        count = 0
        for pid, comp_id, level_id, source_id in proficiencies_data:
            CompetencyProficiency.objects.update_or_create(
                person_id=pid,
                competency_id=comp_id,
                effective_start_date=date(2020, 1, 1),
                defaults={
                    'proficiency_level_id': level_id,
                    'proficiency_source_id': source_id,
                    'effective_end_date': None
                }
            )
            count += 1

        self.stdout.write(f'  ✓ Created {count} competency proficiencies')

    def handle(self, *args, **options):
        # Flush existing data
        self.stdout.write(self.style.WARNING('⚠️  Removing all existing data...'))
        call_command('flush', '--noinput')
        self.stdout.write(self.style.SUCCESS('✓ Database flushed successfully'))

        self.stdout.write('Generating fixture data...')

        self.populate_lookup_types()
        self.populate_lookup_values()
        self.populate_users()
        self.populate_competencies()
        self.populate_work_structure()
        self.populate_grade_rates()
        self.populate_persons_and_employees()
        self.populate_addresses()
        self.populate_assignments()
        self.populate_contracts()
        self.populate_qualifications()
        self.populate_contacts()
        self.populate_competency_proficiencies()

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('✅ All fixture data generated successfully!'))
        self.stdout.write('=' * 60)