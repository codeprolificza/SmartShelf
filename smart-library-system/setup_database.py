import psycopg2
import os
# ================================================
# Sets up the complete SmartShelf schema + sample data directly
# from Python, on the exact same PostgreSQL server
# your Flask app will use (127.0.0.1:5432).
# ================================================

conn = psycopg2.connect(
    host="127.0.0.1",
    database="library_system",
    user="postgres",
    password=os.getenv("LIBRARY_DB_PASSWORD"),
    port="5432"
)

cursor = conn.cursor()

# Read and run schema.sql
with open("database/schema.sql", "r") as f:
    schema_sql = f.read()

cursor.execute(schema_sql)
conn.commit()
print("Complete SmartShelf schema created.")

# Read and run sample-data.sql
with open("database/sample-data.sql", "r") as f:
    sample_sql = f.read()

cursor.execute(sample_sql)
conn.commit()
print("Sample data inserted.")

cursor.close()
conn.close()

print("Done! Run test_db.py now to confirm the books show up.")
