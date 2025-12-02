"""
Comprehensive test cases for Segment API endpoints.
Tests all CRUD operations, custom methods, and complex scenarios.
"""
from django.test import TestCase, Client
from django.urls import reverse
from rest_framework import status
import json

from .models import XX_SegmentType, XX_Segment


class SegmentTypeAPITestCase(TestCase):
    """Test cases for XX_SegmentType API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Create test segment types
        self.entity_type = XX_SegmentType.objects.create(
            segment_name="Entity",
            is_required=True,
            has_hierarchy=True,
            length=50,
            display_order=1,
            description="Cost center entities",
            is_active=True
        )
        
        self.account_type = XX_SegmentType.objects.create(
            segment_name="Account",
            is_required=True,
            has_hierarchy=False,
            length=50,
            display_order=2,
            description="Account codes",
            is_active=True
        )
        
        self.project_type = XX_SegmentType.objects.create(
            segment_name="Project",
            is_required=False,
            has_hierarchy=True,
            length=50,
            display_order=3,
            description="Project codes",
            is_active=False  # Inactive
        )
    
    def test_list_segment_types(self):
        """Test GET /segment-types/ - List all segment types"""
        response = self.client.get('/gl/segment-types/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 3)
        self.assertEqual(data[0]['segment_name'], 'Entity')
    
    def test_list_segment_types_filter_active(self):
        """Test filtering segment types by active status"""
        # Filter active only
        response = self.client.get('/gl/segment-types/?is_active=true')
        data = response.json()
        self.assertEqual(len(data), 2)
        
        # Filter inactive only
        response = self.client.get('/gl/segment-types/?is_active=false')
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['segment_name'], 'Project')
    
    def test_list_segment_types_filter_hierarchy(self):
        """Test filtering segment types by hierarchy support"""
        response = self.client.get('/gl/segment-types/?has_hierarchy=true')
        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertIn(data[0]['segment_name'], ['Entity', 'Project'])
    
    def test_create_segment_type(self):
        """Test POST /segment-types/ - Create new segment type"""
        new_data = {
            'segment_name': 'Department',
            'is_required': True,
            'has_hierarchy': False,
            'length': 10,
            'display_order': 4,
            'description': 'Department codes',
            'is_active': True
        }
        
        response = self.client.post(
            '/gl/segment-types/',
            data=json.dumps(new_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data['segment_name'], 'Department')
        self.assertEqual(data['length'], 10)
        self.assertTrue('id' in data)
        
        # Verify it was created in database
        self.assertTrue(XX_SegmentType.objects.filter(segment_name='Department').exists())
    
    def test_create_segment_type_duplicate_name(self):
        """Test creating segment type with duplicate name fails"""
        duplicate_data = {
            'segment_name': 'Entity',  # Already exists
            'is_required': True,
            'has_hierarchy': False,
            'length': 10,
            'display_order': 5
        }
        
        response = self.client.post(
            '/gl/segment-types/',
            data=json.dumps(duplicate_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_get_segment_type_detail(self):
        """Test GET /segment-types/{id}/ - Get specific segment type"""
        response = self.client.get(f'/gl/segment-types/{self.entity_type.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['segment_name'], 'Entity')
        self.assertTrue(data['has_hierarchy'])
        self.assertTrue('can_delete' in data)
    
    def test_update_segment_type_patch(self):
        """Test PATCH /segment-types/{id}/ - Partial update"""
        update_data = {
            'display_order': 10,
            'description': 'Updated description'
        }
        
        response = self.client.patch(
            f'/gl/segment-types/{self.entity_type.id}/',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['display_order'], 10)
        self.assertEqual(data['description'], 'Updated description')
        
        # Verify in database
        self.entity_type.refresh_from_db()
        self.assertEqual(self.entity_type.display_order, 10)
    
    def test_update_segment_type_put(self):
        """Test PUT /segment-types/{id}/ - Full update"""
        update_data = {
            'segment_name': 'Entity',
            'is_required': False,  # Changed
            'has_hierarchy': True,
            'length': 50,
            'display_order': 1,
            'description': 'Fully updated',
            'is_active': True
        }
        
        response = self.client.put(
            f'/gl/segment-types/{self.entity_type.id}/',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertFalse(data['is_required'])
        self.assertEqual(data['description'], 'Fully updated')
    
    def test_delete_segment_type_success(self):
        """Test DELETE /segment-types/{id}/ - Successful deletion"""
        # Create a new type with no values
        temp_type = XX_SegmentType.objects.create(
            segment_name='TempType',
            is_required=False,
            has_hierarchy=False,
            length=10,
            display_order=99
        )
        
        response = self.client.delete(f'/gl/segment-types/{temp_type.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(XX_SegmentType.objects.filter(id=temp_type.id).exists())
    
    def test_segment_type_can_delete(self):
        """Test GET /segment-types/{id}/can-delete/"""
        response = self.client.get(f'/gl/segment-types/{self.entity_type.id}/can-delete/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue('can_delete' in data)
        self.assertTrue(isinstance(data['can_delete'], bool))
    
    def test_segment_type_toggle_active(self):
        """Test POST /segment-types/{id}/toggle-active/"""
        original_status = self.entity_type.is_active
        
        response = self.client.post(f'/gl/segment-types/{self.entity_type.id}/toggle-active/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['is_active'], not original_status)
        
        # Verify in database
        self.entity_type.refresh_from_db()
        self.assertEqual(self.entity_type.is_active, not original_status)
    
    def test_segment_type_is_used_in_transactions(self):
        """Test GET /segment-types/{id}/is-used-in-transactions/"""
        response = self.client.get(
            f'/gl/segment-types/{self.entity_type.id}/is-used-in-transactions/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue('is_used' in data)
        self.assertTrue('usage_details' in data)
        self.assertFalse(data['is_used'])  # No transactions yet


class SegmentAPITestCase(TestCase):
    """Test cases for XX_Segment API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Create segment type
        self.entity_type = XX_SegmentType.objects.create(
            segment_name="Entity",
            is_required=True,
            has_hierarchy=True,
            length=50,
            display_order=1
        )
        
        # Create hierarchical segments
        self.parent_segment = XX_Segment.objects.create(
            segment_type=self.entity_type,
            code="100",
            alias="Main Office",
            node_type="parent",
            is_active=True
        )
        
        self.child_segment = XX_Segment.objects.create(
            segment_type=self.entity_type,
            code="110",
            parent_code="100",
            alias="Department A",
            node_type="sub_parent",
            is_active=True
        )
        
        self.grandchild_segment = XX_Segment.objects.create(
            segment_type=self.entity_type,
            code="111",
            parent_code="110",
            alias="Team 1",
            node_type="child",
            is_active=True
        )
        
        # Create another parent
        self.parent_segment_2 = XX_Segment.objects.create(
            segment_type=self.entity_type,
            code="200",
            alias="Branch Office",
            node_type="parent",
            is_active=False  # Inactive
        )
    
    def test_list_segments(self):
        """Test GET /segments/ - List all segments"""
        response = self.client.get('/gl/segments/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 4)
    
    def test_list_segments_filter_by_type(self):
        """Test filtering segments by segment type"""
        response = self.client.get(f'/gl/segments/?segment_type={self.entity_type.id}')
        
        data = response.json()
        self.assertEqual(len(data), 4)
        for segment in data:
            self.assertEqual(segment['segment_type'], self.entity_type.id)
    
    def test_list_segments_filter_by_active(self):
        """Test filtering segments by active status"""
        response = self.client.get('/gl/segments/?is_active=true')
        data = response.json()
        self.assertEqual(len(data), 3)
        
        response = self.client.get('/gl/segments/?is_active=false')
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['code'], '200')
    
    def test_list_segments_filter_by_node_type(self):
        """Test filtering segments by node type"""
        response = self.client.get('/gl/segments/?node_type=parent')
        data = response.json()
        self.assertEqual(len(data), 2)
        
        response = self.client.get('/gl/segments/?node_type=child')
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['code'], '111')
    
    def test_list_segments_filter_by_parent_code(self):
        """Test filtering segments by parent code"""
        response = self.client.get('/gl/segments/?parent_code=100')
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['code'], '110')
    
    def test_create_segment(self):
        """Test POST /segments/ - Create new segment"""
        new_data = {
            'segment_type': self.entity_type.id,
            'code': '300',
            'alias': 'New Branch',
            'node_type': 'parent',
            'is_active': True
        }
        
        response = self.client.post(
            '/gl/segments/',
            data=json.dumps(new_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data['code'], '300')
        self.assertEqual(data['alias'], 'New Branch')
        self.assertTrue('id' in data)
        
        # Verify in database
        self.assertTrue(XX_Segment.objects.filter(code='300').exists())
    
    def test_create_segment_with_parent(self):
        """Test creating a child segment with parent code"""
        new_data = {
            'segment_type': self.entity_type.id,
            'code': '120',
            'parent_code': '100',
            'alias': 'Department B',
            'node_type': 'sub_parent',
            'is_active': True
        }
        
        response = self.client.post(
            '/gl/segments/',
            data=json.dumps(new_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data['parent_code'], '100')
    
    def test_get_segment_detail(self):
        """Test GET /segments/{id}/ - Get specific segment"""
        response = self.client.get(f'/gl/segments/{self.parent_segment.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['code'], '100')
        self.assertEqual(data['alias'], 'Main Office')
        self.assertTrue('segment_type_name' in data)
        self.assertEqual(data['segment_type_name'], 'Entity')
    
    def test_update_segment_patch(self):
        """Test PATCH /segments/{id}/ - Partial update"""
        update_data = {
            'alias': 'Updated Main Office'
        }
        
        response = self.client.patch(
            f'/gl/segments/{self.parent_segment.id}/',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['alias'], 'Updated Main Office')
        
        # Verify in database
        self.parent_segment.refresh_from_db()
        self.assertEqual(self.parent_segment.alias, 'Updated Main Office')
    
    def test_delete_segment_success(self):
        """Test DELETE /segments/{id}/ - Successful deletion"""
        # Create a segment with no children
        temp_segment = XX_Segment.objects.create(
            segment_type=self.entity_type,
            code='999',
            alias='Temp Segment',
            node_type='parent',
            is_active=True
        )
        
        response = self.client.delete(f'/gl/segments/{temp_segment.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(XX_Segment.objects.filter(id=temp_segment.id).exists())
    
    def test_get_segment_parent(self):
        """Test GET /segments/{id}/parent/ - Get parent segment"""
        response = self.client.get(f'/gl/segments/{self.child_segment.id}/parent/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['code'], '100')
        self.assertEqual(data['alias'], 'Main Office')
    
    def test_get_segment_parent_none(self):
        """Test getting parent when segment has no parent"""
        response = self.client.get(f'/gl/segments/{self.parent_segment.id}/parent/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.json())
    
    def test_get_segment_full_path(self):
        """Test GET /segments/{id}/full-path/ - Get hierarchical path"""
        response = self.client.get(f'/gl/segments/{self.grandchild_segment.id}/full-path/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['full_path'], '100 > 110 > 111')
        self.assertEqual(data['path_segments'], ['100', '110', '111'])
    
    def test_get_segment_children_codes_only(self):
        """Test GET /segments/{id}/children/ - Get children codes"""
        response = self.client.get(f'/gl/segments/{self.parent_segment.id}/children/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue('children_codes' in data)
        self.assertTrue('children_count' in data)
        self.assertIn('110', data['children_codes'])
        self.assertIn('111', data['children_codes'])
        self.assertEqual(data['children_count'], 2)
    
    def test_get_segment_children_with_details(self):
        """Test GET /segments/{id}/children/?include_details=true"""
        response = self.client.get(
            f'/gl/segments/{self.parent_segment.id}/children/?include_details=true'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue('children' in data)
        self.assertTrue('children_count' in data)
        self.assertEqual(len(data['children']), 2)
        self.assertEqual(data['children_count'], 2)
    
    def test_segment_can_delete(self):
        """Test GET /segments/{id}/can-delete/"""
        # Parent with children cannot be deleted
        response = self.client.get(f'/gl/segments/{self.parent_segment.id}/can-delete/')
        data = response.json()
        self.assertFalse(data['can_delete'])
        self.assertTrue('reason' in data)
        
        # Leaf segment can be deleted
        response = self.client.get(f'/gl/segments/{self.grandchild_segment.id}/can-delete/')
        data = response.json()
        self.assertTrue(data['can_delete'])
    
    def test_segment_toggle_active(self):
        """Test POST /segments/{id}/toggle-active/"""
        original_status = self.parent_segment.is_active
        
        response = self.client.post(f'/gl/segments/{self.parent_segment.id}/toggle-active/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['is_active'], not original_status)
        
        # Verify in database
        self.parent_segment.refresh_from_db()
        self.assertEqual(self.parent_segment.is_active, not original_status)
    
    def test_segment_is_used_in_transactions(self):
        """Test GET /segments/{id}/is-used-in-transactions/"""
        response = self.client.get(
            f'/gl/segments/{self.parent_segment.id}/is-used-in-transactions/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue('is_used' in data)
        self.assertTrue('usage_details' in data)
        self.assertFalse(data['is_used'])  # No transactions yet


class ComplexScenarioTestCase(TestCase):
    """Test complex scenarios and edge cases"""
    
    def setUp(self):
        """Set up complex test data"""
        self.client = Client()
        
        # Create multiple segment types
        self.entity_type = XX_SegmentType.objects.create(
            segment_name="Entity",
            is_required=True,
            has_hierarchy=True,
            length=50,
            display_order=1
        )
        
        self.account_type = XX_SegmentType.objects.create(
            segment_name="Account",
            is_required=True,
            has_hierarchy=False,
            length=50,
            display_order=2
        )
        
        # Create deep hierarchy
        self.level1 = XX_Segment.objects.create(
            segment_type=self.entity_type,
            code="1000",
            alias="Level 1",
            node_type="parent"
        )
        
        self.level2 = XX_Segment.objects.create(
            segment_type=self.entity_type,
            code="1100",
            parent_code="1000",
            alias="Level 2",
            node_type="sub_parent"
        )
        
        self.level3 = XX_Segment.objects.create(
            segment_type=self.entity_type,
            code="1110",
            parent_code="1100",
            alias="Level 3",
            node_type="sub_parent"
        )
        
        self.level4 = XX_Segment.objects.create(
            segment_type=self.entity_type,
            code="1111",
            parent_code="1110",
            alias="Level 4",
            node_type="child"
        )
    
    def test_deep_hierarchy_full_path(self):
        """Test full path for deep hierarchy"""
        response = self.client.get(f'/gl/segments/{self.level4.id}/full-path/')
        
        data = response.json()
        self.assertEqual(data['full_path'], '1000 > 1100 > 1110 > 1111')
        self.assertEqual(len(data['path_segments']), 4)
    
    def test_recursive_children_retrieval(self):
        """Test getting all descendants recursively"""
        response = self.client.get(f'/gl/segments/{self.level1.id}/children/')
        
        data = response.json()
        # Should get all 3 descendants
        self.assertEqual(data['children_count'], 3)
        self.assertIn('1100', data['children_codes'])
        self.assertIn('1110', data['children_codes'])
        self.assertIn('1111', data['children_codes'])
    
    def test_multiple_filters_combined(self):
        """Test combining multiple filters"""
        # Create more test data
        XX_Segment.objects.create(
            segment_type=self.entity_type,
            code="2000",
            alias="Inactive Parent",
            node_type="parent",
            is_active=False
        )
        
        # Filter by type, active status, and node type
        response = self.client.get(
            f'/gl/segments/?segment_type={self.entity_type.id}&is_active=true&node_type=parent'
        )
        
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['code'], '1000')
    
    def test_segment_type_with_values_endpoint(self):
        """Test getting all values for a segment type"""
        response = self.client.get(f'/gl/segment-types/{self.entity_type.id}/values/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 4)  # All 4 segments
    
    def test_segment_type_values_filtered(self):
        """Test filtering segment type values"""
        response = self.client.get(
            f'/gl/segment-types/{self.entity_type.id}/values/?node_type=parent'
        )
        
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['code'], '1000')
    
    def test_404_on_nonexistent_segment_type(self):
        """Test 404 response for non-existent segment type"""
        response = self.client.get('/gl/segment-types/99999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_404_on_nonexistent_segment(self):
        """Test 404 response for non-existent segment"""
        response = self.client.get('/gl/segments/99999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_create_segment_invalid_segment_type(self):
        """Test creating segment with invalid segment type"""
        new_data = {
            'segment_type': 99999,  # Non-existent
            'code': '999',
            'alias': 'Test',
            'node_type': 'parent'
        }
        
        response = self.client.post(
            '/gl/segments/',
            data=json.dumps(new_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_bulk_toggle_operations(self):
        """Test toggling multiple segments"""
        segments = [self.level1, self.level2, self.level3]
        
        for segment in segments:
            original_status = segment.is_active
            response = self.client.post(f'/gl/segments/{segment.id}/toggle-active/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            segment.refresh_from_db()
            self.assertEqual(segment.is_active, not original_status)
    
    def test_segment_type_list_includes_values_count(self):
        """Test that segment type list includes values count"""
        response = self.client.get('/gl/segment-types/')
        
        data = response.json()
        entity_type_data = next(st for st in data if st['segment_name'] == 'Entity')
        self.assertTrue('values_count' in entity_type_data)
        self.assertEqual(entity_type_data['values_count'], 4)
        
        account_type_data = next(st for st in data if st['segment_name'] == 'Account')
        self.assertEqual(account_type_data['values_count'], 0)


class EdgeCaseTestCase(TestCase):
    """Test edge cases and boundary conditions"""
    
    def setUp(self):
        """Set up edge case test data"""
        self.client = Client()
        
        self.segment_type = XX_SegmentType.objects.create(
            segment_name="Test",
            is_required=True,
            has_hierarchy=True,
            length=50,
            display_order=1
        )
    
    def test_segment_with_no_alias(self):
        """Test segment with no alias"""
        segment = XX_Segment.objects.create(
            segment_type=self.segment_type,
            code="100",
            node_type="parent"
        )
        
        response = self.client.get(f'/gl/segments/{segment.id}/')
        data = response.json()
        
        # Name property should return code when alias is None
        self.assertEqual(data['name'], '100')
    
    def test_segment_with_empty_description(self):
        """Test segment type with empty description"""
        response = self.client.get(f'/gl/segment-types/{self.segment_type.id}/')
        data = response.json()
        
        # Description should be None or empty string
        self.assertIn(data.get('description'), [None, ''])
    
    def test_parent_of_orphan_segment(self):
        """Test getting parent of segment with invalid parent_code"""
        segment = XX_Segment.objects.create(
            segment_type=self.segment_type,
            code="200",
            parent_code="999",  # Non-existent parent
            node_type="child"
        )
        
        response = self.client.get(f'/gl/segments/{segment.id}/parent/')
        
        # Should return None when parent doesn't exist
        self.assertIsNone(response.json())
    
    def test_children_of_leaf_segment(self):
        """Test getting children of a leaf segment"""
        leaf = XX_Segment.objects.create(
            segment_type=self.segment_type,
            code="300",
            node_type="child"
        )
        
        response = self.client.get(f'/gl/segments/{leaf.id}/children/')
        data = response.json()
        
        self.assertEqual(data['children_count'], 0)
        self.assertEqual(len(data['children_codes']), 0)
