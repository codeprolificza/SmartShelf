import psycopg2

# ================================================
# Test connection: Python -> PostgreSQL
# Fill in YOUR password below (the one you set
# when you first installed PostgreSQL).
# ================================================

conn = psycopg2.connect(
    host="127.0.0.1",
    database="library_system",
    user="postgres",
    password="library123",
    port="5432"
)

cursor = conn.cursor()

cursor.execute("SELECT id, title, copies_owned FROM book;")
books = cursor.fetchall()

print("Books in the database:")
for book in books:
    print(book)

cursor.close()
conn.close()
