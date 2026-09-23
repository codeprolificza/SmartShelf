from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import psycopg2
import re
import os
from werkzeug.security import generate_password_hash, check_password_hash
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")  # needed for login sessions


def get_db_connection():
    return psycopg2.connect(
        host="127.0.0.1",
        database="library_system",
        user="postgres",
        password=os.getenv("LIBRARY_DB_PASSWORD"),
        port="5432"
    )


EMAIL_PATTERNS = {
    "student": r'^\d{9}@ufh\.ac\.za$',
    "staff": r'^\d{5}@ufh\.ac\.za$',
    "admin": r'^\d{5}@ufh\.ac\.za$'
}

def log_action(member_id, action, details=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO audit_log
        (member_id, action, details)
        VALUES (%s, %s, %s);
    """, (
        member_id,
        action,
        details
    ))

    conn.commit()

    cursor.close()
    conn.close()

@app.route('/')
def home():
    featured_books = fetch_books()[:4]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT
        b.id,
        b.title,
        STRING_AGG(
            DISTINCT a.first_name || ' ' || a.last_name,
            ', '
        ) AS author,
        GREATEST(
            b.copies_owned
            - COUNT(DISTINCT l.id) FILTER (
                WHERE l.returned_date IS NULL
            ),
            0
        ) AS copies_available
    FROM book b
    LEFT JOIN book_author ba
        ON b.id = ba.book_id
    LEFT JOIN author a
        ON ba.author_id = a.id
    LEFT JOIN loan l
        ON b.id = l.book_id
    GROUP BY b.id, b.copies_owned
    ORDER BY b.id DESC
    LIMIT 2;
""")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    new_arrivals = [{"id": r[0], "title": r[1], "author": r[2] if r[2] else "Unknown", "copies": r[3]} for r in rows]

    return render_template('index.html', featured_books=featured_books, new_arrivals=new_arrivals)


@app.route('/account')
def account():
    """Sends a logged-in user to the dashboard for their real role,
    or to Login if nobody is signed in."""
    role = session.get('role')
    redirect_map = {
        "student": "/dashboard",
        "staff": "/dashboard-staff",
        "admin": "/dashboard-admin"
    }
    return redirect(redirect_map.get(role, "/login"))


@app.route('/recommend-purchase')
def recommend_purchase():
    return render_template('recommend-purchase.html')

