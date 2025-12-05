import sqlite3

db_path = "gpus.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    print("Starting database migration...")

    # 1. Rename the existing table to a temporary name
    cursor.execute("ALTER TABLE gpus RENAME TO gpus_old")
    print("Renamed 'gpus' to 'gpus_old'.")

    # 2. Create the NEW table with 'name' as PRIMARY KEY
    # We include 'launch_prices' since you added it recently.
    create_table_sql = """
    CREATE TABLE gpus (
        name TEXT PRIMARY KEY,
        release_date TEXT,
        memory_amount TEXT,
        memory_type TEXT,
        memory_bus TEXT,
        chip TEXT,
        bus TEXT,
        gpu_clock TEXT,
        memory_clock TEXT,
        cores TEXT,
        tmus TEXT,
        rops TEXT,
        launch_prices TEXT
    );
    """
    cursor.execute(create_table_sql)
    print("Created new 'gpus' table with Primary Key.")

    # 3. Copy data from old to new, removing duplicates
    # We use 'GROUP BY name' to ensure we only grab one entry per GPU name.
    # We explicitly list columns to ensure alignment.
    copy_sql = """
    INSERT INTO gpus (
        name, release_date, memory_amount, memory_type, memory_bus, 
        chip, bus, gpu_clock, memory_clock, cores, tmus, rops, launch_prices
    )
    SELECT 
        name, release_date, memory_amount, memory_type, memory_bus, 
        chip, bus, gpu_clock, memory_clock, cores, tmus, rops, launch_prices
    FROM gpus_old
    GROUP BY name
    """
    cursor.execute(copy_sql)
    rows_moved = cursor.rowcount
    print(f"Migrated {rows_moved} unique rows to the new table.")

    # 4. Drop the old table
    cursor.execute("DROP TABLE gpus_old")
    print("Dropped 'gpus_old'.")

    # Commit the transaction
    conn.commit()
    print("Success! Database cleaned and Primary Key set.")

except Exception as e:
    print(f"An error occurred: {e}")
    print("Rolling back changes...")
    conn.rollback()

finally:
    conn.close()