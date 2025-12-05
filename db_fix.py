import sqlite3
import re

db_path = "gpus.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

def clean_price(price_str):
    """
    Converts '$699', '699 USD', '249' to float 699.0, 249.0
    Returns None if the price is 'N/A' or 'Not Found'.
    """
    if not price_str or "N/A" in price_str or "Not Found" in price_str:
        return None
    
    # Remove everything except numbers and dots
    # This handles "$ 1,200.00" -> "1200.00"
    clean_str = re.sub(r'[^\d.]', '', price_str)
    
    try:
        return float(clean_str)
    except ValueError:
        return None

try:
    print("Starting migration...")
    
    # 1. Get the current list of columns so we don't lose any data
    cursor.execute("PRAGMA table_info(gpus)")
    columns_info = cursor.fetchall()
    column_names = [col[1] for col in columns_info]
    
    print(f"Detected columns: {column_names}")

    # 2. Rename the current table to a temporary name
    cursor.execute("ALTER TABLE gpus RENAME TO gpus_old")
    
    # 3. Construct the CREATE TABLE SQL dynamically
    # We force 'launch_prices', 'amazon_new_avg', and 'ebay_used_avg' to be REAL
    # All other columns default to TEXT unless specified otherwise
    
    float_cols = ['launch_prices']
    schema_parts = []
    
    for col in column_names:
        if col == 'name':
            schema_parts.append("name TEXT PRIMARY KEY")
        elif col in float_cols:
            schema_parts.append(f"{col} REAL")
        else:
            schema_parts.append(f"{col} TEXT")
            
    create_sql = f"CREATE TABLE gpus ({', '.join(schema_parts)})"
    cursor.execute(create_sql)
    print("Created new table with REAL types.")

    # 4. Copy and Clean the Data
    cursor.execute("SELECT * FROM gpus_old")
    rows = cursor.fetchall()
    
    # Find the index of the 'launch_prices' column
    try:
        price_index = column_names.index('launch_prices')
    except ValueError:
        print("Error: 'launch_prices' column not found!")
        raise

    cleaned_rows = []
    for row in rows:
        row_list = list(row)
        
        # specific cleaning for launch_price
        original_price = row_list[price_index]
        if isinstance(original_price, str):
            row_list[price_index] = clean_price(original_price)
            
        cleaned_rows.append(tuple(row_list))

    # 5. Insert cleaned data into the new table
    placeholders = ', '.join(['?'] * len(column_names))
    insert_sql = f"INSERT INTO gpus VALUES ({placeholders})"
    
    cursor.executemany(insert_sql, cleaned_rows)
    print(f"Migrated and cleaned {len(cleaned_rows)} rows.")

    # 6. Verify and Drop Old Table
    cursor.execute("SELECT COUNT(*) FROM gpus")
    new_count = cursor.fetchone()[0]
    
    if new_count == len(rows):
        cursor.execute("DROP TABLE gpus_old")
        conn.commit()
        print("Success! 'gpus_old' dropped. Migration complete.")
    else:
        print("Error: Row count mismatch. Rolling back.")
        conn.rollback()

except Exception as e:
    print(f"An error occurred: {e}")
    conn.rollback()

finally:
    conn.close()