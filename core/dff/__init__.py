"""
DFF (Descriptive Flexfield) - Core Infrastructure

Provides reusable DFF pattern for business-configurable custom fields.

Exports:
    - DFFMixin: Adds 30 DFF columns (20 text + 5 date + 5 number)
    - DFFConfigBase: Abstract base for DFF configuration models
    - DFFService: Generic service for DFF CRUD operations

Usage:
    from core.dff import DFFMixin, DFFConfigBase, DFFService

    # In your model
    class MyModel(DFFMixin, models.Model):
        code = models.CharField(max_length=50)
        name = models.CharField(max_length=128)

    # DFF config
    class MyModelDFFConfig(DFFConfigBase):
        my_model = models.ForeignKey(MyModel, on_delete=models.CASCADE)

        class Meta(DFFConfigBase.Meta):
            db_table = 'my_model_dff_config'
            unique_together = [
                ('my_model', 'field_name'),
                ('my_model', 'column_name'),
            ]

    # Use service
    DFFService.set_dff_data(instance, MyModelDFFConfig, {'field1': 'value1'}, 'code')
"""

from .models import DFFMixin, DFFConfigBase
from .services import DFFService

__all__ = ['DFFMixin', 'DFFConfigBase', 'DFFService']

