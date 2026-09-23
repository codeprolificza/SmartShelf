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

# Extends the original ER diagram: the 'member' table didn't distinguish
# roles, so we add one here to support Student / Staff / Admin accounts
# all in the same table (they still share loan/reservation/fine history).
cursor.execute("""
    ALTER TABLE member ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'student';
""")

conn.commit()
print("member table updated: 'role' column added (defaults to 'student').")

cursor.close()
conn.close()
