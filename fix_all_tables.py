"""Find and fix ALL user_id=6 references in ALL tables"""
import sqlite3

conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]

total_fixed = 0
print("Scanning all tables for user_id=6 references...\n")

for table in tables:
    # Get table structure
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    
    # Check columns that might reference users
    user_columns = [col for col in columns if 'user_id' in col.lower() or col.endswith('_by_id')]
    
    for column in user_columns:
        try:
            # Check if any rows have user_id=6
            cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} = 6")
            count = cursor.fetchone()[0]
            
            if count > 0:
                print(f"Fixing {count} rows in {table}.{column}")
                cursor.execute(f"UPDATE {table} SET {column} = 1 WHERE {column} = 6")
                total_fixed += count
        except Exception as e:
            # Skip if query fails (e.g., column doesn't exist anymore)
            pass

conn.commit()
conn.close()

print(f"\n✓ Fixed {total_fixed} total foreign key references across all tables")
