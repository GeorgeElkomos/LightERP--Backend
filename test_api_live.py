"""
Live API testing script for Segment endpoints.
Tests the running server at http://127.0.0.1:8000/
"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000/finance/gl/api"


def print_test(test_name, passed, details=""):
    """Print test result"""
    status = "[PASS]" if passed else "[FAIL]"
    print(f"{status}: {test_name}")
    if details:
        print(f"  {details}")
    print()


def test_segment_types():
    """Test Segment Type endpoints"""
    print("=" * 60)
    print("TESTING SEGMENT TYPE ENDPOINTS")
    print("=" * 60)
    print()
    
    # Test 1: List all segment types
    print("Test 1: GET /segment-types/ - List all")
    response = requests.get(f"{BASE_URL}/segment-types/")
    print_test(
        "List segment types",
        response.status_code == 200,
        f"Status: {response.status_code}, Count: {len(response.json()) if response.status_code == 200 else 'N/A'}"
    )
    
    # Test 2: Create a new segment type
    print("Test 2: POST /segment-types/ - Create new")
    new_segment_type = {
        "segment_name": "TestDepartment",
        "is_required": True,
        "has_hierarchy": False,
        "length": 10,
        "display_order": 99,
        "description": "Test department codes",
        "is_active": True
    }
    response = requests.post(f"{BASE_URL}/segment-types/", json=new_segment_type)
    created_id = None
    if response.status_code == 201:
        created_id = response.json().get('id')
    print_test(
        "Create segment type",
        response.status_code == 201,
        f"Status: {response.status_code}, ID: {created_id}"
    )
    
    if created_id:
        # Test 3: Get specific segment type
        print(f"Test 3: GET /segment-types/{created_id}/ - Get details")
        response = requests.get(f"{BASE_URL}/segment-types/{created_id}/")
        print_test(
            "Get segment type details",
            response.status_code == 200 and response.json().get('segment_name') == 'TestDepartment',
            f"Status: {response.status_code}, Name: {response.json().get('segment_name') if response.status_code == 200 else 'N/A'}"
        )
        
        # Test 4: Update segment type (PATCH)
        print(f"Test 4: PATCH /segment-types/{created_id}/ - Partial update")
        update_data = {"description": "Updated description"}
        response = requests.patch(f"{BASE_URL}/segment-types/{created_id}/", json=update_data)
        print_test(
            "Update segment type",
            response.status_code == 200 and response.json().get('description') == 'Updated description',
            f"Status: {response.status_code}"
        )
        
        # Test 5: Check if can delete
        print(f"Test 5: GET /segment-types/{created_id}/can-delete/ - Check deletion")
        response = requests.get(f"{BASE_URL}/segment-types/{created_id}/can-delete/")
        print_test(
            "Check can delete",
            response.status_code == 200 and 'can_delete' in response.json(),
            f"Status: {response.status_code}, Can delete: {response.json().get('can_delete') if response.status_code == 200 else 'N/A'}"
        )
        
        # Test 6: Check transaction usage
        print(f"Test 6: GET /segment-types/{created_id}/is-used-in-transactions/")
        response = requests.get(f"{BASE_URL}/segment-types/{created_id}/is-used-in-transactions/")
        print_test(
            "Check transaction usage",
            response.status_code == 200 and 'is_used' in response.json(),
            f"Status: {response.status_code}, Is used: {response.json().get('is_used') if response.status_code == 200 else 'N/A'}"
        )
        
        # Test 7: Toggle active status
        print(f"Test 7: POST /segment-types/{created_id}/toggle-active/")
        response = requests.post(f"{BASE_URL}/segment-types/{created_id}/toggle-active/")
        print_test(
            "Toggle active status",
            response.status_code == 200 and 'is_active' in response.json(),
            f"Status: {response.status_code}, Is active: {response.json().get('is_active') if response.status_code == 200 else 'N/A'}"
        )
        
        # Test 8: Get values for segment type
        print(f"Test 8: GET /segment-types/{created_id}/values/")
        response = requests.get(f"{BASE_URL}/segment-types/{created_id}/values/")
        print_test(
            "Get segment type values",
            response.status_code == 200,
            f"Status: {response.status_code}, Count: {len(response.json()) if response.status_code == 200 else 'N/A'}"
        )
        
        # Test 9: Delete segment type
        print(f"Test 9: DELETE /segment-types/{created_id}/ - Delete")
        response = requests.delete(f"{BASE_URL}/segment-types/{created_id}/")
        print_test(
            "Delete segment type",
            response.status_code == 204,
            f"Status: {response.status_code}"
        )
    
    # Test 10: Filter by active status
    print("Test 10: GET /segment-types/?is_active=true - Filter active")
    response = requests.get(f"{BASE_URL}/segment-types/?is_active=true")
    print_test(
        "Filter by active status",
        response.status_code == 200,
        f"Status: {response.status_code}, Count: {len(response.json()) if response.status_code == 200 else 'N/A'}"
    )


def test_segments():
    """Test Segment endpoints"""
    print("=" * 60)
    print("TESTING SEGMENT ENDPOINTS")
    print("=" * 60)
    print()
    
    # First, create a segment type to use
    segment_type_data = {
        "segment_name": "TestEntity",
        "is_required": True,
        "has_hierarchy": True,
        "length": 50,
        "display_order": 1
    }
    response = requests.post(f"{BASE_URL}/segment-types/", json=segment_type_data)
    if response.status_code != 201:
        print("Failed to create test segment type!")
        return
    
    segment_type_id = response.json()['id']
    print(f"Created test segment type with ID: {segment_type_id}\n")
    
    # Test 1: List all segments
    print("Test 1: GET /segments/ - List all")
    response = requests.get(f"{BASE_URL}/segments/")
    print_test(
        "List segments",
        response.status_code == 200,
        f"Status: {response.status_code}, Count: {len(response.json()) if response.status_code == 200 else 'N/A'}"
    )
    
    # Test 2: Create parent segment
    print("Test 2: POST /segments/ - Create parent")
    parent_data = {
        "segment_type": segment_type_id,
        "code": "1000",
        "alias": "Main Office",
        "node_type": "parent",
        "is_active": True
    }
    response = requests.post(f"{BASE_URL}/segments/", json=parent_data)
    parent_id = None
    if response.status_code == 201:
        parent_id = response.json().get('id')
    print_test(
        "Create parent segment",
        response.status_code == 201,
        f"Status: {response.status_code}, ID: {parent_id}"
    )
    
    # Test 3: Create child segment
    print("Test 3: POST /segments/ - Create child")
    child_data = {
        "segment_type": segment_type_id,
        "code": "1100",
        "parent_code": "1000",
        "alias": "Department A",
        "node_type": "sub_parent",
        "is_active": True
    }
    response = requests.post(f"{BASE_URL}/segments/", json=child_data)
    child_id = None
    if response.status_code == 201:
        child_id = response.json().get('id')
    print_test(
        "Create child segment",
        response.status_code == 201,
        f"Status: {response.status_code}, ID: {child_id}"
    )
    
    # Test 4: Create grandchild segment
    print("Test 4: POST /segments/ - Create grandchild")
    grandchild_data = {
        "segment_type": segment_type_id,
        "code": "1110",
        "parent_code": "1100",
        "alias": "Team 1",
        "node_type": "child",
        "is_active": True
    }
    response = requests.post(f"{BASE_URL}/segments/", json=grandchild_data)
    grandchild_id = None
    if response.status_code == 201:
        grandchild_id = response.json().get('id')
    print_test(
        "Create grandchild segment",
        response.status_code == 201,
        f"Status: {response.status_code}, ID: {grandchild_id}"
    )
    
    if parent_id and child_id and grandchild_id:
        # Test 5: Get parent of child
        print(f"Test 5: GET /segments/{child_id}/parent/ - Get parent")
        response = requests.get(f"{BASE_URL}/segments/{child_id}/parent/")
        parent_code = response.json().get('code') if response.status_code == 200 else None
        print_test(
            "Get parent segment",
            response.status_code == 200 and parent_code == "1000",
            f"Status: {response.status_code}, Parent code: {parent_code}"
        )
        
        # Test 6: Get full path of grandchild
        print(f"Test 6: GET /segments/{grandchild_id}/full-path/ - Get hierarchy")
        response = requests.get(f"{BASE_URL}/segments/{grandchild_id}/full-path/")
        full_path = response.json().get('full_path') if response.status_code == 200 else None
        print_test(
            "Get full hierarchical path",
            response.status_code == 200 and full_path == "1000 > 1100 > 1110",
            f"Status: {response.status_code}, Path: {full_path}"
        )
        
        # Test 7: Get children of parent
        print(f"Test 7: GET /segments/{parent_id}/children/ - Get descendants")
        response = requests.get(f"{BASE_URL}/segments/{parent_id}/children/")
        children_count = response.json().get('children_count') if response.status_code == 200 else 0
        print_test(
            "Get all children",
            response.status_code == 200 and children_count == 2,
            f"Status: {response.status_code}, Children count: {children_count}"
        )
        
        # Test 8: Get children with details
        print(f"Test 8: GET /segments/{parent_id}/children/?include_details=true")
        response = requests.get(f"{BASE_URL}/segments/{parent_id}/children/?include_details=true")
        has_children_array = 'children' in response.json() if response.status_code == 200 else False
        print_test(
            "Get children with details",
            response.status_code == 200 and has_children_array,
            f"Status: {response.status_code}, Has children array: {has_children_array}"
        )
        
        # Test 9: Check if parent can be deleted (should be false - has children)
        print(f"Test 9: GET /segments/{parent_id}/can-delete/")
        response = requests.get(f"{BASE_URL}/segments/{parent_id}/can-delete/")
        can_delete = response.json().get('can_delete') if response.status_code == 200 else None
        print_test(
            "Check parent can delete (should be false)",
            response.status_code == 200 and can_delete == False,
            f"Status: {response.status_code}, Can delete: {can_delete}"
        )
        
        # Test 10: Check if grandchild can be deleted (should be true - no children)
        print(f"Test 10: GET /segments/{grandchild_id}/can-delete/")
        response = requests.get(f"{BASE_URL}/segments/{grandchild_id}/can-delete/")
        can_delete = response.json().get('can_delete') if response.status_code == 200 else None
        print_test(
            "Check grandchild can delete (should be true)",
            response.status_code == 200 and can_delete == True,
            f"Status: {response.status_code}, Can delete: {can_delete}"
        )
        
        # Test 11: Toggle segment active status
        print(f"Test 11: POST /segments/{parent_id}/toggle-active/")
        response = requests.post(f"{BASE_URL}/segments/{parent_id}/toggle-active/")
        print_test(
            "Toggle segment active",
            response.status_code == 200 and 'is_active' in response.json(),
            f"Status: {response.status_code}"
        )
        
        # Test 12: Filter segments by type
        print(f"Test 12: GET /segments/?segment_type={segment_type_id}")
        response = requests.get(f"{BASE_URL}/segments/?segment_type={segment_type_id}")
        print_test(
            "Filter by segment type",
            response.status_code == 200,
            f"Status: {response.status_code}, Count: {len(response.json()) if response.status_code == 200 else 'N/A'}"
        )
        
        # Test 13: Filter by node type
        print("Test 13: GET /segments/?node_type=parent")
        response = requests.get(f"{BASE_URL}/segments/?node_type=parent")
        print_test(
            "Filter by node type",
            response.status_code == 200,
            f"Status: {response.status_code}, Count: {len(response.json()) if response.status_code == 200 else 'N/A'}"
        )
        
        # Test 14: Update segment
        print(f"Test 14: PATCH /segments/{parent_id}/ - Update")
        update_data = {"alias": "Updated Main Office"}
        response = requests.patch(f"{BASE_URL}/segments/{parent_id}/", json=update_data)
        print_test(
            "Update segment",
            response.status_code == 200,
            f"Status: {response.status_code}"
        )
        
        # Test 15: Check transaction usage
        print(f"Test 15: GET /segments/{parent_id}/is-used-in-transactions/")
        response = requests.get(f"{BASE_URL}/segments/{parent_id}/is-used-in-transactions/")
        print_test(
            "Check transaction usage",
            response.status_code == 200 and 'is_used' in response.json(),
            f"Status: {response.status_code}, Is used: {response.json().get('is_used') if response.status_code == 200 else 'N/A'}"
        )
    
    # Cleanup - delete the test segment type
    print(f"\nCleaning up: Deleting test segment type {segment_type_id}")
    # First delete all segments
    if grandchild_id:
        requests.delete(f"{BASE_URL}/segments/{grandchild_id}/")
    if child_id:
        requests.delete(f"{BASE_URL}/segments/{child_id}/")
    if parent_id:
        requests.delete(f"{BASE_URL}/segments/{parent_id}/")
    # Then delete the type
    requests.delete(f"{BASE_URL}/segment-types/{segment_type_id}/")
    print("Cleanup complete\n")


def test_edge_cases():
    """Test edge cases and error handling"""
    print("=" * 60)
    print("TESTING EDGE CASES")
    print("=" * 60)
    print()
    
    # Test 1: Get non-existent segment type
    print("Test 1: GET /segment-types/99999/ - Non-existent")
    response = requests.get(f"{BASE_URL}/segment-types/99999/")
    print_test(
        "404 for non-existent segment type",
        response.status_code == 404,
        f"Status: {response.status_code}"
    )
    
    # Test 2: Get non-existent segment
    print("Test 2: GET /segments/99999/ - Non-existent")
    response = requests.get(f"{BASE_URL}/segments/99999/")
    print_test(
        "404 for non-existent segment",
        response.status_code == 404,
        f"Status: {response.status_code}"
    )
    
    # Test 3: Create segment with invalid segment type
    print("Test 3: POST /segments/ - Invalid segment type")
    invalid_data = {
        "segment_type": 99999,
        "code": "TEST",
        "node_type": "parent"
    }
    response = requests.post(f"{BASE_URL}/segments/", json=invalid_data)
    print_test(
        "400 for invalid segment type",
        response.status_code == 400,
        f"Status: {response.status_code}"
    )


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("SEGMENT API LIVE TESTING")
    print("Testing server at: http://127.0.0.1:8000")
    print("=" * 60)
    print()
    
    try:
        # Check if server is running
        response = requests.get("http://127.0.0.1:8000/")
        print("[OK] Server is running!\n")
    except requests.exceptions.ConnectionError:
        print("[ERROR] Server is not running at http://127.0.0.1:8000")
        print("Please start the server with: python manage.py runserver")
        exit(1)

    
    # Run all tests
    test_segment_types()
    test_segments()
    test_edge_cases()
    
    print("=" * 60)
    print("TESTING COMPLETE")
    print("=" * 60)
