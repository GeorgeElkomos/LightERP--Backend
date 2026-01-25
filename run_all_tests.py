"""Test Summary Script - Runs all test modules and reports results"""
import subprocess
import sys
import re

# List of all test modules in the ERP system
TEST_MODULES = [
    'Finance.Invoice.tests.test_views_ap',
    'Finance.Invoice.tests.test_views_ar',
    'Finance.budget_control.tests',
    'Finance.BusinessPartner.tests',
    'Finance.cash_management.tests',
    'Finance.default_combinations.tests',
    'Finance.GL.tests',
    'Finance.payments.tests',
    'Finance.period.tests',
    'Finance.core.tests',
    'core.approval.tests',
    'core.job_roles.tests',
    'core.user_accounts.tests',
    'procurement.PR.tests',
    'procurement.po.tests',
    'procurement.receiving.tests',
    'procurement.catalog.tests',
    'procurement.tests',
]

def run_tests(module):
    """Run tests for a specific module and return results"""
    try:
        result = subprocess.run(
            ['python', 'manage.py', 'test', module, '--keepdb', '-v', '0'],
            capture_output=True,
            text=True,
            timeout=300
        )
        output = result.stdout + result.stderr
        
        # Extract test count
        match = re.search(r'Ran (\d+) test', output)
        if match:
            test_count = int(match.group(1))
            
            # Check for failures/errors
            if 'FAILED' in output or 'ERROR' in output:
                failure_match = re.search(r'failures=(\d+)', output)
                error_match = re.search(r'errors=(\d+)', output)
                failures = int(failure_match.group(1)) if failure_match else 0
                errors = int(error_match.group(1)) if error_match else 0
                return {
                    'module': module,
                    'total': test_count,
                    'passed': test_count - failures - errors,
                    'failed': failures + errors,
                    'status': 'FAILED'
                }
            else:
                return {
                    'module': module,
                    'total': test_count,
                    'passed': test_count,
                    'failed': 0,
                    'status': 'OK'
                }
        else:
            # No tests found
            return {
                'module': module,
                'total': 0,
                'passed': 0,
                'failed': 0,
                'status': 'NO TESTS'
            }
    except subprocess.TimeoutExpired:
        return {
            'module': module,
            'total': 0,
            'passed': 0,
            'failed': 0,
            'status': 'TIMEOUT'
        }
    except Exception as e:
        return {
            'module': module,
            'total': 0,
            'passed': 0,
            'failed': 0,
            'status': f'ERROR: {str(e)}'
        }

def main():
    print("=" * 80)
    print("ERP TEST SUITE SUMMARY")
    print("=" * 80)
    print()
    
    results = []
    total_tests = 0
    total_passed = 0
    total_failed = 0
    
    for module in TEST_MODULES:
        print(f"Running {module}...", end=' ', flush=True)
        result = run_tests(module)
        results.append(result)
        
        print(f"{result['status']} - {result['total']} tests")
        
        total_tests += result['total']
        total_passed += result['passed']
        total_failed += result['failed']
    
    print()
    print("=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {total_passed}")
    print(f"Failed: {total_failed}")
    print(f"Success Rate: {(total_passed/total_tests*100):.2f}%" if total_tests > 0 else "N/A")
    print()
    
    # Show detailed results
    print("Detailed Results:")
    print("-" * 80)
    for result in results:
        status_icon = "✅" if result['status'] == 'OK' else "❌"
        print(f"{status_icon} {result['module']:50} {result['passed']:4}/{result['total']:4} passed")
    
    print("=" * 80)
    
    # Return exit code based on failures
    sys.exit(0 if total_failed == 0 else 1)

if __name__ == '__main__':
    main()
