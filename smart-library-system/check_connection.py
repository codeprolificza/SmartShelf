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

cursor.execute("SELECT current_database(), current_user, inet_server_addr(), inet_server_port(), version();")
info = cursor.fetchone()

print("Connected to database:", info[0])
print("Connected as user:", info[1])
print("Server address:", info[2])
print("Server port:", info[3])
print("PostgreSQL version:", info[4])

print()
print("Tables currently in the 'public' schema:")
cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public';")
tables = cursor.fetchall()

if tables:
    for t in tables:
        print(" -", t[0])
else:
    print(" (no tables found)")

cursor.close()
conn.close()
