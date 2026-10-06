import os
import psycopg2

from werkzeug.security import generate_password_hash


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db_connection():

    return psycopg2.connect(
        host="127.0.0.1",
        database="library_system",
        user="postgres",
        password=os.getenv("LIBRARY"),
        port="5432"
    )


# ============================================================
# DEFAULT ADMINISTRATORS
# ============================================================

DEFAULT_ADMINS = [

    {
        "first_name": "System",
        "last_name": "Administrator",
        "email": "10001@ufh.ac.za",
        "password": "Admin@12345"
    },

    {
        "first_name": "Library",
        "last_name": "Administrator",
        "email": "10002@ufh.ac.za",
        "password": "Admin@67890"
    }

]


# ============================================================
# CREATE ADMINS
# ============================================================

def create_default_admins():

    conn = get_db_connection()
    cursor = conn.cursor()

    try:

        for admin in DEFAULT_ADMINS:

            # --------------------------------------------
            # Check if the account already exists
            # --------------------------------------------

            cursor.execute(
                """
                SELECT id, role
                FROM member
                WHERE LOWER(email) = LOWER(%s);
                """,
                (admin["email"],)
            )

            existing = cursor.fetchone()


            if existing:

                print(
                    f"Account already exists: "
                    f"{admin['email']}"
                )

                continue


            # --------------------------------------------
            # Generate secure password hash
            # --------------------------------------------

            password_hash = generate_password_hash(
                admin["password"]
            )


            # --------------------------------------------
            # Insert administrator
            # --------------------------------------------

            cursor.execute(
                """
                INSERT INTO member
                (
                    first_name,
                    last_name,
                    email,
                    password_hash,
                    role,
                    faculty,
                    department,
                    programme,
                    active_status_id
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    'admin',
                    NULL,
                    NULL,
                    NULL,
                    1
                );
                """,
                (
                    admin["first_name"],
                    admin["last_name"],
                    admin["email"],
                    password_hash
                )
            )


            print(
                f"Created administrator: "
                f"{admin['email']}"
            )


        # --------------------------------------------
        # Save changes
        # --------------------------------------------

        conn.commit()

        print()
        print(
            "Default administrator setup completed."
        )


    except Exception as error:

        conn.rollback()

        print(
            "ERROR creating administrators:"
        )

        print(error)

        raise


    finally:

        cursor.close()
        conn.close()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    create_default_admins()