from django.db import migrations

def create_base_types(apps, schema_editor):
    PersonType = apps.get_model('person', 'PersonType')
    
    # Use update_or_create to be idempotent
    PersonType.objects.update_or_create(
        code='APL',
        defaults={'name': 'Applicant', 'base_type': 'APL', 'is_active': True}
    )
    PersonType.objects.update_or_create(
        code='EMP',
        defaults={'name': 'Employee', 'base_type': 'EMP', 'is_active': True}
    )
    PersonType.objects.update_or_create(
        code='CWK',
        defaults={'name': 'Contingent Worker', 'base_type': 'CWK', 'is_active': True}
    )
    PersonType.objects.update_or_create(
        code='CON',
        defaults={'name': 'Contact', 'base_type': 'CON', 'is_active': True}
    )

def remove_base_types(apps, schema_editor):
    PersonType = apps.get_model('person', 'PersonType')
    PersonType.objects.filter(code__in=['APL', 'EMP', 'CWK', 'CON']).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('person', '0002_initial'),
    ]

    operations = [
        migrations.RunPython(create_base_types, remove_base_types),
    ]
