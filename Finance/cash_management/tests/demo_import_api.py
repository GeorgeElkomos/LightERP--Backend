"""
Test script to demonstrate Bank Statement Import API

This script shows how to use the import API with minimal parameters.
Just provide file and bank_account_id - everything else is auto-generated!
"""

import requests
import json

# Configuration
BASE_URL = "http://localhost:8000"
ACCESS_TOKEN = "your_access_token_here"  # Replace with actual token

# API endpoints
IMPORT_URL = f"{BASE_URL}/finance/cash/statements/import_statement/"
PREVIEW_URL = f"{BASE_URL}/finance/cash/statements/import_preview/"
DOWNLOAD_TEMPLATE_URL = f"{BASE_URL}/finance/cash/statements/download_template/"

# Headers
headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}"
}


def test_download_template():
    """Download the Excel template"""
    print("\n" + "="*60)
    print("1. DOWNLOADING TEMPLATE")
    print("="*60)
    
    response = requests.get(DOWNLOAD_TEMPLATE_URL, headers=headers)
    
    if response.status_code == 200:
        # Save template
        with open("statement_template.xlsx", "wb") as f:
            f.write(response.content)
        print("✓ Template downloaded: statement_template.xlsx")
        print("  Open it, fill with your data, and save")
    else:
        print(f"✗ Failed: {response.status_code}")
        print(response.json())


def test_preview_import(file_path, bank_account_id):
    """Preview import without saving"""
    print("\n" + "="*60)
    print("2. PREVIEWING IMPORT (Validation Only)")
    print("="*60)
    
    with open(file_path, 'rb') as f:
        files = {'file': f}
        data = {'bank_account_id': bank_account_id}
        
        response = requests.post(PREVIEW_URL, headers=headers, files=files, data=data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✓ Preview successful!")
        print(f"  Total lines: {result['total_lines']}")
        print(f"  Valid rows: {result['summary']['valid_rows']}")
        print(f"  Error rows: {result['summary']['error_rows']}")
        print(f"  Total debits: ${result['summary']['total_debits']}")
        print(f"  Total credits: ${result['summary']['total_credits']}")
        
        if result.get('errors'):
            print(f"\n⚠ Errors found:")
            for error in result['errors'][:5]:  # Show first 5
                print(f"    Row {error.get('row')}: {error.get('error')}")
        
        if result.get('statement_info'):
            info = result['statement_info']
            print(f"\n  Statement period: {info['from_date']} to {info['to_date']}")
        
        return True
    else:
        print(f"✗ Preview failed: {response.status_code}")
        print(response.json())
        return False


def test_import_statement(file_path, bank_account_id):
    """Import statement (full save to database)"""
    print("\n" + "="*60)
    print("3. IMPORTING STATEMENT (Save to Database)")
    print("="*60)
    
    with open(file_path, 'rb') as f:
        files = {'file': f}
        data = {
            'bank_account_id': bank_account_id,
            # NOTE: statement_number and statement_date are AUTO-GENERATED!
            # You can optionally provide them:
            # 'statement_number': 'STMT-2026-001',
            # 'statement_date': '2026-01-30',
        }
        
        response = requests.post(IMPORT_URL, headers=headers, files=files, data=data)
    
    if response.status_code == 201:
        result = response.json()
        print(f"✓ Import successful!")
        print(f"  Message: {result['message']}")
        
        statement = result['statement']
        print(f"\n  Statement created:")
        print(f"    ID: {statement['id']}")
        print(f"    Number: {statement['statement_number']} (AUTO-GENERATED)")
        print(f"    Date: {statement['statement_date']} (AUTO-GENERATED)")
        print(f"    Period: {statement['from_date']} to {statement['to_date']}")
        print(f"    Transactions: {statement['transaction_count']}")
        print(f"    Total Debits: ${statement['total_debits']}")
        print(f"    Total Credits: ${statement['total_credits']}")
        
        print(f"\n  Summary:")
        summary = result['summary']
        print(f"    Lines created: {result['lines_created']}")
        print(f"    Valid rows: {summary['valid_rows']}")
        print(f"    Error rows: {summary['error_rows']}")
        
        return True
    else:
        print(f"✗ Import failed: {response.status_code}")
        error_data = response.json()
        print(json.dumps(error_data, indent=2))
        return False


def main():
    """Run the complete import workflow"""
    print("\n" + "="*70)
    print(" BANK STATEMENT IMPORT API - TEST DEMONSTRATION")
    print("="*70)
    print("\nThis demonstrates the SIMPLIFIED import process:")
    print("  • Only 2 required fields: file + bank_account_id")
    print("  • statement_number is AUTO-GENERATED")
    print("  • statement_date is AUTO-GENERATED from transactions")
    print("="*70)
    
    # Configuration
    FILE_PATH = "bank_statement_sample.csv"  # or .xlsx
    BANK_ACCOUNT_ID = 1  # Change to your bank account ID
    
    # Step 1: Download template (optional)
    # test_download_template()
    
    # Step 2: Preview import (recommended - validates without saving)
    preview_success = test_preview_import(FILE_PATH, BANK_ACCOUNT_ID)
    
    if preview_success:
        # Step 3: Import statement (saves to database)
        import_success = test_import_statement(FILE_PATH, BANK_ACCOUNT_ID)
        
        if import_success:
            print("\n" + "="*70)
            print("✓ COMPLETE SUCCESS!")
            print("="*70)
            print("\nYour bank statement has been imported successfully.")
            print("Check your database for the new BankStatement and BankStatementLine records.")
    else:
        print("\n" + "="*70)
        print("⚠ PREVIEW FAILED - Fix errors before importing")
        print("="*70)


if __name__ == "__main__":
    # Quick usage guide
    print("""
QUICK START:
============

1. Get your access token:
   - Login to get JWT token
   - Update ACCESS_TOKEN variable above

2. Check bank account ID:
   - GET /finance/cash/accounts/
   - Note the account ID you want to import for

3. Prepare your file:
   - Use bank_statement_sample.csv (included)
   - Or download template and fill with your data

4. Run this script:
   python test_import_api.py

MINIMAL REQUEST:
================
Just 2 fields needed:
• file (CSV or Excel)
• bank_account_id

Everything else is auto-generated:
• statement_number → STMT-{account_id}-{date}-{counter}
• statement_date → latest transaction date from file

Press Ctrl+C to exit, or continue to run the demo...
    """)
    
    try:
        input("\nPress Enter to run demo (or Ctrl+C to exit)...")
        main()
    except KeyboardInterrupt:
        print("\n\nDemo cancelled.")
    except Exception as e:
        print(f"\n\n✗ Error: {e}")
        print("\nMake sure:")
        print("  1. Server is running (python manage.py runserver)")
        print("  2. ACCESS_TOKEN is set correctly")
        print("  3. bank_statement_sample.csv exists")
        print("  4. Bank account ID is valid")
