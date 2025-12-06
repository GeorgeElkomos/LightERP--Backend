from django.test import TestCase
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import date

# from .models import (
#     AssetCategory, AssetLocation, FixedAsset,
#     DepreciationSchedule, DepreciationRun
# )
# from Finance.core.models import Currency


class AssetCategoryTestCase(TestCase):
    """Tests for AssetCategory model."""
    
    def setUp(self):
        pass
    
    # def test_create_category(self):
    #     """Test creating an asset category."""
    #     category = AssetCategory.objects.create(
    #         code='VEHICLE',
    #         name='Vehicles',
    #         default_depreciation_method='STRAIGHT_LINE',
    #         default_useful_life_years=5
    #     )
    #     self.assertEqual(category.code, 'VEHICLE')


class FixedAssetTestCase(TestCase):
    """Tests for FixedAsset model."""
    
    def setUp(self):
        pass
    
    # def test_straight_line_depreciation(self):
    #     """Test straight line depreciation calculation."""
    #     # Create asset with known values
    #     # acquisition_cost = 12000, salvage_value = 0, useful_life = 5 years
    #     # Expected monthly depreciation = 12000 / 60 = 200
    #     pass
    
    # def test_declining_balance_depreciation(self):
    #     """Test declining balance depreciation calculation."""
    #     pass
    
    # def test_asset_lifecycle(self):
    #     """Test asset lifecycle: draft -> active -> disposed."""
    #     pass


class DepreciationRunTestCase(TestCase):
    """Tests for depreciation run."""
    
    def setUp(self):
        pass
    
    # def test_run_depreciation(self):
    #     """Test running depreciation for a period."""
    #     pass
    
    # def test_cannot_run_depreciation_twice(self):
    #     """Test that depreciation cannot be run twice for same period."""
    #     pass
