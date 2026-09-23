import psycopg2
import os
conn = psycopg2.connect(
    host="127.0.0.1",
    database="library_system",
    user="postgres",
    password=os.getenv("LIBRARY_DB_PASSWORD"),
    port="5432"
)

cursor = conn.cursor()

# The original ER diagram's loan table only had loan_date and returned_date —
# no due date. Adding one here so we can track and display due dates properly.
cursor.execute("""
    ALTER TABLE loan ADD COLUMN IF NOT EXISTS due_date DATE;
""")

conn.commit()
print("loan table updated: 'due_date' column added.")

cursor.close()
conn.close()
