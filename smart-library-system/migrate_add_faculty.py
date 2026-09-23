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

# Adds a faculty field for students (not in the original ER diagram —
# this is an extension the team asked for).
cursor.execute("""
    ALTER TABLE member ADD COLUMN IF NOT EXISTS faculty VARCHAR(100);
""")

conn.commit()
print("member table updated: 'faculty' column added.")

cursor.close()
conn.close()
