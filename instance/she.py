import sqlite3
import sys
from pathlib import Path

def extract_schema(db_path, output_file='schema.txt'):
    """
    Extract schema from SQLite database and save it to a text file.
    
    Args:
        db_path (str): Path to the SQLite database file
        output_file (str): Path to the output text file (default: schema.txt)
    """
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get list of all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        with open(output_file, 'w') as f:
            f.write(f"Schema for database: {db_path}\n")
            f.write("=" * 50 + "\n\n")
            
            # Iterate through each table
            for table in tables:
                table_name = table[0]
                f.write(f"Table: {table_name}\n")
                f.write("-" * 30 + "\n")
                
                # Get CREATE TABLE statement
                cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}';")
                create_stmt = cursor.fetchone()[0]
                f.write(f"{create_stmt};\n\n")
                
                # Get table info (column details)
                cursor.execute(f"PRAGMA table_info({table_name});")
                columns = cursor.fetchall()
                
                f.write("Columns:\n")
                for col in columns:
                    col_id, name, type_, notnull, default, pk = col
                    constraints = []
                    if pk:
                        constraints.append("PRIMARY KEY")
                    if notnull:
                        constraints.append("NOT NULL")
                    if default is not None:
                        constraints.append(f"DEFAULT {default}")
                    
                    constraints_str = " | ".join(constraints)
                    f.write(f"  - {name}: {type_}" + (f" ({constraints_str})" if constraints_str else "") + "\n")
                
                # Get index information
                cursor.execute(f"SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='{table_name}';")
                indexes = cursor.fetchall()
                
                if indexes:
                    f.write("\nIndexes:\n")
                    for idx_name, idx_sql in indexes:
                        f.write(f"  - {idx_sql};\n")
                
                f.write("\n" + "=" * 50 + "\n\n")
        
        print(f"Schema has been extracted to {output_file}")
        
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script.py <database_path> [output_file]")
        sys.exit(1)
    
    db_path = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'schema.txt'
    
    if not Path(db_path).exists():
        print(f"Error: Database file '{db_path}' not found!")
        sys.exit(1)
    
    extract_schema(db_path, output_file)