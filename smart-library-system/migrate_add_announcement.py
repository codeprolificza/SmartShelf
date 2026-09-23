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

# New table (extends the original diagram): lets Admin post real
# announcements shown on the homepage, instead of hardcoded text.
cursor.execute("""
    CREATE TABLE IF NOT EXISTS announcement (
        id SERIAL PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        body TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_by INTEGER REFERENCES member(id)
    );
""")

conn.commit()
print("announcement table created (if it didn't already exist).")

cursor.close()
conn.close()