@app.route('/api/recommend-purchase', methods=['POST'])
def submit_purchase_request():

    if 'member_id' not in session:
        return jsonify({
            "error": "Please log in to recommend a purchase."
        }), 401

    if session.get('role') != 'student':
        return jsonify({
            "error": "Only students can recommend a purchase."
        }), 403

    data = request.get_json()

    title = data.get('title', '').strip()
    author = data.get('author', '').strip()
    reason = data.get('reason', '').strip()

    if not title:
        return jsonify({
            "error": "Book title is required."
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO purchase_request
        (member_id, title, author, reason)
        VALUES (%s, %s, %s, %s);
    """, (
        session['member_id'],
        title,
        author,
        reason
    ))

    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({
        "message": "Your book purchase request has been submitted successfully."
    }), 200

@app.route('/api/pay-fine', methods=['POST'])
def pay_fine():

    # Student must be logged in
    if 'member_id' not in session:
        return jsonify({
            "error": "Please log in first."
        }), 401

    # Only students can pay fines
    if session.get('role') != 'student':
        return jsonify({
            "error": "Only students can pay fines."
        }), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:

        # Calculate total fines
        cursor.execute("""
            SELECT COALESCE(SUM(fine_amount), 0)
            FROM fine
            WHERE member_id = %s;
        """, (session['member_id'],))

        total_fines = cursor.fetchone()[0]

        # Calculate total payments already made
        cursor.execute("""
            SELECT COALESCE(SUM(payment_amount), 0)
            FROM fine_payment
            WHERE member_id = %s;
        """, (session['member_id'],))

        total_paid = cursor.fetchone()[0]

        # Calculate outstanding balance
        outstanding = total_fines - total_paid

        if outstanding <= 0:

            conn.rollback()

            return jsonify({
                "message": "You have no outstanding fines."
            }), 200

        # Record the payment
        cursor.execute("""
            INSERT INTO fine_payment
            (
                member_id,
                payment_date,
                payment_amount
            )
            VALUES (%s, CURRENT_DATE, %s);
        """, (
            session['member_id'],
            outstanding
        ))

        conn.commit()

        return jsonify({
            "message": f"Fine payment of R{outstanding:.2f} was successful."
        }), 200

    except Exception:

        conn.rollback()

        return jsonify({
            "error": "Could not process the fine payment."
        }), 500

    finally:

        cursor.close()
        conn.close()

@app.route('/forgot-password')
def forgot_password():
    return render_template('forgot-password.html')

@app.route('/reset-password/<token>')
def reset_password(token):
    return render_template('reset-password.html', token=token)

@app.route('/api/reset-password', methods=['POST'])
def reset_password_api():
    data = request.get_json()

    token = data.get('token', '').strip()
    new_password = data.get('password', '')

    if not token:
        return jsonify({"error": "Invalid reset token."}), 400

    if len(new_password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, member_id
        FROM password_reset
        WHERE reset_token = %s
        AND used = FALSE
        AND expires_at > CURRENT_TIMESTAMP;
    """, (token,))

    reset_record = cursor.fetchone()

    if not reset_record:
        cursor.close()
        conn.close()
        return jsonify({
            "error": "This reset link is invalid or has expired."
        }), 400

    reset_id, member_id = reset_record

    password_hash = generate_password_hash(new_password)

    cursor.execute("""
        UPDATE member
        SET password_hash = %s
        WHERE id = %s;
    """, (password_hash, member_id))

    cursor.execute("""
        UPDATE password_reset
        SET used = TRUE
        WHERE id = %s;
    """, (reset_id,))

    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({
        "message": "Your password has been reset successfully."
    })

@app.route('/api/forgot-password', methods=['POST'])
def request_password_reset():
    data = request.get_json()

    email = data.get('email', '').strip().lower()

    if not email.endswith('@ufh.ac.za'):
        return jsonify({
            "error": "Please use your @ufh.ac.za email address."
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM member
        WHERE LOWER(email) = %s;
    """, (email,))

    member = cursor.fetchone()

    if member:
        import secrets
        from datetime import datetime, timedelta

        reset_token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(minutes=30)

        cursor.execute("""
            INSERT INTO password_reset
            (member_id, reset_token, expires_at)
            VALUES (%s, %s, %s);
        """, (member[0], reset_token, expires_at))

        conn.commit()

    cursor.close()
    conn.close()

    return jsonify({
        "message": "If an account exists for that email, a password reset link has been sent."
    })

@app.route('/interests', methods=['GET'])
def interests():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, category_name FROM category ORDER BY category_name;")
    all_categories = [{"id": r[0], "name": r[1]} for r in cursor.fetchall()]

    cursor.execute("SELECT category_id FROM member_interest WHERE member_id = %s;", (session['member_id'],))
    selected_ids = set(r[0] for r in cursor.fetchall())

    cursor.close()
    conn.close()

    return render_template('interests.html', all_categories=all_categories, selected_ids=selected_ids)


@app.route('/api/save-interests', methods=['POST'])
def save_interests():
    if session.get('role') != 'student':
        return jsonify({"error": "Please log in as a student."}), 401

    data = request.get_json()
    category_ids = data.get('category_ids', [])

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM member_interest WHERE member_id = %s;", (session['member_id'],))
    for cat_id in category_ids:
        cursor.execute("""
            INSERT INTO member_interest (member_id, category_id) VALUES (%s, %s)
            ON CONFLICT DO NOTHING;
        """, (session['member_id'], cat_id))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Interests saved."})


@app.route('/recommendations')
def recommendations():

    if session.get('role') != 'student':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Rule-based recommendations:
    # 1. Student interests
    # 2. Categories from previously borrowed books
    # 3. Real book ratings from other library users
    #
    # No AI and no fake match percentages are used.

    cursor.execute("""
        SELECT
            b.id,
            b.title,

            STRING_AGG(
                DISTINCT a.first_name || ' ' || a.last_name,
                ', '
            ) AS author,

            c.category_name,

            COALESCE(rs.average_rating, 0) AS average_rating,
            COALESCE(rs.review_count, 0) AS review_count,

            CASE

                WHEN mi.category_id IS NOT NULL
                     AND prev.category_id IS NOT NULL
                     AND COALESCE(rs.average_rating, 0) >= 4
                THEN 'Matches your interests, past borrowing and is highly rated'

                WHEN mi.category_id IS NOT NULL
                     AND prev.category_id IS NOT NULL
                THEN 'Matches your interests and past borrowing'

                WHEN mi.category_id IS NOT NULL
                     AND COALESCE(rs.average_rating, 0) >= 4
                THEN 'Matches your interests and is highly rated'

                WHEN prev.category_id IS NOT NULL
                     AND COALESCE(rs.average_rating, 0) >= 4
                THEN 'Based on your borrowing history and its high rating'

                WHEN mi.category_id IS NOT NULL
                THEN 'Because you are interested in ' || c.category_name

                WHEN prev.category_id IS NOT NULL
                THEN 'Because you borrowed a book in ' || c.category_name

                WHEN COALESCE(rs.average_rating, 0) >= 4
                THEN 'Highly rated by library users'

                ELSE 'Recommended from library activity'

            END AS reason,

            (
                CASE
                    WHEN mi.category_id IS NOT NULL THEN 3
                    ELSE 0
                END
                +
                CASE
                    WHEN prev.category_id IS NOT NULL THEN 2
                    ELSE 0
                END
                +
                CASE
                    WHEN COALESCE(rs.average_rating, 0) >= 4 THEN 2
                    ELSE 0
                END
                +
                CASE
                    WHEN COALESCE(rs.review_count, 0) > 0 THEN 1
                    ELSE 0
                END
            ) AS recommendation_score

        FROM book b

        LEFT JOIN category c
            ON b.category_id = c.id

        LEFT JOIN book_author ba
            ON b.id = ba.book_id

        LEFT JOIN author a
            ON ba.author_id = a.id

        LEFT JOIN member_interest mi
            ON mi.category_id = b.category_id
            AND mi.member_id = %s

        LEFT JOIN (
            SELECT DISTINCT bk.category_id
            FROM loan l2
            JOIN book bk
                ON l2.book_id = bk.id
            WHERE l2.member_id = %s
        ) prev
            ON prev.category_id = b.category_id

        LEFT JOIN (
            SELECT
                book_id,
                ROUND(AVG(rating), 1) AS average_rating,
                COUNT(*) AS review_count
            FROM book_review
            GROUP BY book_id
        ) rs
            ON rs.book_id = b.id

        WHERE b.id NOT IN (
            SELECT book_id
            FROM loan
            WHERE member_id = %s
            AND returned_date IS NULL
        )

        GROUP BY
            b.id,
            b.title,
            c.category_name,
            mi.category_id,
            prev.category_id,
            rs.average_rating,
            rs.review_count

        HAVING
            mi.category_id IS NOT NULL
            OR prev.category_id IS NOT NULL
            OR COALESCE(rs.average_rating, 0) >= 4

        ORDER BY
            recommendation_score DESC,
            average_rating DESC,
            review_count DESC,
            b.title

        LIMIT 8;
    """, (
        session['member_id'],
        session['member_id'],
        session['member_id']
    ))

    rows = cursor.fetchall()

    # Categories the student explicitly selected
    cursor.execute("""
        SELECT c.category_name
        FROM member_interest mi
        JOIN category c
            ON mi.category_id = c.id
        WHERE mi.member_id = %s
        ORDER BY c.category_name;
    """, (session['member_id'],))

    based_on = [r[0] for r in cursor.fetchall()]

    cursor.close()
    conn.close()

    recommended_books = []

    for row in rows:

        (
            book_id,
            title,
            author,
            category,
            average_rating,
            review_count,
            reason,
            recommendation_score
        ) = row

        recommended_books.append({
            "id": book_id,
            "title": title,
            "author": author if author else "Unknown",
            "category": category if category else "Uncategorized",
            "average_rating": float(average_rating),
            "review_count": review_count,
            "reason": reason
        })

    return render_template(
        'recommendations.html',
        recommended_books=recommended_books,
        based_on=based_on
    )

# ================================================
# RESERVE A BOOK
# ================================================

@app.route('/reserve', methods=['POST'])
def reserve_book():

    if 'member_id' not in session:
        return jsonify({
            "error": "Please log in to reserve this book."
        }), 401

    if session.get('role') != 'student':
        return jsonify({
            "error": "Only students can reserve books."
        }), 403

    data = request.get_json()
    book_id = data.get('book_id')

    if not book_id:
        return jsonify({"error": "Book ID is required."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check that the book exists
    cursor.execute("""
        SELECT id, title
        FROM book
        WHERE id = %s;
    """, (book_id,))

    book = cursor.fetchone()

    if not book:
        cursor.close()
        conn.close()
        return jsonify({"error": "Book not found."}), 404

    # Make sure all copies are currently unavailable
    cursor.execute("""
        SELECT copy_id
        FROM book_copy
        WHERE book_id = %s
        AND copy_status = 'AVAILABLE'
        LIMIT 1;
    """, (book_id,))

    available_copy = cursor.fetchone()

    if available_copy:
        cursor.close()
        conn.close()
        return jsonify({
            "error": "A copy of this book is currently available. You can borrow it instead."
        }), 400

    # Check for an existing active reservation
    cursor.execute("""
        SELECT id
        FROM reservation
        WHERE book_id = %s
        AND member_id = %s
        AND reservation_status_id IN (1, 4);
    """, (book_id, session['member_id']))

    existing_reservation = cursor.fetchone()

    if existing_reservation:
        cursor.close()
        conn.close()
        return jsonify({
            "error": "You already have an active reservation for this book."
        }), 400

    # Find the next queue position
    cursor.execute("""
        SELECT COALESCE(MAX(queue_position), 0) + 1
        FROM reservation
        WHERE book_id = %s
        AND reservation_status_id = 1;
    """, (book_id,))

    queue_position = cursor.fetchone()[0]

       # Create reservation
    cursor.execute("""
        INSERT INTO reservation
        (
            book_id,
            member_id,
            reservation_date,
            reservation_status_id,
            queue_position
        )
        VALUES (%s, %s, CURRENT_DATE, 1, %s);
    """, (
        book_id,
        session['member_id'],
        queue_position
    ))

    # Record the reservation action in the audit log
    log_action(
        session['member_id'],
        "RESERVATION",
        f"Student reserved '{book[1]}' (queue position {queue_position})."
    )

    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({
        "message": f"Reservation created successfully. You are number {queue_position} in the queue."
    })

@app.route('/borrowed')
def borrowed():

    if session.get('role') != 'student':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get the student's borrowed books
    cursor.execute("""
        SELECT
            l.id,
            b.title,
            l.loan_date,
            l.due_date,
            l.returned_date
        FROM loan l
        JOIN book b
            ON l.book_id = b.id
        WHERE l.member_id = %s
        ORDER BY l.loan_date DESC;
    """, (session['member_id'],))

    loan_rows = cursor.fetchall()

    # Get the student's reservations
    cursor.execute("""
        SELECT
            r.id,
            b.title,
            r.reservation_date,
            r.queue_position,
            rs.status_value,
            r.expires_at
        FROM reservation r
        JOIN book b
            ON r.book_id = b.id
        JOIN reservation_status rs
            ON r.reservation_status_id = rs.id
        WHERE r.member_id = %s
        ORDER BY r.reservation_date DESC, r.id DESC;
    """, (session['member_id'],))

    reservation_rows = cursor.fetchall()

    cursor.close()
    conn.close()

    from datetime import date

    # Prepare borrowed-book history
    history = []

    for row in loan_rows:

        loan_id, title, loan_date, due_date, returned_date = row

        if returned_date:
            status = "Returned"

        elif due_date and due_date < date.today():
            status = "Overdue"

        else:
            status = "Currently Out"

        history.append({
            "loan_id": loan_id,
            "title": title,
            "loan_date": loan_date.strftime("%d %b %Y") if loan_date else "",
            "due_date": due_date.strftime("%d %b %Y") if due_date else "-",
            "status": status
        })

    # Prepare reservation information
    reservations = []

    for row in reservation_rows:

        reservation_id, title, reservation_date, queue_position, status, expires_at = row

        reservations.append({
            "reservation_id": reservation_id,
            "title": title,
            "reservation_date": reservation_date.strftime("%d %b %Y") if reservation_date else "",
            "queue_position": queue_position or "-",
            "status": status,
            "expires_at": expires_at.strftime("%d %b %Y") if expires_at else "-"
        })

    return render_template(
        'borrowed.html',
        history=history,
        reservations=reservations
    )


# ================================================
# BOOK RATINGS AND REVIEWS
# ================================================

@app.route('/api/reviews/<int:book_id>', methods=['GET'])
def get_book_reviews(book_id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            br.id,
            br.rating,
            br.review_text,
            br.created_at,
            m.first_name || ' ' || m.last_name AS reviewer
        FROM book_review br
        JOIN member m
            ON br.member_id = m.id
        WHERE br.book_id = %s
        ORDER BY br.created_at DESC;
    """, (book_id,))

    rows = cursor.fetchall()

    cursor.execute("""
        SELECT
            COALESCE(AVG(rating), 0),
            COUNT(*)
        FROM book_review
        WHERE book_id = %s;
    """, (book_id,))

    rating_row = cursor.fetchone()

    cursor.close()
    conn.close()

    reviews = []

    for row in rows:
        review_id, rating, review_text, created_at, reviewer = row

        reviews.append({
            "id": review_id,
            "rating": rating,
            "review_text": review_text or "",
            "created_at": created_at.strftime("%d %b %Y") if created_at else "",
            "reviewer": reviewer
        })

    average_rating = round(float(rating_row[0]), 1) if rating_row[0] else 0
    review_count = rating_row[1]

    return jsonify({
        "average_rating": average_rating,
        "review_count": review_count,
        "reviews": reviews
    })


@app.route('/api/reviews', methods=['POST'])
def submit_book_review():

    if 'member_id' not in session:
        return jsonify({
            "error": "Please log in first."
        }), 401

    if session.get('role') != 'student':
        return jsonify({
            "error": "Only students can review books."
        }), 403

    data = request.get_json()

    book_id = data.get('book_id')
    rating = data.get('rating')
    review_text = data.get('review_text', '').strip()

    if not book_id:
        return jsonify({
            "error": "Book ID is required."
        }), 400

    try:
        rating = int(rating)
    except (ValueError, TypeError):
        return jsonify({
            "error": "Rating must be a number from 1 to 5."
        }), 400

    if rating < 1 or rating > 5:
        return jsonify({
            "error": "Rating must be between 1 and 5."
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Make sure the student has borrowed this book before
    cursor.execute("""
        SELECT id
        FROM loan
        WHERE book_id = %s
        AND member_id = %s
        LIMIT 1;
    """, (
        book_id,
        session['member_id']
    ))

    loan = cursor.fetchone()

    if not loan:
        cursor.close()
        conn.close()
        return jsonify({
            "error": "You can only review a book you have borrowed."
        }), 403

    # Check whether the student already reviewed this book
    cursor.execute("""
        SELECT id
        FROM book_review
        WHERE book_id = %s
        AND member_id = %s;
    """, (
        book_id,
        session['member_id']
    ))

    existing_review = cursor.fetchone()

    if existing_review:
        cursor.close()
        conn.close()
        return jsonify({
            "error": "You have already reviewed this book."
        }), 400

    cursor.execute("""
        INSERT INTO book_review
        (
            book_id,
            member_id,
            rating,
            review_text
        )
        VALUES (%s, %s, %s, %s);
    """, (
        book_id,
        session['member_id'],
        rating,
        review_text if review_text else None
    ))

    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({
        "message": "Your rating and review were submitted successfully."
    })



@app.route('/profile')
def profile():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            first_name,
            last_name,
            email,
            faculty,
            department,
            programme
        FROM member
        WHERE id = %s;
    """, (session['member_id'],))

    row = cursor.fetchone()

    cursor.execute(
        "SELECT COUNT(*) FROM loan WHERE member_id = %s;",
        (session['member_id'],)
    )
    total_borrowed = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM loan WHERE member_id = %s AND returned_date IS NULL;",
        (session['member_id'],)
    )
    currently_out = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM member_interest WHERE member_id = %s;",
        (session['member_id'],)
    )
    interests_count = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    first_name, last_name, email, faculty, department, programme = row

    profile_data = {
        "full_name": first_name + " " + last_name,
        "email": email,
        "faculty": faculty or "Not set",
        "department": department or "Not set",
        "programme": programme or "Not set",
        "total_borrowed": total_borrowed,
        "currently_out": currently_out,
        "interests_count": interests_count
    }

    return render_template('profile.html', profile=profile_data)


@app.route('/loans')
def loans():
    if session.get('role') not in ('staff', 'admin'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT l.id, b.title, m.first_name || ' ' || m.last_name AS student,
               l.loan_date, l.due_date, l.returned_date
        FROM loan l
        JOIN book b ON l.book_id = b.id
        JOIN member m ON l.member_id = m.id
        ORDER BY l.loan_date DESC;
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    from datetime import date
    all_loans = []
    for row in rows:
        loan_id, title, student, loan_date, due_date, returned_date = row
        if returned_date:
            status = "Returned"
        elif due_date and due_date < date.today():
            status = "Overdue"
        else:
            status = "On Loan"
        all_loans.append({
            "loan_id": loan_id,
            "title": title,
            "student": student,
            "loan_date": loan_date.strftime("%d %b %Y") if loan_date else "",
            "due_date": due_date.strftime("%d %b %Y") if due_date else "-",
            "status": status
        })

    return render_template('loans.html', all_loans=all_loans)


@app.route('/students')
def students():
    if session.get('role') not in ('staff', 'admin'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT m.id, m.first_name || ' ' || m.last_name AS name, m.email,
               COUNT(l.id) FILTER (WHERE l.returned_date IS NULL) AS books_out,
               ms.status_value,
               m.active_status_id
        FROM member m
        LEFT JOIN loan l ON l.member_id = m.id
        LEFT JOIN member_status ms ON m.active_status_id = ms.id
        WHERE m.role = 'student'
        GROUP BY m.id, ms.status_value, m.active_status_id
        ORDER BY name;
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    student_list = []
    for row in rows:
        member_id, name, email, books_out, status_value, active_status_id = row
        student_list.append({
            "id": member_id,
            "name": name,
            "email": email,
            "books_out": books_out,
            "status": status_value or "Active",
            "active_status_id": active_status_id
        })

    return render_template('students.html', student_list=student_list)

@app.route('/api/students/<int:student_id>/suspend', methods=['POST'])
def suspend_student(student_id):
    if session.get('role') != 'admin':
        return jsonify({"error": "Only an admin can suspend students."}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE member
        SET active_status_id = 3
        WHERE id = %s
        AND role = 'student';
    """, (student_id,))

    if cursor.rowcount == 0:
        cursor.close()
        conn.close()
        return jsonify({"error": "Student not found."}), 404

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Student suspended successfully."})

@app.route('/api/students/<int:student_id>/reactivate', methods=['POST'])
def reactivate_student(student_id):
    if session.get('role') != 'admin':
        return jsonify({"error": "Only an admin can reactivate students."}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE member
        SET active_status_id = 1
        WHERE id = %s
        AND role = 'student';
    """, (student_id,))

    if cursor.rowcount == 0:
        cursor.close()
        conn.close()
        return jsonify({"error": "Student not found."}), 404

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Student reactivated successfully."})

# ================================================
# BOOKS + SEARCH
# ================================================

def fetch_books(search_term="", category="", author="all", year="all"):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT
            b.id,
            b.title,

            STRING_AGG(
                DISTINCT a.first_name || ' ' || a.last_name,
                ', '
            ) AS author,

            c.category_name,

            COUNT(DISTINCT bc.copy_id) FILTER (
                WHERE bc.copy_status = 'AVAILABLE'
            ) AS copies_available,

            EXTRACT(YEAR FROM b.publication_date) AS publication_year

        FROM book b

        LEFT JOIN category c
            ON b.category_id = c.id

        LEFT JOIN book_author ba
            ON b.id = ba.book_id

        LEFT JOIN author a
            ON ba.author_id = a.id

        LEFT JOIN book_copy bc
            ON b.id = bc.book_id
    """

    params = []

    # Search
    if search_term:
        if len(search_term) == 1 and search_term.isalpha():
            query += """
                AND b.title ILIKE %s
            """
            params.append(search_term + "%")

        else:
            query += """
                AND (
                    b.title ILIKE %s
                    OR (a.first_name || ' ' || a.last_name) ILIKE %s
                    OR c.category_name ILIKE %s
                )
            """

            search_pattern = "%" + search_term + "%"

            params.extend([
                search_pattern,
                search_pattern,
                search_pattern
            ])

    # Category filter
    if category and category != "all":
        query += """
            AND c.category_name = %s
        """
        params.append(category)

    # Author filter
    if author and author != "all":
        query += """
            AND (a.first_name || ' ' || a.last_name) = %s
        """
        params.append(author)

    # Year filter
    if year and year != "all":
        query += """
            AND EXTRACT(YEAR FROM b.publication_date) = %s
        """
        params.append(int(year))

    query += """
        GROUP BY
            b.id,
            b.title,
            c.category_name,
            b.publication_date

        ORDER BY b.title;
    """

    cursor.execute(query, params)
    rows = cursor.fetchall()

    books = []

    for row in rows:
        books.append({
            "id": row[0],
            "title": row[1],
            "author": row[2] if row[2] else "Unknown",
            "category": row[3] if row[3] else "Uncategorized",
            "copies": row[4],
            "year": int(row[5]) if row[5] else None
        })

    cursor.close()
    conn.close()

    return books

@app.route('/search')
def library_search():
    initial_category = request.args.get('category', 'all')
    books = fetch_books(category=initial_category)
    return render_template('search.html', books=books, initial_category=initial_category)


@app.route('/api/search')
def api_search():

    search_term = request.args.get('q', '')
    category = request.args.get('category', 'all')
    author = request.args.get('author', 'all')
    year = request.args.get('year', 'all')

    books = fetch_books(
        search_term,
        category,
        author,
        year
    )

    return jsonify(books)

# ================================================
# REGISTER / LOGIN / LOGOUT  — now supports all
# three roles (student, staff, admin), all stored
# in the 'member' table with a 'role' column.
# ================================================

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Public self-registration. Only ever creates STUDENT accounts —
    Staff/Admin accounts must be created by an existing Admin
    (see /admin/add-user), never self-selected here."""

    if request.method == 'GET':
        return render_template('signup.html')

    data = request.get_json()

    first_name = data.get('firstName', '').strip()
    last_name = data.get('lastName', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    faculty = data.get('faculty', '').strip()
    department = data.get('department', '').strip()
    programme = data.get('programme', '').strip()

    role = "student"  # hardcoded — never trust a role submitted by the public form

    if not re.match(EMAIL_PATTERNS[role], email):
        return jsonify({"error": "Student email must be 9 digits followed by @ufh.ac.za."}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    password_hash = generate_password_hash(password)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM member WHERE email = %s;", (email,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "An account with this email already exists."}), 400

    cursor.execute("""
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
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1);
""", (
    first_name,
    last_name,
    email,
    password_hash,
    role,
    faculty,
    department,
    programme
))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Account created successfully."})


@app.route('/admin/add-user', methods=['POST'])
def admin_add_user():
    """Protected: only a logged-in Admin can create Staff or Admin accounts."""

    if session.get('role') != 'admin':
        return jsonify({"error": "Only an admin can create staff or admin accounts."}), 403

    data = request.get_json()

    first_name = data.get('firstName', '').strip()
    last_name = data.get('lastName', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    role = data.get('role', '')

    if role not in ('staff', 'admin'):
        return jsonify({"error": "Role must be 'staff' or 'admin'."}), 400

    if not re.match(EMAIL_PATTERNS[role], email):
        return jsonify({"error": "Staff/Admin email must be 5 digits followed by @ufh.ac.za."}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    password_hash = generate_password_hash(password)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM member WHERE email = %s;", (email,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "An account with this email already exists."}), 400

    cursor.execute("""
        INSERT INTO member (first_name, last_name, email, password_hash, role, active_status_id)
        VALUES (%s, %s, %s, %s, %s, 1);
    """, (first_name, last_name, email, password_hash, role))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": role.capitalize() + " account created successfully."})

@app.route('/login.html')
def login_html():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login always determines the real role from the database."""

    if request.method == 'GET':
        return render_template('login.html')

    data = request.get_json()

    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            first_name,
            password_hash,
            role,
            active_status_id
        FROM member
        WHERE email = %s;
    """, (email,))

    row = cursor.fetchone()

    cursor.close()
    conn.close()

    if not row:
        return jsonify({
            "error": "No account found with this email. Please sign up first."
        }), 400

    member_id, first_name, password_hash, actual_role, active_status_id = row

    if not password_hash or not check_password_hash(password_hash, password):
        return jsonify({
            "error": "Incorrect password. Please try again."
        }), 400

    if active_status_id != 1:
        return jsonify({
            "error": "Your account is not active. Please contact the library."
        }), 403

    session['member_id'] = member_id
    session['first_name'] = first_name
    session['email'] = email
    session['role'] = actual_role

    # Record successful login in the audit log
    log_action(
        member_id,
        "LOGIN",
        f"{actual_role.capitalize()} user logged in successfully."
    )

    redirect_map = {
        "student": "/dashboard",
        "staff": "/dashboard-staff",
        "admin": "/dashboard-admin"
    }

    return jsonify({
        "message": "Login successful.",
        "redirect": redirect_map[actual_role]
    })


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


# ================================================
# DASHBOARDS (role-protected)
# ================================================

@app.route('/dashboard')
def dashboard():

    if session.get('role') != 'student':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

        # ============================================
    # CREATE LIBRARY NOTIFICATIONS
    # ============================================

    from datetime import date

    # Due soon / due today / overdue notifications
    cursor.execute("""
        SELECT
            l.id,
            l.due_date,
            b.title
        FROM loan l
        JOIN book b
            ON l.book_id = b.id
        WHERE l.member_id = %s
        AND l.returned_date IS NULL;
    """, (session['member_id'],))

    notification_loans = cursor.fetchall()

    for loan_row in notification_loans:

        loan_id, due_date, title = loan_row

        if not due_date:
            continue

        days_left = (due_date - date.today()).days

        # Overdue
        if days_left < 0:

            overdue_days = abs(days_left)

            cursor.execute("""
                SELECT id
                FROM notification
                WHERE member_id = %s
                AND loan_id = %s
                AND notification_type = 'OVERDUE';
            """, (
                session['member_id'],
                loan_id
            ))

            if not cursor.fetchone():

                cursor.execute("""
                    INSERT INTO notification
                    (
                        member_id,
                        loan_id,
                        notification_type,
                        title,
                        message
                    )
                    VALUES (%s, %s, %s, %s, %s);
                """, (
                    session['member_id'],
                    loan_id,
                    'OVERDUE',
                    'Book overdue',
                    f'{title} is overdue by {overdue_days} day(s). Please return it.'
                ))

        # Due today
        elif days_left == 0:

            cursor.execute("""
                SELECT id
                FROM notification
                WHERE member_id = %s
                AND loan_id = %s
                AND notification_type = 'DUE_TODAY';
            """, (
                session['member_id'],
                loan_id
            ))

            if not cursor.fetchone():

                cursor.execute("""
                    INSERT INTO notification
                    (
                        member_id,
                        loan_id,
                        notification_type,
                        title,
                        message
                    )
                    VALUES (%s, %s, %s, %s, %s);
                """, (
                    session['member_id'],
                    loan_id,
                    'DUE_TODAY',
                    'Book due today',
                    f'{title} is due today. Please return it.'
                ))

        # Due within 3 days
        elif days_left <= 3:

            cursor.execute("""
                SELECT id
                FROM notification
                WHERE member_id = %s
                AND loan_id = %s
                AND notification_type = 'DUE_SOON';
            """, (
                session['member_id'],
                loan_id
            ))

            if not cursor.fetchone():

                cursor.execute("""
                    INSERT INTO notification
                    (
                        member_id,
                        loan_id,
                        notification_type,
                        title,
                        message
                    )
                    VALUES (%s, %s, %s, %s, %s);
                """, (
                    session['member_id'],
                    loan_id,
                    'DUE_SOON',
                    'Book due soon',
                    f'{title} is due in {days_left} day(s). Please return it soon.'
                ))

    # Reservation ready notifications
    cursor.execute("""
        SELECT
            r.id,
            r.expires_at,
            b.title
        FROM reservation r
        JOIN book b
            ON r.book_id = b.id
        WHERE r.member_id = %s
        AND r.reservation_status_id = 4;
    """, (session['member_id'],))

    ready_reservations = cursor.fetchall()

    for reservation_row in ready_reservations:

        reservation_id, expires_at, title = reservation_row

        cursor.execute("""
            SELECT id
            FROM notification
            WHERE member_id = %s
            AND reservation_id = %s
            AND notification_type = 'RESERVATION_READY';
        """, (
            session['member_id'],
            reservation_id
        ))

        if not cursor.fetchone():

            expiry_text = (
                expires_at.strftime("%d %b %Y")
                if expires_at
                else "soon"
            )

            cursor.execute("""
                INSERT INTO notification
                (
                    member_id,
                    reservation_id,
                    notification_type,
                    title,
                    message
                )
                VALUES (%s, %s, %s, %s, %s);
            """, (
                session['member_id'],
                reservation_id,
                'RESERVATION_READY',
                'Reservation ready',
                f'{title} is ready for you. Please collect it by {expiry_text}.'
            ))

            conn.commit()

    # Get the student's notifications
    cursor.execute("""
        SELECT
            id,
            title,
            message,
            is_read,
            created_at
        FROM notification
        WHERE member_id = %s
        ORDER BY created_at DESC
        LIMIT 10;
    """, (session['member_id'],))

    notification_rows = cursor.fetchall()
    notifications = []

    # Get the student's borrowed books
    cursor.execute("""
         SELECT
        l.id,
        l.book_id,
        b.title,
        l.loan_date,
        l.due_date,
        l.returned_date

        FROM loan l
        JOIN book b ON l.book_id = b.id
        WHERE l.member_id = %s
        ORDER BY l.loan_date DESC;
    """, (session['member_id'],))

    rows = cursor.fetchall()

    # Get the student's reservations
    cursor.execute("""
        SELECT
            r.id,
            b.title,
            r.reservation_date,
            r.queue_position,
            rs.status_value,
            r.expires_at
        FROM reservation r
        JOIN book b
            ON r.book_id = b.id
        JOIN reservation_status rs
            ON r.reservation_status_id = rs.id
        WHERE r.member_id = %s
        ORDER BY r.reservation_date DESC, r.id DESC;
    """, (session['member_id'],))

    reservation_rows = cursor.fetchall()
    from datetime import date

    borrowed_books = []

    for row in rows:
        loan_id, book_id, title, loan_date, due_date, returned_date = row

        if returned_date:
            status = "Returned"
            reminder = ""

        elif due_date and due_date < date.today():
            overdue_days = (date.today() - due_date).days
            status = "Overdue"
            reminder = f"Overdue by {overdue_days} day(s). Please return this book."

        else:
            status = "Currently Out"
            reminder = ""

            if due_date:
                days_left = (due_date - date.today()).days

                if days_left == 0:
                    reminder = "Due today. Please return this book."
                elif days_left == 1:
                    reminder = "Reminder: This book is due tomorrow."
                elif days_left <= 3:
                    reminder = f"Reminder: This book is due in {days_left} days."

        borrowed_books.append({
            "loan_id": loan_id,
            "book_id": book_id,
            "title": title,
            "loan_date": loan_date.strftime("%d %b %Y") if loan_date else "",
            "due_date": due_date.strftime("%d %b %Y") if due_date else "-",
            "status": status,
           "reminder": reminder
    })

       # Get the student's fines
    cursor.execute("""
        SELECT
            f.id,
            b.title,
            l.due_date,
            l.returned_date,
            f.fine_amount
        FROM fine f
        JOIN loan l ON f.loan_id = l.id
        JOIN book b ON l.book_id = b.id
        WHERE f.member_id = %s
        ORDER BY f.fine_date DESC;
    """, (session['member_id'],))

    fine_rows = cursor.fetchall()

    # Get total fines
    cursor.execute("""
        SELECT COALESCE(SUM(fine_amount), 0)
        FROM fine
        WHERE member_id = %s;
    """, (session['member_id'],))

    total_fines = cursor.fetchone()[0]

    # Get total amount already paid
    cursor.execute("""
        SELECT COALESCE(SUM(payment_amount), 0)
        FROM fine_payment
        WHERE member_id = %s;
    """, (session['member_id'],))

    total_paid = cursor.fetchone()[0]

    # Calculate outstanding balance
    outstanding_fine = total_fines - total_paid

    if outstanding_fine < 0:
        outstanding_fine = 0

    fines = []

    for row in fine_rows:
        fine_id, title, due_date, returned_date, fine_amount = row

        fines.append({
            "fine_id": fine_id,
            "title": title,
            "due_date": due_date.strftime("%d %b %Y") if due_date else "-",
            "returned_date": returned_date.strftime("%d %b %Y") if returned_date else "-",
            "fine_amount": f"R{fine_amount:.2f}"
        })

    reservations = []

    for row in reservation_rows:

        reservation_id, title, reservation_date, queue_position, status, expires_at = row

        reservations.append({
            "reservation_id": reservation_id,
            "title": title,
            "reservation_date": reservation_date.strftime("%d %b %Y") if reservation_date else "",
            "queue_position": queue_position or "-",
            "status": status,
            "expires_at": expires_at.strftime("%d %b %Y") if expires_at else "-"
        })


    for row in notification_rows:

        notification_id, title, message, is_read, created_at = row

        notifications.append({
            "id": notification_id,
            "title": title,
            "message": message,
            "is_read": is_read,
            "created_at": created_at.strftime("%d %b %Y %H:%M") if created_at else ""
        })

    cursor.close()
    conn.close()

    return render_template(
        'dashboard-student.html',
        first_name=session.get('first_name'),
        borrowed_books=borrowed_books,
        fines=fines,
        reservations=reservations,
        notifications=notifications,
        total_fines=total_fines,
        total_paid=total_paid,
        outstanding_fine=outstanding_fine
    )


@app.route('/dashboard-staff')
def dashboard_staff():
    if session.get('role') not in ('staff', 'admin'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Total books
    cursor.execute("""
        SELECT COUNT(*)
        FROM book;
    """)

    total_books = cursor.fetchone()[0]


    # Books currently borrowed
    cursor.execute("""
        SELECT COUNT(*)
        FROM loan
        WHERE returned_date IS NULL;
    """)

    borrowed_now = cursor.fetchone()[0]


    # Overdue books
    cursor.execute("""
        SELECT COUNT(*)
        FROM loan
        WHERE returned_date IS NULL
        AND due_date < CURRENT_DATE;
    """)

    overdue_books = cursor.fetchone()[0]


    # Active students
    cursor.execute("""
        SELECT COUNT(*)
        FROM member
        WHERE role = 'student'
        AND active_status_id = 1;
    """)

    active_students = cursor.fetchone()[0]

    cursor.execute("""
    SELECT
        b.id,
        b.title,
        STRING_AGG(DISTINCT a.first_name || ' ' || a.last_name, ', ') AS author,
        c.category_name,
        b.copies_owned
    FROM book b
    LEFT JOIN category c ON b.category_id = c.id
    LEFT JOIN book_author ba ON b.id = ba.book_id
    LEFT JOIN author a ON ba.author_id = a.id
    GROUP BY b.id, c.category_name
    ORDER BY b.id DESC
    LIMIT 10;
""")

    rows = cursor.fetchall()

    # Get book purchase requests
    cursor.execute("""
        SELECT
            pr.id,
            pr.title,
            pr.author,
            pr.reason,
            pr.request_date,
            pr.status,
            m.first_name || ' ' || m.last_name AS student
        FROM purchase_request pr
        JOIN member m ON pr.member_id = m.id
        ORDER BY pr.request_date DESC, pr.id DESC;
    """)

    purchase_rows = cursor.fetchall()

    cursor.close()
    conn.close()

    recent_books = []
    for row in rows:
        recent_books.append({
            "id": row[0],
            "title": row[1],
            "author": row[2] if row[2] else "Unknown",
            "category": row[3] if row[3] else "Uncategorized",
            "copies": row[4]
        })

    return render_template(
    'dashboard-staff.html',
    recent_books=recent_books,
    purchase_requests=purchase_rows,
    total_books=total_books,
    borrowed_now=borrowed_now,
    overdue_books=overdue_books,
    active_students=active_students
)


@app.route('/dashboard-admin')
def dashboard_admin():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Total books
    cursor.execute("SELECT COUNT(*) FROM book;")
    total_books = cursor.fetchone()[0]

    # Total students
    cursor.execute("SELECT COUNT(*) FROM member WHERE role = 'student';")
    total_students = cursor.fetchone()[0]

    # Total staff
    cursor.execute("SELECT COUNT(*) FROM member WHERE role = 'staff';")
    total_staff = cursor.fetchone()[0]

    # Active loans
    cursor.execute("""
        SELECT COUNT(*)
        FROM loan
        WHERE returned_date IS NULL;
    """)
    active_loans = cursor.fetchone()[0]

    # Overdue books
    cursor.execute("""
        SELECT COUNT(*)
        FROM loan
        WHERE returned_date IS NULL
        AND due_date < CURRENT_DATE;
    """)
    overdue_loans = cursor.fetchone()[0]

    # Staff and admin accounts
    cursor.execute("""
        SELECT
            m.first_name || ' ' || m.last_name,
            m.email,
            m.role
        FROM member m
        WHERE m.role IN ('staff', 'admin')
        ORDER BY m.role, m.first_name;
    """)
    staff_admin_rows = cursor.fetchall()

    # Students who currently have overdue books
    cursor.execute("""
        SELECT COUNT(DISTINCT member_id)
        FROM loan
        WHERE returned_date IS NULL
        AND due_date < CURRENT_DATE;
    """)
    overdue_students = cursor.fetchone()[0]

    # Most borrowed category
    cursor.execute("""
        SELECT
            c.category_name,
            COUNT(l.id) AS category_loans
        FROM loan l
        JOIN book b
            ON l.book_id = b.id
        JOIN category c
            ON b.category_id = c.id
        GROUP BY c.category_name
        ORDER BY category_loans DESC
        LIMIT 1;
    """)
    most_borrowed_row = cursor.fetchone()

    # Total loan records
    cursor.execute("""
        SELECT COUNT(*)
        FROM loan;
    """)
    total_loan_records = cursor.fetchone()[0]

    most_borrowed_category = "No borrowing data"
    most_borrowed_percentage = 0

    if most_borrowed_row and total_loan_records > 0:
        most_borrowed_category = most_borrowed_row[0]
        most_borrowed_percentage = round(
            (most_borrowed_row[1] / total_loan_records) * 100,
            2
        )

    # Close database connection only after ALL queries are finished
    cursor.close()
    conn.close()

    staff_admin_list = [
        {
            "name": r[0],
            "email": r[1],
            "role": r[2]
        }
        for r in staff_admin_rows
    ]

    stats = {
        "total_books": total_books,
        "total_students": total_students,
        "total_staff": total_staff,
        "active_loans": active_loans,
        "overdue_loans": overdue_loans,
        "overdue_students": overdue_students,
        "most_borrowed_category": most_borrowed_category,
        "most_borrowed_percentage": most_borrowed_percentage
    }

    return render_template(
        'dashboard-admin.html',
        stats=stats,
        staff_admin_list=staff_admin_list
    )


@app.route('/admin/add-category', methods=['POST'])
def admin_add_category():

    if session.get('role') != 'admin':
        return jsonify({"error": "Only an admin can manage categories."}), 403

    data = request.get_json()
    name = data.get('name', '').strip()

    if not name:
        return jsonify({"error": "Category name is required."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM category WHERE category_name = %s;", (name,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "That category already exists."}), 400

    cursor.execute("INSERT INTO category (category_name) VALUES (%s);", (name,))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Category added."})


# ================================================
# CATEGORIES PAGE (public)
# ================================================

@app.route('/categories')
def categories_page():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT c.category_name, COUNT(b.id) AS book_count
        FROM category c
        LEFT JOIN book b ON b.category_id = c.id
        GROUP BY c.category_name
        ORDER BY c.category_name;
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    category_list = [{"name": r[0], "count": r[1]} for r in rows]

    return render_template('categories.html', category_list=category_list)


# ================================================
# RESOURCES / RESEARCH / GUIDES / REPOSITORY
# (clearly-marked "coming soon" placeholder pages —
# per the brief, no fake functionality)
# ================================================

@app.route('/resources')
def resources_page():
    cards = [
        {
            "icon": "📘",
            "title": "E-Books",
            "desc": "Access free digital books through Project Gutenberg.",
            "available": True,
            "url": "https://www.gutenberg.org/ebooks/"
        },
        {
            "icon": "📰",
            "title": "Online Journals",
            "desc": "Peer-reviewed journals across all faculties."
        },
        {
            "icon": "🗄️",
            "title": "Research Databases",
            "desc": "Searchable academic and scientific databases."
        },
        {
            "icon": "📄",
            "title": "Research Papers",
            "desc": "Published research from students and staff."
        },
        {
            "icon": "🎓",
            "title": "Theses & Dissertations",
            "desc": "Postgraduate research submitted at UFH."
        },
        {
            "icon": "📝",
            "title": "Past Examination Papers",
            "desc": "Previous exam papers for revision."
        },
        {
            "icon": "📚",
            "title": "Academic Resources",
            "desc": "Study guides and supplementary material."
        },
        {
            "icon": "🏛️",
            "title": "University Publications",
            "desc": "Official UFH publications and reports."
        },
    ]

    return render_template(
        'placeholder-section.html',
        page_title="Library Resources",
        page_subtitle="Explore the resources available through UniLibrary.",
        cards=cards
    )


@app.route('/research')
def research_page():

    cards = [
        {
            "icon": "🔬",
            "title": "Research Databases",
            "desc": "Searchable academic and scientific research databases."
        },
        {
            "icon": "📄",
            "title": "Research Papers",
            "desc": "Published research from students and staff."
        },
        {
            "icon": "🎓",
            "title": "Theses & Dissertations",
            "desc": "Postgraduate research submitted at UFH."
        },
        {
            "icon": "📚",
            "title": "Research Guides",
            "desc": "Guidance for finding and using academic sources."
        },
        {
            "icon": "📝",
            "title": "Past Research Projects",
            "desc": "Explore completed academic research projects."
        },
        {
            "icon": "🏛️",
            "title": "University Research",
            "desc": "Research and publications connected to UFH."
        }
    ]

    return render_template(
        'placeholder-section.html',
        page_title="Library Research",
        page_subtitle="Explore research resources and academic materials available through UniLibrary.",
        cards=cards
    )


@app.route('/guides')
def guides_page():
    cards = [
        {"icon": "💻", "title": "Computer Science", "desc": "Recommended books and resources for CS students."},
        {"icon": "📐", "title": "Mathematics", "desc": "Recommended books and resources for Maths students."},
        {"icon": "🧪", "title": "Science", "desc": "Recommended books and resources for Science students."},
        {"icon": "📖", "title": "Humanities", "desc": "Recommended books and resources for Humanities students."},
        {"icon": "💼", "title": "Business", "desc": "Recommended books and resources for Business students."},
        {"icon": "🎓", "title": "General Academic Guide", "desc": "General study and research guidance for all students."},
    ]
    return render_template('placeholder-section.html',
                            page_title="Library Guides",
                            page_subtitle="Subject guides to help you find the right material.",
                            cards=cards)


@app.route('/repository')
def repository_page():
    cards = [
        {"icon": "🎓", "title": "Theses & Dissertations", "desc": "Postgraduate research submitted at UFH."},
        {"icon": "📝", "title": "Past Examination Papers", "desc": "Previous exam papers for revision."},
        {"icon": "📄", "title": "Research Papers", "desc": "Published research from students and staff."},
        {"icon": "🏛️", "title": "University Publications", "desc": "Official UFH publications and reports."},
    ]
    return render_template('placeholder-section.html',
                            page_title="Institutional Repository",
                            page_subtitle="UFH's archive of academic and research output.",
                            cards=cards)


@app.route('/services')
def services_page():
    cards = [
        {"icon": "📖", "title": "Borrowing & Returns", "desc": "Borrow and return books through your account.", "available": True},
        {"icon": "👤", "title": "My Library Account", "desc": "View your profile, loans, and history.", "available": True},
        {"icon": "📚", "title": "Study Resources", "desc": "Access study guides and academic material."},
        {"icon": "🔬", "title": "Research Support", "desc": "Get help with research resources and tools."},
        {"icon": "🆘", "title": "Library Help", "desc": "Contact the library for assistance."},
        {"icon": "🏫", "title": "Study Room Booking", "desc": "Reserve a room to study on campus."},
        {"icon": "🔄", "title": "Interlibrary Loan", "desc": "Request material from other libraries."},
        {"icon": "💬", "title": "Ask a Librarian", "desc": "Get direct help from library staff."},
    ]
    return render_template('placeholder-section.html',
                            page_title="Library Services",
                            page_subtitle="Services available to UniLibrary members.",
                            cards=cards)


# ================================================
# ANNOUNCEMENTS (public read, admin write)
# ================================================

@app.route('/api/announcements')
def api_announcements():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT title, body, created_at FROM announcement
        ORDER BY created_at DESC LIMIT 5;
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    announcements = [{"title": r[0], "body": r[1], "date": r[2].strftime("%d %b %Y")} for r in rows]
    return jsonify(announcements)


@app.route('/admin/add-announcement', methods=['POST'])
def admin_add_announcement():
    if session.get('role') != 'admin':
        return jsonify({"error": "Only an admin can post announcements."}), 403

    data = request.get_json()
    title = data.get('title', '').strip()
    body = data.get('body', '').strip()

    if not title or not body:
        return jsonify({"error": "Title and body are required."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO announcement (title, body, created_by)
        VALUES (%s, %s, %s);
    """, (title, body, session.get('member_id')))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Announcement posted."})


# ================================================
# BORROW A BOOK
# ================================================

@app.route('/borrow', methods=['POST'])
def borrow_book():

    if session.get('role') != 'student':
        return jsonify({"error": "Only students can borrow books."}), 403

    data = request.get_json()
    book_id = data.get('book_id')

    if not book_id:
        return jsonify({"error": "Book ID is required."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check that the book exists
    cursor.execute("""
        SELECT id, title
        FROM book
        WHERE id = %s;
    """, (book_id,))

    book = cursor.fetchone()

    if not book:
        cursor.close()
        conn.close()
        return jsonify({"error": "Book not found."}), 404

    book_id, title = book

    # Check if this student already has the same book
    cursor.execute("""
        SELECT id
        FROM loan
        WHERE book_id = %s
        AND member_id = %s
        AND returned_date IS NULL;
    """, (book_id, session['member_id']))

    existing_loan = cursor.fetchone()

    if existing_loan:
        cursor.close()
        conn.close()
        return jsonify({
            "error": "You already have this book borrowed."
        }), 400

    # Find one available physical copy
    cursor.execute("""
        SELECT copy_id, barcode
        FROM book_copy
        WHERE book_id = %s
        AND copy_status = 'AVAILABLE'
        ORDER BY copy_id
        LIMIT 1
        FOR UPDATE;
    """, (book_id,))

    available_copy = cursor.fetchone()

    if not available_copy:
        cursor.close()
        conn.close()
        return jsonify({
            "error": "No copies of this book are currently available."
        }), 400

    copy_id, barcode = available_copy

    # Create the loan using the selected physical copy
    cursor.execute("""
        INSERT INTO loan
        (book_id, member_id, loan_date, due_date, copy_id)
        VALUES (%s, %s, CURRENT_DATE, CURRENT_DATE + INTERVAL '14 days', %s);
    """, (
        book_id,
        session['member_id'],
        copy_id
    ))

       # Mark the physical copy as borrowed
    cursor.execute("""
        UPDATE book_copy
        SET copy_status = 'BORROWED'
        WHERE copy_id = %s;
    """, (copy_id,))

    # Record the borrow action in the audit log
    log_action(
        session['member_id'],
        "BORROW",
        f"Student borrowed '{title}' (Copy {barcode})."
    )

    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({
        "message": f"Book borrowed successfully. Copy {barcode} is assigned to you. It is due back in 14 days."
    })


# ================================================
# ADD A BOOK (Staff / Admin only)
# ================================================

@app.route('/return', methods=['POST'])
def return_book():

    if 'member_id' not in session:
        return jsonify({"error": "Please log in first."}), 401

    data = request.get_json()
    loan_id = data.get('loan_id')

    if not loan_id:
        return jsonify({"error": "Loan ID is required."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get the loan information
    cursor.execute("""
        SELECT
            id,
            member_id,
            book_id,
            due_date,
            returned_date,
            copy_id
        FROM loan
        WHERE id = %s;
    """, (loan_id,))

    loan = cursor.fetchone()

    if not loan:
        cursor.close()
        conn.close()
        return jsonify({"error": "Loan not found."}), 404

    loan_id, member_id, book_id, due_date, returned_date, copy_id = loan

    # Students can only return their own books
    if session.get('role') == 'student' and member_id != session['member_id']:
        cursor.close()
        conn.close()
        return jsonify({
            "error": "You can only return your own books."
        }), 403

    # Check if the book has already been returned
    if returned_date is not None:
        cursor.close()
        conn.close()
        return jsonify({
            "error": "This book has already been returned."
        }), 400

    # Calculate overdue days
    cursor.execute("""
        SELECT GREATEST(CURRENT_DATE - due_date, 0)
        FROM loan
        WHERE id = %s;
    """, (loan_id,))

    overdue_days = cursor.fetchone()[0]

    # Return the loan
    cursor.execute("""
        UPDATE loan
        SET returned_date = CURRENT_DATE
        WHERE id = %s;
    """, (loan_id,))

    # Make the physical copy available
    if copy_id:
        cursor.execute("""
            UPDATE book_copy
            SET copy_status = 'AVAILABLE'
            WHERE copy_id = %s;
        """, (copy_id,))

        # Find the first pending reservation for this book
        cursor.execute("""
            SELECT r.id, r.member_id
            FROM reservation r
            WHERE r.book_id = %s
            AND r.reservation_status_id = 1
            AND NOT EXISTS (
                SELECT 1
                FROM loan l
                WHERE l.book_id = r.book_id
                AND l.member_id = r.member_id
                AND l.returned_date IS NULL
            )
            ORDER BY r.queue_position
            LIMIT 1
            FOR UPDATE;
        """, (book_id,))

        reservation = cursor.fetchone()

        if reservation:
            reservation_id, reservation_member_id = reservation

            # Give the returned copy to the first student in the queue
            cursor.execute("""
                UPDATE reservation
                SET reservation_status_id = 4,
                    allocated_copy_id = %s,
                    expires_at = CURRENT_DATE + 3
                WHERE id = %s;
            """, (copy_id, reservation_id))

            # Reserve that physical copy for the student
            cursor.execute("""
                UPDATE book_copy
                SET copy_status = 'RESERVED'
                WHERE copy_id = %s;
            """, (copy_id,))

       # Create a fine if the book is overdue
    fine_amount = overdue_days * 5

    if fine_amount > 0:
        cursor.execute("""
            INSERT INTO fine
            (member_id, loan_id, fine_date, fine_amount)
            VALUES (%s, %s, CURRENT_DATE, %s);
        """, (member_id, loan_id, fine_amount))

    # Record the return action in the audit log
    log_action(
        session['member_id'],
        "RETURN",
        f"{session.get('role').capitalize()} returned loan ID {loan_id}, book ID {book_id}, copy ID {copy_id}."
    )

    conn.commit()

    cursor.close()
    conn.close()

    if fine_amount > 0:
        return jsonify({
            "message": "Book returned successfully.",
            "fine": f"R{fine_amount} fine for {overdue_days} overdue day(s)."
        })

    return jsonify({
        "message": "Book returned successfully. No fine."
    })
@app.route('/add-book', methods=['POST'])
def add_book():

    if session.get('role') not in ('staff', 'admin'):
        return jsonify({"error": "Only staff or admin can add books."}), 403

    data = request.get_json()
    title = data.get('title', '').strip()
    author_name = data.get('author', '').strip()
    category_name = data.get('category', '').strip()
    copies = data.get('copies', 1)

    if not title or not author_name:
        return jsonify({"error": "Title and author are required."}), 400

    try:
        copies = int(copies)
    except (ValueError, TypeError):
        return jsonify({
            "error": "Number of copies must be a whole number."
        }), 400

    if copies < 1:
        return jsonify({
            "error": "There must be at least 1 copy."
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Find the category id
    cursor.execute(
        "SELECT id FROM category WHERE category_name = %s;",
        (category_name,)
    )

    cat_row = cursor.fetchone()

    if not cat_row:
        cursor.close()
        conn.close()

        return jsonify({
            "error": "That category does not exist."
        }), 400

    category_id = cat_row[0]

    # Insert the book
    cursor.execute("""
        INSERT INTO book (title, category_id, publication_date, copies_owned)
        VALUES (%s, %s, CURRENT_DATE, %s)
        RETURNING id;
    """, (title, category_id, copies))
    book_id = cursor.fetchone()[0]

    # Create physical copies for the new book
    for copy_number in range(1, copies + 1):

        barcode = f"BOOK-{book_id}-COPY-{copy_number}"

        cursor.execute("""
            INSERT INTO book_copy
            (
                book_id,
                barcode,
                copy_status
            )
            VALUES (%s, %s, 'AVAILABLE');
        """, (
            book_id,
            barcode
        ))

    # Find or create the author (split on first space: first name / last name)
    name_parts = author_name.split(" ", 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    cursor.execute("""
        SELECT id FROM author WHERE first_name = %s AND last_name = %s;
    """, (first_name, last_name))
    author_row = cursor.fetchone()

    if author_row:
        author_id = author_row[0]
    else:
        cursor.execute("""
            INSERT INTO author (first_name, last_name)
            VALUES (%s, %s)
            RETURNING id;
        """, (first_name, last_name))
        author_id = cursor.fetchone()[0]

    # Link book to author
    cursor.execute("""
        INSERT INTO book_author (book_id, author_id) VALUES (%s, %s);
    """, (book_id, author_id))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Book added successfully.", "book_id": book_id})


# ================================================
# EDIT A BOOK (Staff / Admin only)
# ================================================

@app.route('/edit-book', methods=['POST'])
def edit_book():

    if session.get('role') not in ('staff', 'admin'):
        return jsonify({
            "error": "Only staff or admin can edit books."
        }), 403

    data = request.get_json() or {}

    try:
        book_id = int(data.get('book_id'))
    except (ValueError, TypeError):
        return jsonify({
            "error": "Invalid book ID."
        }), 400

    title = data.get('title', '').strip()
    author_name = data.get('author', '').strip()
    category_name = data.get('category', '').strip()

    try:
        copies = int(data.get('copies'))
    except (ValueError, TypeError):
        return jsonify({
            "error": "Number of copies must be a whole number."
        }), 400

    if not title:
        return jsonify({
            "error": "Book title is required."
        }), 400

    if not author_name:
        return jsonify({
            "error": "Author is required."
        }), 400

    if not category_name:
        return jsonify({
            "error": "Category is required."
        }), 400

    if copies < 1:
        return jsonify({
            "error": "There must be at least 1 copy."
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:

        # Find the book
        cursor.execute("""
            SELECT title, copies_owned
            FROM book
            WHERE id = %s;
        """, (book_id,))

        book = cursor.fetchone()

        if not book:
            return jsonify({
                "error": "Book not found."
            }), 404

        old_title, old_copies = book

        # Count copies currently borrowed
        cursor.execute("""
            SELECT COUNT(*)
            FROM loan
            WHERE book_id = %s
            AND returned_date IS NULL;
        """, (book_id,))

        active_loans = cursor.fetchone()[0]

        if copies < active_loans:
            return jsonify({
                "error": (
                    f"This book currently has {active_loans} "
                    f"borrowed copy/copies. "
                    f"Copies cannot be reduced below {active_loans}."
                )
            }), 400

        # Find the category
        cursor.execute("""
            SELECT id
            FROM category
            WHERE category_name = %s;
        """, (category_name,))

        category_row = cursor.fetchone()

        if not category_row:
            return jsonify({
                "error": "That category does not exist."
            }), 400

        category_id = category_row[0]

        # Find or create the author
        name_parts = author_name.split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        cursor.execute("""
            SELECT id
            FROM author
            WHERE first_name = %s
            AND last_name = %s;
        """, (
            first_name,
            last_name
        ))

        author_row = cursor.fetchone()

        if author_row:
            author_id = author_row[0]

        else:
            cursor.execute("""
                INSERT INTO author
                (
                    first_name,
                    last_name
                )
                VALUES (%s, %s)
                RETURNING id;
            """, (
                first_name,
                last_name
            ))

            author_id = cursor.fetchone()[0]

        # Update the book
        cursor.execute("""
            UPDATE book
            SET
                title = %s,
                category_id = %s,
                copies_owned = %s
            WHERE id = %s;
        """, (
            title,
            category_id,
            copies,
            book_id
        ))

        # Replace the book-author relationship
        cursor.execute("""
            DELETE FROM book_author
            WHERE book_id = %s;
        """, (book_id,))

        cursor.execute("""
            INSERT INTO book_author
            (
                book_id,
                author_id
            )
            VALUES (%s, %s);
        """, (
            book_id,
            author_id
        ))

        # Keep physical copies synchronized
        cursor.execute("""
            SELECT copy_id, copy_status
            FROM book_copy
            WHERE book_id = %s
            ORDER BY copy_id;
        """, (book_id,))

        physical_copies = cursor.fetchall()
        physical_count = len(physical_copies)

        # Add copies when the total increases
        if copies > physical_count:

            for copy_number in range(
                physical_count + 1,
                copies + 1
            ):

                barcode = f"BOOK-{book_id}-COPY-{copy_number}"

                cursor.execute("""
                    INSERT INTO book_copy
                    (
                        book_id,
                        barcode,
                        copy_status
                    )
                    VALUES (%s, %s, 'AVAILABLE');
                """, (
                    book_id,
                    barcode
                ))

        # Remove only available copies when the total decreases
        elif copies < physical_count:

            remove_count = physical_count - copies

            available_copy_ids = [
                row[0]
                for row in physical_copies
                if row[1] == 'AVAILABLE'
            ]

            if len(available_copy_ids) < remove_count:
                return jsonify({
                    "error": (
                        "There are not enough available copies "
                        "to reduce the total. Some copies are "
                        "currently borrowed or reserved."
                    )
                }), 400

            for copy_id in available_copy_ids[:remove_count]:

                cursor.execute("""
                    DELETE FROM book_copy
                    WHERE copy_id = %s
                    AND copy_status = 'AVAILABLE';
                """, (copy_id,))

        conn.commit()

        log_action(
            session['member_id'],
            "EDIT_BOOK",
            f"Edited book ID {book_id}: '{old_title}' to '{title}'."
        )

        return jsonify({
            "message": "Book updated successfully."
        }), 200

    except Exception:

        conn.rollback()

        return jsonify({
            "error": "Could not update the book."
        }), 500

    finally:
        cursor.close()
        conn.close()


# ================================================
# DELETE A BOOK (Staff / Admin only)
# ================================================

@app.route('/delete-book', methods=['POST'])
def delete_book():

    if session.get('role') not in ('staff', 'admin'):
        return jsonify({
            "error": "Only staff or admin can delete books."
        }), 403

    data = request.get_json() or {}

    try:
        book_id = int(data.get('book_id'))
    except (ValueError, TypeError):
        return jsonify({
            "error": "Invalid book ID."
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:

        # Find the book
        cursor.execute("""
            SELECT title
            FROM book
            WHERE id = %s;
        """, (book_id,))

        book = cursor.fetchone()

        if not book:
            return jsonify({
                "error": "Book not found."
            }), 404

        book_title = book[0]

        # Do not delete currently borrowed books
        cursor.execute("""
            SELECT COUNT(*)
            FROM loan
            WHERE book_id = %s
            AND returned_date IS NULL;
        """, (book_id,))

        active_loans = cursor.fetchone()[0]

        if active_loans > 0:
            return jsonify({
                "error": (
                    "This book cannot be deleted because "
                    "it is currently borrowed."
                )
            }), 400

        # Keep borrowing history
        cursor.execute("""
            SELECT COUNT(*)
            FROM loan
            WHERE book_id = %s;
        """, (book_id,))

        loan_history = cursor.fetchone()[0]

        if loan_history > 0:
            return jsonify({
                "error": (
                    "This book cannot be deleted because "
                    "it has borrowing history."
                )
            }), 400

        # Keep reservation history safe
        cursor.execute("""
            SELECT COUNT(*)
            FROM reservation
            WHERE book_id = %s;
        """, (book_id,))

        reservation_count = cursor.fetchone()[0]

        if reservation_count > 0:
            return jsonify({
                "error": (
                    "This book cannot be deleted because "
                    "it has reservation records."
                )
            }), 400

        # Keep review history safe
        cursor.execute("""
            SELECT COUNT(*)
            FROM book_review
            WHERE book_id = %s;
        """, (book_id,))

        review_count = cursor.fetchone()[0]

        if review_count > 0:
            return jsonify({
                "error": (
                    "This book cannot be deleted because "
                    "it has review records."
                )
            }), 400

        # Delete physical copies first
        cursor.execute("""
            DELETE FROM book_copy
            WHERE book_id = %s;
        """, (book_id,))

        # Delete book-author links
        cursor.execute("""
            DELETE FROM book_author
            WHERE book_id = %s;
        """, (book_id,))

        # Delete the book
        cursor.execute("""
            DELETE FROM book
            WHERE id = %s;
        """, (book_id,))

        conn.commit()

        log_action(
            session['member_id'],
            "DELETE_BOOK",
            f"Deleted book ID {book_id}: '{book_title}'."
        )

        return jsonify({
            "message": f"'{book_title}' was deleted successfully."
        }), 200

    except Exception:

        conn.rollback()

        return jsonify({
            "error": "Could not delete the book."
        }), 500

    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    app.run(debug=False)
