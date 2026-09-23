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

# New table (extends the diagram): lets a student select categories
# they're interested in, used for real recommendations.
cursor.execute("""
    CREATE TABLE IF NOT EXISTS member_interest (
        member_id INTEGER REFERENCES member(id),
        category_id INTEGER REFERENCES category(id),
        PRIMARY KEY (member_id, category_id)
    );
""")

conn.commit()
print("member_interest table created (if it didn't already exist).")

cursor.close()
conn.close()
