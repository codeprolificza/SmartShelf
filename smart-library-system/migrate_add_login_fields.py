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

# Add email + password columns to member, if they don't already exist.
# (These weren't in the original ER diagram, but are needed for real login.)
cursor.execute("""
    ALTER TABLE member ADD COLUMN IF NOT EXISTS email VARCHAR(255) UNIQUE;
""")
cursor.execute("""
    ALTER TABLE member ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);
""")

cursor.execute("""
    ALTER TABLE member ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'student';
""")

conn.commit()
print("member table updated: email, password_hash, and role columns added (if not already present).")

cursor.close()
conn.close()
