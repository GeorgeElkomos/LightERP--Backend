"""
Script to test all Default Combinations endpoints
"""
import requests
import json
from typing import Dict, Any

BASE_URL = "http://127.0.0.1:8000"
ENDPOINTS = [
    {"method": "GET", "url": "/finance/default-combinations/", "description": "List all defaults"},
    {"method": "POST", "url": "/finance/default-combinations/", "description": "Create/update default", "data": "required"},
    {"method": "GET", "url": "/finance/default-combinations/{id}/", "description": "Retrieve specific default", "needs_id": True},
    {"method": "PUT", "url": "/finance/default-combinations/{id}/", "description": "Update default", "needs_id": True, "data": "required"},
    {"method": "PATCH", "url": "/finance/default-combinations/{id}/", "description": "Partial update", "needs_id": True, "data": "required"},
    {"method": "DELETE", "url": "/finance/default-combinations/{id}/", "description": "Delete default", "needs_id": True},
    {"method": "GET", "url": "/finance/default-combinations/by-transaction-type/AP_INVOICE/", "description": "Get by transaction type"},
    {"method": "GET", "url": "/finance/default-combinations/ap-invoice-default/", "description": "Get AP invoice default"},
    {"method": "GET", "url": "/finance/default-combinations/ar-invoice-default/", "description": "Get AR invoice default"},
    {"method": "POST", "url": "/finance/default-combinations/{id}/validate/", "description": "Validate combination", "needs_id": True},
    {"method": "POST", "url": "/finance/default-combinations/check-all-validity/", "description": "Check all defaults"},
    {"method": "POST", "url": "/finance/default-combinations/{id}/activate/", "description": "Activate default", "needs_id": True},
    {"method": "POST", "url": "/finance/default-combinations/{id}/deactivate/", "description": "Deactivate default", "needs_id": True},
    {"method": "GET", "url": "/finance/default-combinations/transaction-types/", "description": "List transaction types"},
]

def get_auth_token():
    """Get authentication token"""
    print("\n=== Attempting to get authentication token ===")
    
    # Try to login
    login_endpoints = [
        "/api/auth/login/",
        "/auth/login/",
        "/api/token/",
    ]
    
    # Common test credentials
    credentials = [
        {"username": "admin", "password": "admin"},
        {"username": "admin", "password": "admin123"},
        {"username": "test", "password": "test"},
    ]
    
    for endpoint in login_endpoints:
        for cred in credentials:
            try:
                url = f"{BASE_URL}{endpoint}"
                response = requests.post(url, json=cred, timeout=5)
                if response.status_code in [200, 201]:
                    data = response.json()
                    token = data.get('token') or data.get('access') or data.get('access_token')
                    if token:
                        print(f"✓ Successfully authenticated at {endpoint}")
                        return token
            except Exception:
                continue
    
    print("⚠ Could not authenticate - will test endpoints without auth token")
    return None

def test_endpoint(method: str, url: str, description: str, headers: Dict, test_id: int = None, data: Dict = None) -> Dict[str, Any]:
    """Test a single endpoint"""
    
    # Replace {id} with actual ID if needed
    if "{id}" in url:
        if test_id is None:
            return {
                "status": "SKIPPED",
                "reason": "No ID available",
                "status_code": None
            }
        url = url.replace("{id}", str(test_id))
    
    full_url = f"{BASE_URL}{url}"
    
    try:
        if method == "GET":
            response = requests.get(full_url, headers=headers, timeout=10)
        elif method == "POST":
            response = requests.post(full_url, headers=headers, json=data or {}, timeout=10)
        elif method == "PUT":
            response = requests.put(full_url, headers=headers, json=data or {}, timeout=10)
        elif method == "PATCH":
            response = requests.patch(full_url, headers=headers, json=data or {}, timeout=10)
        elif method == "DELETE":
            response = requests.delete(full_url, headers=headers, timeout=10)
        else:
            return {"status": "ERROR", "reason": "Unknown method", "status_code": None}
        
        # Determine status
        if response.status_code in [200, 201]:
            status = "✓ WORKING"
        elif response.status_code == 401:
            status = "⚠ AUTH REQUIRED"
        elif response.status_code == 403:
            status = "⚠ FORBIDDEN"
        elif response.status_code == 404:
            status = "✗ NOT FOUND (might need data)"
        elif response.status_code == 405:
            status = "✗ METHOD NOT ALLOWED"
        elif response.status_code in [400, 422]:
            status = "⚠ BAD REQUEST (might need proper data)"
        else:
            status = f"? STATUS {response.status_code}"
        
        result = {
            "status": status,
            "status_code": response.status_code,
            "response_preview": None
        }
        
        # Try to get response preview
        try:
            if response.status_code != 204:
                data = response.json()
                if isinstance(data, list):
                    result["response_preview"] = f"List with {len(data)} items"
                elif isinstance(data, dict):
                    keys = list(data.keys())[:5]
                    result["response_preview"] = f"Dict with keys: {', '.join(keys)}"
        except:
            pass
        
        return result
        
    except requests.exceptions.Timeout:
        return {"status": "✗ TIMEOUT", "status_code": None}
    except requests.exceptions.ConnectionError:
        return {"status": "✗ CONNECTION ERROR", "status_code": None}
    except Exception as e:
        return {"status": f"✗ ERROR: {str(e)[:50]}", "status_code": None}

