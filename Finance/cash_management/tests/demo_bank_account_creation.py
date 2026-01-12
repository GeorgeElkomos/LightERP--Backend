"""
Demo script showing how to create Bank Accounts using the updated API

This demonstrates TWO approaches for creating bank accounts:
1. Using existing GL combination IDs (original approach)
2. Using segment details directly (new approach - like Invoice/Payment/JE)
"""

import requests
import json

# Configuration
BASE_URL = "http://localhost:8000"
ACCESS_TOKEN = "your_access_token_here"  # Replace with actual token

# API endpoints
ACCOUNTS_URL = f"{BASE_URL}/finance/cash/accounts/"

# Headers
headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}


def create_account_with_combination_ids():
    """
    APPROACH 1: Using existing GL combination IDs
    
    This is the original approach - requires GL combinations to be created first.
    """
    print("\n" + "="*70)
    print("APPROACH 1: Create Bank Account with GL Combination IDs")
    print("="*70)
    
    data = {
        "branch": 1,
        "account_number": "ACC1234567890",
        "account_name": "Main Operating Account",
        "account_type": "CURRENT",
        "currency": 1,
        "opening_balance": "50000.00",
        "iban": "US12NBCO0210000211234567890",
        "opening_date": "2026-01-01",
        "cash_GL_combination": 1,  # Existing combination ID
        "cash_clearing_GL_combination": 2,  # Existing combination ID
        "is_active": True,
        "description": "Main company operating account for daily transactions"
    }
    
    print("\nRequest body:")
    print(json.dumps(data, indent=2))
    
    response = requests.post(ACCOUNTS_URL, headers=headers, json=data)
    
    if response.status_code == 201:
        result = response.json()
        print(f"\n✓ Account created successfully!")
        print(f"  ID: {result['id']}")
        print(f"  Account Number: {result['account_number']}")
        print(f"  Account Name: {result['account_name']}")
        print(f"  Cash GL Combination: {result['cash_GL_combination']}")
        print(f"  Clearing GL Combination: {result['cash_clearing_GL_combination']}")
        return True
    else:
        print(f"\n✗ Failed: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        return False


def create_account_with_segments():
    """
    APPROACH 2: Using segment details directly (NEW!)
    
    This is the new approach - just like Invoice, Payment, and Journal Entry creation.
    No need to create GL combinations first - they're created automatically!
    """
    print("\n" + "="*70)
    print("APPROACH 2: Create Bank Account with Segment Details (NEW!)")
    print("="*70)
    
    data = {
        "branch": 1,
        "account_number": "ACC9876543210",
        "account_name": "Secondary Operating Account",
        "account_type": "CURRENT",
        "currency": 1,
        "opening_balance": "25000.00",
        "iban": "US12NBCO0210000219876543210",
        "opening_date": "2026-01-01",
        # NEW: Provide segment details instead of combination IDs!
        "cash_GL_segments": [
            {
                "segment_type_id": 1,  # Entity
                "segment_code": "100"
            },
            {
                "segment_type_id": 2,  # Account
                "segment_code": "1010"  # Cash account
            }
        ],
        "cash_clearing_GL_segments": [
            {
                "segment_type_id": 1,  # Entity
                "segment_code": "100"
            },
            {
                "segment_type_id": 2,  # Account
                "segment_code": "1020"  # Cash clearing account
            }
        ],
        "is_active": True,
        "description": "Secondary account created with segment details"
    }
    
    print("\nRequest body:")
    print(json.dumps(data, indent=2))
    
    response = requests.post(ACCOUNTS_URL, headers=headers, json=data)
    
    if response.status_code == 201:
        result = response.json()
        print(f"\n✓ Account created successfully!")
        print(f"  ID: {result['id']}")
        print(f"  Account Number: {result['account_number']}")
        print(f"  Account Name: {result['account_name']}")
        print(f"  Cash GL Combination: {result['cash_GL_combination']} (AUTO-CREATED)")
        print(f"  Clearing GL Combination: {result['cash_clearing_GL_combination']} (AUTO-CREATED)")
        print("\nNote: GL combinations were automatically created or reused!")
        return True
    else:
        print(f"\n✗ Failed: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        return False


def main():
    """Run demo for both approaches"""
    print("\n" + "="*70)
    print(" BANK ACCOUNT CREATION - TWO APPROACHES")
    print("="*70)
    print("\nThis demo shows two ways to create bank accounts:")
    print("  1. Using existing GL combination IDs (original)")
    print("  2. Using segment details directly (NEW - like Invoice/Payment/JE)")
    print("="*70)
    
    print("\n\n>>> Choose which demo to run:")
    print("    1 - Create with GL combination IDs (original)")
    print("    2 - Create with segment details (NEW)")
    print("    3 - Run both demos")
    
    try:
        choice = input("\nEnter choice (1-3): ").strip()
        
        if choice == "1":
            create_account_with_combination_ids()
        elif choice == "2":
            create_account_with_segments()
        elif choice == "3":
            create_account_with_combination_ids()
            create_account_with_segments()
        else:
            print("Invalid choice")
            
        print("\n" + "="*70)
        print("DEMO COMPLETE")
        print("="*70)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nMake sure:")
        print("  1. Server is running (python manage.py runserver)")
        print("  2. ACCESS_TOKEN is set correctly")
        print("  3. Branch ID, Currency ID exist")
        print("  4. Segment types and codes exist (for Approach 2)")


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                 BANK ACCOUNT CREATION API DEMO                       ║
╚══════════════════════════════════════════════════════════════════════╝

WHAT'S NEW:
===========
You can now create bank accounts by providing GL segment details directly,
just like you do when creating Invoices, Payments, or Journal Entries!

APPROACH 1 (Original):
======================
Provide GL combination IDs:
{
  "cash_GL_combination": 1,
  "cash_clearing_GL_combination": 2,
  ...
}

APPROACH 2 (NEW!):
==================
Provide segment details:
{
  "cash_GL_segments": [
    {"segment_type_id": 1, "segment_code": "100"},
    {"segment_type_id": 2, "segment_code": "1010"}
  ],
  "cash_clearing_GL_segments": [
    {"segment_type_id": 1, "segment_code": "100"},
    {"segment_type_id": 2, "segment_code": "1020"}
  ],
  ...
}

BENEFITS:
=========
✓ No need to pre-create GL combinations
✓ System automatically finds existing or creates new combinations
✓ Same pattern as Invoice/Payment/Journal Entry APIs
✓ Maintains immutability of GL combinations (for audit integrity)
✓ Backward compatible - both approaches work!

VALIDATION:
===========
• Must provide EITHER combination ID OR segments (not both)
• At least one segment required if using segments approach
• Segments are validated (type and code must exist)
• Cannot mix approaches (e.g., ID for one, segments for other)

Press Ctrl+C to exit...
    """)
    
    main()
