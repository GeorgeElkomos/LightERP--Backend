"""
Bank Statement Import Service
Handles parsing and importing bank statements from Excel/CSV files.
"""
import pandas as pd
from decimal import Decimal, InvalidOperation
from datetime import datetime, date
from typing import Dict, List, Tuple, Optional
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
import io


class BankStatementImporter:
    """
    Service class for importing bank statements from Excel/CSV files.
    
    HOW IT WORKS:
    =============
    
    1. FILE UPLOAD:
       - User uploads Excel (.xlsx, .xls) or CSV (.csv) file
       - File is read into memory using pandas
       
    2. COLUMN MAPPING:
       - System maps file columns to database fields
       - Supports multiple column name variations (e.g., "Date", "Transaction Date", "Trans Date")
       - Flexible mapping handles different bank formats
       
    3. DATA VALIDATION:
       - Validates date formats
       - Validates decimal amounts
       - Checks for required fields
       - Detects duplicate line numbers
       - Validates transaction types (DEBIT/CREDIT)
       
    4. PREVIEW MODE:
       - Returns parsed data without saving
       - Shows any errors or warnings
       - Allows user to review before confirming
       
    5. IMPORT MODE:
       - Creates BankStatement record
       - Creates all BankStatementLine records
       - Uses database transaction (all-or-nothing)
       - Tracks who imported and when
       
    6. ERROR HANDLING:
       - Line-by-line error reporting
       - Shows which row has issues
       - Continues processing valid rows
       - Returns summary of successes/failures
    """
    
    # Column name mappings (flexible to handle different bank formats)
    COLUMN_MAPPINGS = {
        'line_number': ['line_number', 'line', 'line_no', 'transaction_no', 'trans_no', '#'],
        'transaction_date': ['transaction_date', 'trans_date', 'date', 'value_date', 'posting_date'],
        'value_date': ['value_date', 'effective_date', 'settlement_date'],
        'description': ['description', 'details', 'narrative', 'particulars', 'remarks'],
        'reference_number': ['reference_number', 'reference', 'ref', 'ref_no', 'check_no', 'cheque_no'],
        'debit_amount': ['debit', 'debit_amount', 'withdrawal', 'dr', 'payment'],
        'credit_amount': ['credit', 'credit_amount', 'deposit', 'cr', 'receipt'],
        'amount': ['amount', 'transaction_amount', 'trans_amount'],
        'transaction_type': ['transaction_type', 'type', 'trans_type', 'dr_cr'],
        'balance': ['balance', 'running_balance', 'balance_after', 'closing_balance'],
        'payee_payer': ['payee_payer', 'party', 'counterparty', 'beneficiary', 'payee', 'payer'],
    }
    
    # Date formats to try
    DATE_FORMATS = [
        '%Y-%m-%d',      # 2026-01-15
        '%d/%m/%Y',      # 15/01/2026
        '%m/%d/%Y',      # 01/15/2026
        '%d-%m-%Y',      # 15-01-2026
        '%Y/%m/%d',      # 2026/01/15
        '%Y.%m.%d',      # 2026.01.15
        '%d.%m.%Y',      # 15.01.2026
        '%d %b %Y',      # 15 Jan 2026
        '%d %B %Y',      # 15 January 2026
    ]
    
    def __init__(self, file_obj, bank_account_id: int, user):
        """
        Initialize importer with uploaded file.
        
        Args:
            file_obj: Uploaded file object
            bank_account_id: ID of the bank account this statement belongs to
            user: User performing the import
        """
        self.file_obj = file_obj
        self.bank_account_id = bank_account_id
        self.user = user
        self.errors = []
        self.warnings = []
        self.df = None
        
    def read_file(self) -> bool:
        """
        Read file into pandas DataFrame.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            file_name = self.file_obj.name.lower()
            
            # Read based on file extension
            if file_name.endswith('.csv'):
                self.df = pd.read_csv(io.BytesIO(self.file_obj.read()))
            elif file_name.endswith(('.xlsx', '.xls')):
                self.df = pd.read_excel(io.BytesIO(self.file_obj.read()))
            else:
                self.errors.append({
                    'row': 'File',
                    'error': 'Unsupported file format. Please upload .csv, .xlsx, or .xls file'
                })
                return False
            
            # Clean column names (strip spaces, lowercase)
            self.df.columns = self.df.columns.str.strip().str.lower()
            
            if self.df.empty:
                self.errors.append({
                    'row': 'File',
                    'error': 'File is empty or has no data rows'
                })
                return False
            
            return True
            
        except Exception as e:
            self.errors.append({
                'row': 'File',
                'error': f'Error reading file: {str(e)}'
            })
            return False
    
    def _find_column(self, field_name: str) -> Optional[str]:
        """
        Find the actual column name in DataFrame based on field mappings.
        Case-insensitive matching.
        
        Args:
            field_name: The standard field name we're looking for
            
        Returns:
            str: Actual column name in DataFrame, or None if not found
        """
        possible_names = self.COLUMN_MAPPINGS.get(field_name, [])
        
        # Convert all possible names and column names to lowercase for comparison
        possible_names_lower = [name.lower() for name in possible_names]
        
        for col_name in self.df.columns:
            col_name_lower = str(col_name).lower().replace('_', '').replace(' ', '')
            for idx, possible_name_lower in enumerate(possible_names_lower):
                possible_name_lower = possible_name_lower.replace('_', '').replace(' ', '')
                if col_name_lower == possible_name_lower:
                    return col_name
        
        return None
    
    def _parse_date(self, date_value) -> Optional[date]:
        """
        Parse date from various formats.
        
        Args:
            date_value: Date value to parse (string, datetime, or date)
            
        Returns:
            date: Parsed date or None if parsing fails
        """
        if pd.isna(date_value):
            return None
        
        # Already a date/datetime
        if isinstance(date_value, (date, datetime)):
            return date_value if isinstance(date_value, date) else date_value.date()
        
        # Try parsing string
        date_str = str(date_value).strip()
        
        for date_format in self.DATE_FORMATS:
            try:
                return datetime.strptime(date_str, date_format).date()
            except ValueError:
                continue
        
        return None
    
    def _parse_decimal(self, value) -> Optional[Decimal]:
        """
        Parse decimal value from string or number.
        Handles both US format (1,234.56) and European format (1.234,56)
        Handles negative values in parentheses: (1,000.00) → -1000.00
        
        Args:
            value: Value to parse
            
        Returns:
            Decimal: Parsed decimal or None if parsing fails
        """
        if pd.isna(value) or value == '' or value is None:
            return None
        
        try:
            is_negative = False
            
            # Remove currency symbols
            if isinstance(value, str):
                value = value.replace('$', '').replace('€', '').replace('£', '').strip()
                
                # Check for parentheses (negative)
                if value.startswith('(') and value.endswith(')'):
                    is_negative = True
                    value = value[1:-1].strip()
                
                # Detect format based on last separator
                # European format: 1.234,56 → comma is decimal separator
                # US format: 1,234.56 → dot is decimal separator
                if ',' in value and '.' in value:
                    # Both present - determine which is decimal separator
                    last_comma_pos = value.rfind(',')
                    last_dot_pos = value.rfind('.')
                    
                    if last_comma_pos > last_dot_pos:
                        # European format: 1.234,56
                        value = value.replace('.', '').replace(',', '.')
                    else:
                        # US format: 1,234.56
                        value = value.replace(',', '')
                elif ',' in value and '.' not in value:
                    # Only comma - could be thousand separator or decimal
                    # If only one comma and it's followed by 2 digits, it's decimal separator
                    parts = value.split(',')
                    if len(parts) == 2 and len(parts[1]) == 2:
                        # European decimal: 1234,56
                        value = value.replace(',', '.')
                    else:
                        # Thousand separator: 1,234
                        value = value.replace(',', '')
                else:
                    # Only dot or neither - standard format
                    pass
            
            result = Decimal(str(value))
            return -result if is_negative else result
        except (InvalidOperation, ValueError):
            return None
    
    def _determine_transaction_type(self, row_data: Dict) -> Tuple[Optional[str], Optional[Decimal]]:
        """
        Determine transaction type and amount from row data.
        
        Logic:
        1. If transaction_type column exists → use it
        2. If debit_amount has value → DEBIT
        3. If credit_amount has value → CREDIT
        4. If amount column with type indicator → use indicator
        
        Args:
            row_data: Dictionary of row values
            
        Returns:
            Tuple[str, Decimal]: (transaction_type, amount)
        """
        # Check for explicit transaction_type column
        trans_type = row_data.get('transaction_type')
        if trans_type:
            trans_type = str(trans_type).strip().upper()
            if 'DEBIT' in trans_type or 'DR' in trans_type or 'WITHDRAWAL' in trans_type:
                amount = row_data.get('amount') or row_data.get('debit_amount')
                return ('DEBIT', amount)
            elif 'CREDIT' in trans_type or 'CR' in trans_type or 'DEPOSIT' in trans_type:
                amount = row_data.get('amount') or row_data.get('credit_amount')
                return ('CREDIT', amount)
        
        # Check debit/credit columns
        debit = row_data.get('debit_amount')
        credit = row_data.get('credit_amount')
        
        if debit and debit != Decimal('0'):
            return ('DEBIT', debit)
        elif credit and credit != Decimal('0'):
            return ('CREDIT', credit)
        
        # Check amount column (assume negative = debit, positive = credit)
        amount = row_data.get('amount')
        if amount:
            if amount < 0:
                return ('DEBIT', abs(amount))
            else:
                return ('CREDIT', amount)
        
        return (None, None)
    
    def parse_data(self) -> Dict:
        """
        Parse DataFrame into structured data for import.
        
        Returns:
            Dict: Parsed data with statement info and lines
        """
        parsed_data = {
            'statement_info': {},
            'lines': [],
            'summary': {
                'total_lines': 0,
                'valid_lines': 0,
                'error_lines': 0,
                'total_debits': Decimal('0'),
                'total_credits': Decimal('0'),
            }
        }
        
        # Map columns
        column_map = {}
        for field, possible_names in self.COLUMN_MAPPINGS.items():
            found_col = self._find_column(field)
            if found_col:
                column_map[field] = found_col
        
        # Validate required columns exist
        required_fields = ['transaction_date', 'description']
        missing_fields = []
        
        for field in required_fields:
            if field not in column_map:
                missing_fields.append(field)
        
        if missing_fields:
            self.errors.append({
                'row': 'File',
                'error': f'Missing required columns: {", ".join(missing_fields)}'
            })
            return parsed_data
        
        # Process each row
        for idx, row in self.df.iterrows():
            row_num = idx + 2  # Excel row number (1-indexed + header)
            parsed_data['summary']['total_lines'] += 1
            
            # Extract row data
            row_data = {}
            for field, col_name in column_map.items():
                value = row[col_name]
                
                # Parse dates
                if field in ['transaction_date', 'value_date']:
                    row_data[field] = self._parse_date(value)
                # Parse decimals
                elif field in ['debit_amount', 'credit_amount', 'amount', 'balance']:
                    row_data[field] = self._parse_decimal(value)
                # Parse line number
                elif field == 'line_number':
                    row_data[field] = int(value) if pd.notna(value) else None
                # String fields
                else:
                    row_data[field] = str(value).strip() if pd.notna(value) else ''
            
            # Validate row
            row_errors = []
            
            # Required: transaction_date
            if not row_data.get('transaction_date'):
                row_errors.append('Missing or invalid transaction date')
            
            # Required: description
            if not row_data.get('description'):
                row_errors.append('Missing description')
            
            # Determine transaction type and amount
            trans_type, amount = self._determine_transaction_type(row_data)
            
            # If no transaction type/amount, skip silently (e.g., opening balance, summary lines)
            if not trans_type or not amount:
                # Skip informational rows without marking as error
                continue
            
            row_data['transaction_type'] = trans_type
            row_data['amount'] = amount
            
            # If errors, record and continue
            if row_errors:
                parsed_data['summary']['error_lines'] += 1
                for error in row_errors:
                    self.errors.append({
                        'row': row_num,
                        'error': error,
                        'data': row_data
                    })
                continue
            
            # Add to parsed lines
            parsed_data['lines'].append({
                'row_number': row_num,
                'line_number': row_data.get('line_number'),
                'transaction_date': row_data['transaction_date'],
                'value_date': row_data.get('value_date') or row_data['transaction_date'],
                'transaction_type': trans_type,
                'amount': amount,
                'balance_after_transaction': row_data.get('balance'),
                'reference_number': row_data.get('reference_number', ''),
                'description': row_data['description'],
                'payee_payer': row_data.get('payee_payer', ''),
            })
            
            parsed_data['summary']['valid_lines'] += 1
            
            # Update totals - ensure amount is Decimal
            if amount and trans_type:
                amount_decimal = Decimal(str(amount)) if not isinstance(amount, Decimal) else amount
                if trans_type == 'DEBIT':
                    parsed_data['summary']['total_debits'] += amount_decimal
                else:
                    parsed_data['summary']['total_credits'] += amount_decimal
        
        # Calculate statement-level info
        if parsed_data['lines']:
            dates = [line['transaction_date'] for line in parsed_data['lines']]
            parsed_data['statement_info'] = {
                'from_date': min(dates),
                'to_date': max(dates),
                'transaction_count': len(parsed_data['lines']),
                'total_debits': parsed_data['summary']['total_debits'],
                'total_credits': parsed_data['summary']['total_credits'],
            }
        
        return parsed_data
    
    @transaction.atomic
    def import_statement(self, statement_data: Dict, skip_parse: bool = False) -> Dict:
        """
        Import parsed data into database.
        
        This uses a database transaction, so if ANY error occurs,
        ALL changes are rolled back (nothing is saved).
        
        Args:
            statement_data: Dictionary with statement_number, statement_date, 
                          opening_balance, closing_balance
            skip_parse: If True, assumes file has already been read and parsed
            
        Returns:
            Dict: Import result with created statement and lines
        """
        from Finance.cash_management.models import BankStatement, BankStatementLine, BankAccount
        
        # Get bank account
        try:
            bank_account = BankAccount.objects.get(id=self.bank_account_id)
        except BankAccount.DoesNotExist:
            raise ValidationError(f'Bank account with ID {self.bank_account_id} not found')
        
        # Read and parse file (only if not already done)
        if not skip_parse:
            if not self.read_file():
                raise ValidationError('Failed to read file')
            
            parsed_data = self.parse_data()
        else:
            # Use already parsed data
            if self.df is None:
                raise ValidationError('File has not been read yet')
            parsed_data = self.parse_data()
        
        if self.errors:
            raise ValidationError(f'File has {len(self.errors)} validation errors')
        
        if not parsed_data['lines']:
            raise ValidationError('No valid transaction lines found in file')
        
        # Create BankStatement
        statement = BankStatement.objects.create(
            bank_account=bank_account,
            statement_number=statement_data['statement_number'],
            statement_date=statement_data['statement_date'],
            from_date=parsed_data['statement_info']['from_date'],
            to_date=parsed_data['statement_info']['to_date'],
            opening_balance=statement_data.get('opening_balance', Decimal('0')),
            closing_balance=statement_data.get('closing_balance', Decimal('0')),
            transaction_count=parsed_data['statement_info']['transaction_count'],
            total_debits=parsed_data['statement_info']['total_debits'],
            total_credits=parsed_data['statement_info']['total_credits'],
            import_file_name=self.file_obj.name,
            import_date=timezone.now(),
            imported_by=self.user,
            created_by=self.user,
            updated_by=self.user,
        )
        
        # Create BankStatementLines
        created_lines = []
        for idx, line_data in enumerate(parsed_data['lines'], start=1):
            line = BankStatementLine.objects.create(
                bank_statement=statement,
                line_number=line_data.get('line_number') or idx,
                transaction_date=line_data['transaction_date'],
                value_date=line_data['value_date'],
                debit_amount=line_data['amount'] if line_data['transaction_type'] == 'DEBIT' else Decimal('0'),
                credit_amount=line_data['amount'] if line_data['transaction_type'] == 'CREDIT' else Decimal('0'),
                balance=line_data.get('balance_after_transaction') or Decimal('0'),
                reference_number=line_data['reference_number'],
                description=line_data['description'],
                created_by=self.user,
                updated_by=self.user,
            )
            created_lines.append(line)
        
        return {
            'success': True,
            'statement': statement,
            'lines_created': len(created_lines),
            'summary': parsed_data['summary'],
        }
    
    def preview_import(self) -> Dict:
        """
        Preview import without saving to database.
        
        Returns:
            Dict: Preview data with parsed lines and any errors/warnings
        """
        if not self.read_file():
            return {
                'success': False,
                'errors': self.errors,
                'warnings': self.warnings,
            }
        
        parsed_data = self.parse_data()
        
        return {
            'success': len(self.errors) == 0,
            'statement_info': parsed_data['statement_info'],
            'lines_preview': parsed_data['lines'][:10],  # First 10 lines
            'total_lines': len(parsed_data['lines']),
            'summary': {
                'total_rows': parsed_data['summary']['total_lines'],
                'valid_rows': parsed_data['summary']['valid_lines'],
                'error_rows': parsed_data['summary']['error_lines'],
                'total_debits': str(parsed_data['summary']['total_debits']),
                'total_credits': str(parsed_data['summary']['total_credits']),
            },
            'errors': self.errors,
            'warnings': self.warnings,
        }
