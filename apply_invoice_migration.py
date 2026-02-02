"""
Manually apply invoice_number migration to database.
"""
import sqlite3

def apply_migration():
    conn = sqlite3.connect('db.sqlite3')
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(invoice)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'invoice_number' not in columns:
            print("Adding invoice_number column...")
            cursor.execute('ALTER TABLE invoice ADD COLUMN invoice_number VARCHAR(50) NULL')
            conn.commit()
            print("✓ Column added")
        else:
            print("✓ Column already exists")
        
        # Backfill existing invoices
        cursor.execute('SELECT id, prefix_code FROM invoice WHERE invoice_number IS NULL')
        rows = cursor.fetchall()
        
        if rows:
            print(f"Backfilling {len(rows)} invoice numbers...")
            for invoice_id, prefix_code in rows:
                if prefix_code:
                    invoice_number = f'{prefix_code}-{invoice_id}'
                else:
                    invoice_number = str(invoice_id)
                cursor.execute('UPDATE invoice SET invoice_number = ? WHERE id = ?', 
                             (invoice_number, invoice_id))
            conn.commit()
            print(f"✓ Backfilled {len(rows)} invoice numbers")
        else:
            print("✓ No invoices to backfill")
        
        # Verify
        cursor.execute('SELECT COUNT(*) FROM invoice WHERE invoice_number IS NULL')
        null_count = cursor.fetchone()[0]
        
        if null_count > 0:
            print(f"⚠ Warning: {null_count} invoices still have NULL invoice_number")
        else:
            print("✓ All invoices have invoice_number")
            
    except Exception as e:
        print(f"✗ Error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    apply_migration()
