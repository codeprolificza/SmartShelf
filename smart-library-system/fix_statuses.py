import psycopg2

password = input("PostgreSQL password: ")

conn = psycopg2.connect(
    host="127.0.0.1",
    database="library_system",
    user="postgres",
    password=password,
    port="5432"
)

cursor = conn.cursor()

# Create the required member statuses
cursor.execute("""
    INSERT INTO member_status (id, status_value)
    VALUES
        (1, 'ACTIVE'),
        (2, 'SUSPENDED'),
        (3, 'INACTIVE')
    ON CONFLICT (id) DO NOTHING;
""")

# Create the required reservation statuses
cursor.execute("""
    INSERT INTO reservation_status (id, status_value)
    VALUES
        (1, 'PENDING'),
        (2, 'CANCELLED'),
        (3, 'FULFILLED'),
        (4, 'ALLOCATED')
    ON CONFLICT (id) DO NOTHING;
""")

# Keep SERIAL sequences correct
cursor.execute("""
    SELECT setval(
        pg_get_serial_sequence('member_status', 'id'),
        COALESCE((SELECT MAX(id) FROM member_status), 1),
        true
    );
""")

cursor.execute("""
    SELECT setval(
        pg_get_serial_sequence('reservation_status', 'id'),
        COALESCE((SELECT MAX(id) FROM reservation_status), 1),
        true
    );
""")

conn.commit()

print()
print("SUCCESS!")
print("Member statuses and reservation statuses have been created.")

cursor.close()
conn.close()