def main():
    print("=" * 80)
    print("TESTING DEFAULT COMBINATIONS ENDPOINTS")
    print("=" * 80)
    
    # Get auth token
    token = get_auth_token()
    
    headers = {}
    if token:
        headers["Authorization"] = f"Token {token}"
    
    # First, try to get a list to find an existing ID
    print("\n=== Getting existing data for ID-based tests ===")
    list_url = f"{BASE_URL}/finance/default-combinations/"
    test_id = None
    
    try:
        response = requests.get(list_url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                test_id = data[0].get('id')
                print(f"✓ Found test ID: {test_id}")
            elif isinstance(data, dict) and 'results' in data and len(data['results']) > 0:
                test_id = data['results'][0].get('id')
                print(f"✓ Found test ID: {test_id}")
            else:
                print("⚠ No existing data found - ID-based tests will be skipped")
        else:
            print(f"⚠ Could not fetch list (status {response.status_code})")
    except Exception as e:
        print(f"⚠ Error fetching list: {e}")
    
    # Test all endpoints
    print("\n" + "=" * 80)
    print("ENDPOINT TEST RESULTS")
    print("=" * 80)
    
    results = []
    
    for i, endpoint_info in enumerate(ENDPOINTS, 1):
        method = endpoint_info["method"]
        url = endpoint_info["url"]
        description = endpoint_info["description"]
        needs_id = endpoint_info.get("needs_id", False)
        
        print(f"\n[{i}/{len(ENDPOINTS)}] Testing: {method:6s} {url}")
        print(f"    Description: {description}")
        
        result = test_endpoint(
            method=method,
            url=url,
            description=description,
            headers=headers,
            test_id=test_id if needs_id else None
        )
        
        print(f"    Result: {result['status']}")
        if result.get('status_code'):
            print(f"    Status Code: {result['status_code']}")
        if result.get('response_preview'):
            print(f"    Response: {result['response_preview']}")
        
        results.append({
            "endpoint": f"{method} {url}",
            "description": description,
            **result
        })
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    working = sum(1 for r in results if "✓ WORKING" in r['status'])
    auth_required = sum(1 for r in results if "⚠ AUTH REQUIRED" in r['status'])
    not_found = sum(1 for r in results if "✗ NOT FOUND" in r['status'])
    method_not_allowed = sum(1 for r in results if "✗ METHOD NOT ALLOWED" in r['status'])
    skipped = sum(1 for r in results if "SKIPPED" in r['status'])
    other = len(results) - working - auth_required - not_found - method_not_allowed - skipped
    
    print(f"\nTotal endpoints tested: {len(results)}")
    print(f"  ✓ Working:              {working}")
    print(f"  ⚠ Auth Required:        {auth_required}")
    print(f"  ✗ Not Found:            {not_found}")
    print(f"  ✗ Method Not Allowed:   {method_not_allowed}")
    print(f"  ⚠ Skipped:              {skipped}")
    print(f"  ? Other Issues:         {other}")
    
    # Detailed breakdown
    print("\n" + "=" * 80)
    print("DETAILED BREAKDOWN BY STATUS")
    print("=" * 80)
    
    for status_filter in ["✓ WORKING", "⚠ AUTH REQUIRED", "✗ NOT FOUND", "✗ METHOD NOT ALLOWED", "SKIPPED"]:
        filtered = [r for r in results if status_filter in r['status']]
        if filtered:
            print(f"\n{status_filter}:")
            for r in filtered:
                print(f"  • {r['endpoint']:60s} - {r['description']}")
    
    # List other issues
    other_results = [r for r in results if not any(s in r['status'] for s in ["✓ WORKING", "⚠ AUTH REQUIRED", "✗ NOT FOUND", "✗ METHOD NOT ALLOWED", "SKIPPED"])]
    if other_results:
        print(f"\nOTHER ISSUES:")
        for r in other_results:
            print(f"  • {r['endpoint']:60s} - {r['status']}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
