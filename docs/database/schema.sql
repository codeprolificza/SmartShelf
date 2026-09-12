-- SmartShelf PostgreSQL schema
-- Run this file on PostgreSQL 15+.

BEGIN;

CREATE TYPE account_status AS ENUM ('ACTIVE', 'SUSPENDED', 'INACTIVE');
CREATE TYPE role_code AS ENUM ('STUDENT', 'STAFF', 'ADMIN');
CREATE TYPE admin_request_status AS ENUM ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED');
CREATE TYPE copy_status AS ENUM ('AVAILABLE', 'BORROWED', 'RESERVED', 'LOST', 'DAMAGED', 'MAINTENANCE');
CREATE TYPE loan_status AS ENUM ('ACTIVE', 'RETURNED', 'OVERDUE', 'LOST');
CREATE TYPE reservation_status AS ENUM ('PENDING', 'READY', 'CANCELLED', 'FULFILLED', 'EXPIRED');
CREATE TYPE notification_type AS ENUM ('DUE_SOON', 'DUE_TODAY', 'OVERDUE', 'RESERVATION_READY', 'GENERAL');

CREATE TABLE faculty (
    faculty_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    faculty_name varchar(150) NOT NULL UNIQUE
);

CREATE TABLE department (
    department_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    faculty_id bigint NOT NULL REFERENCES faculty(faculty_id) ON DELETE RESTRICT,
    department_name varchar(150) NOT NULL,
    UNIQUE (faculty_id, department_name)
);

CREATE TABLE programme (
    programme_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    department_id bigint NOT NULL REFERENCES department(department_id) ON DELETE RESTRICT,
    programme_code varchar(20) NOT NULL UNIQUE,
    programme_name varchar(200) NOT NULL,
    qualification_level varchar(50) NOT NULL
);

CREATE TABLE app_user (
    user_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    university_id char(9) NOT NULL UNIQUE CHECK (university_id ~ '^[0-9]{9}$'),
    first_name varchar(100) NOT NULL,
    last_name varchar(100) NOT NULL,
    email varchar(254) NOT NULL UNIQUE CHECK (email = lower(email)),
    password_hash text NOT NULL,
    account_status account_status NOT NULL DEFAULT 'ACTIVE',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app_role (
    role_id smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    role_name role_code NOT NULL UNIQUE,
    description varchar(300) NOT NULL
);

CREATE TABLE user_role (
    user_role_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
    role_id smallint NOT NULL REFERENCES app_role(role_id) ON DELETE RESTRICT,
    granted_at timestamptz NOT NULL DEFAULT now(),
    granted_by_user_id bigint REFERENCES app_user(user_id) ON DELETE RESTRICT,
    revoked_at timestamptz,
    CHECK (revoked_at IS NULL OR revoked_at >= granted_at)
);

CREATE TABLE student_profile (
    user_id bigint PRIMARY KEY REFERENCES app_user(user_id) ON DELETE CASCADE,
    programme_id bigint NOT NULL REFERENCES programme(programme_id) ON DELETE RESTRICT,
    student_number varchar(30) NOT NULL UNIQUE,
    year_of_study smallint NOT NULL CHECK (year_of_study BETWEEN 1 AND 10)
);

CREATE TABLE staff_profile (
    user_id bigint PRIMARY KEY REFERENCES app_user(user_id) ON DELETE CASCADE,
    department_id bigint NOT NULL REFERENCES department(department_id) ON DELETE RESTRICT,
    staff_number varchar(30) NOT NULL UNIQUE
);

CREATE TABLE admin_role_request (
    admin_request_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
    request_reason text,
    request_status admin_request_status NOT NULL DEFAULT 'PENDING',
    requested_at timestamptz NOT NULL DEFAULT now(),
    reviewed_by_user_id bigint REFERENCES app_user(user_id) ON DELETE RESTRICT,
    reviewed_at timestamptz,
    review_note text,
    CHECK ((request_status IN ('APPROVED', 'REJECTED')) = (reviewed_at IS NOT NULL)),
    CHECK (reviewed_at IS NULL OR reviewed_by_user_id IS NOT NULL),
    CHECK (reviewed_at IS NULL OR reviewed_at >= requested_at)
);

CREATE TABLE password_reset_token (
    reset_token_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
    token_hash text NOT NULL UNIQUE,
    expires_at timestamptz NOT NULL,
    used_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (expires_at > created_at),
    CHECK (used_at IS NULL OR used_at <= expires_at)
);

CREATE TABLE user_session (
    session_id uuid PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_activity_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    CHECK (expires_at > created_at),
    CHECK (last_activity_at >= created_at),
    CHECK (revoked_at IS NULL OR revoked_at >= created_at)
);

CREATE TABLE interest (
    interest_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    interest_name varchar(100) NOT NULL UNIQUE
);

CREATE TABLE user_interest (
    user_id bigint NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
    interest_id bigint NOT NULL REFERENCES interest(interest_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, interest_id)
);

CREATE TABLE book (
    book_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    isbn13 char(13) UNIQUE CHECK (isbn13 IS NULL OR isbn13 ~ '^[0-9]{13}$'),
    title varchar(500) NOT NULL,
    description text,
    publisher varchar(200),
    publication_year smallint CHECK (publication_year BETWEEN 1450 AND 2100),
    edition varchar(50),
    language_code char(2) NOT NULL DEFAULT 'en' CHECK (language_code ~ '^[a-z]{2}$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE author (
    author_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    first_name varchar(100),
    last_name varchar(150) NOT NULL
);

CREATE TABLE book_author (
    book_id bigint NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
    author_id bigint NOT NULL REFERENCES author(author_id) ON DELETE RESTRICT,
    author_order smallint NOT NULL CHECK (author_order > 0),
    PRIMARY KEY (book_id, author_id),
    UNIQUE (book_id, author_order)
);

CREATE TABLE category (
    category_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    category_name varchar(100) NOT NULL UNIQUE,
    description varchar(500)
);

CREATE TABLE book_category (
    book_id bigint NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
    category_id bigint NOT NULL REFERENCES category(category_id) ON DELETE RESTRICT,
    PRIMARY KEY (book_id, category_id)
);

CREATE TABLE subject (
    subject_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_name varchar(150) NOT NULL UNIQUE
);

CREATE TABLE book_subject (
    book_id bigint NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
    subject_id bigint NOT NULL REFERENCES subject(subject_id) ON DELETE RESTRICT,
    PRIMARY KEY (book_id, subject_id)
);

CREATE TABLE keyword (
    keyword_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    keyword_text varchar(100) NOT NULL UNIQUE
);

CREATE TABLE book_keyword (
    book_id bigint NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
    keyword_id bigint NOT NULL REFERENCES keyword(keyword_id) ON DELETE RESTRICT,
    PRIMARY KEY (book_id, keyword_id)
);

CREATE TABLE book_copy (
    copy_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    book_id bigint NOT NULL REFERENCES book(book_id) ON DELETE RESTRICT,
    barcode varchar(50) NOT NULL UNIQUE,
    copy_status copy_status NOT NULL DEFAULT 'AVAILABLE',
    acquired_at date,
    shelf_location varchar(100),
    condition_notes text
);

CREATE TABLE loan (
    loan_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    copy_id bigint NOT NULL REFERENCES book_copy(copy_id) ON DELETE RESTRICT,
    user_id bigint NOT NULL REFERENCES app_user(user_id) ON DELETE RESTRICT,
    issued_by_user_id bigint REFERENCES app_user(user_id) ON DELETE RESTRICT,
    borrowed_at timestamptz NOT NULL DEFAULT now(),
    due_at timestamptz NOT NULL,
    returned_at timestamptz,
    returned_by_user_id bigint REFERENCES app_user(user_id) ON DELETE RESTRICT,
    loan_status loan_status NOT NULL DEFAULT 'ACTIVE',
    renewal_count smallint NOT NULL DEFAULT 0 CHECK (renewal_count >= 0),
    CHECK (due_at > borrowed_at),
    CHECK (returned_at IS NULL OR returned_at >= borrowed_at),
    CHECK ((loan_status = 'RETURNED') = (returned_at IS NOT NULL))
);

CREATE TABLE reservation (
    reservation_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    book_id bigint NOT NULL REFERENCES book(book_id) ON DELETE RESTRICT,
    user_id bigint NOT NULL REFERENCES app_user(user_id) ON DELETE RESTRICT,
    requested_at timestamptz NOT NULL DEFAULT now(),
    queue_position integer NOT NULL CHECK (queue_position > 0),
    reservation_status reservation_status NOT NULL DEFAULT 'PENDING',
    allocated_copy_id bigint REFERENCES book_copy(copy_id) ON DELETE RESTRICT,
    expires_at timestamptz,
    cancelled_at timestamptz,
    fulfilled_at timestamptz,
    CHECK (expires_at IS NULL OR expires_at >= requested_at),
    CHECK (cancelled_at IS NULL OR cancelled_at >= requested_at),
    CHECK (fulfilled_at IS NULL OR fulfilled_at >= requested_at)
);

CREATE TABLE book_rating (
    rating_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    book_id bigint NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
    user_id bigint NOT NULL REFERENCES app_user(user_id) ON DELETE RESTRICT,
    rating_value smallint NOT NULL CHECK (rating_value BETWEEN 1 AND 5),
    review_text text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, book_id)
);

CREATE TABLE notification (
    notification_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
    loan_id bigint REFERENCES loan(loan_id) ON DELETE SET NULL,
    notification_type notification_type NOT NULL,
    title varchar(200) NOT NULL,
    message text NOT NULL,
    is_read boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    sent_at timestamptz
);

CREATE TABLE recommendation (
    recommendation_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
    book_id bigint NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
    recommendation_score numeric(6, 3) NOT NULL CHECK (recommendation_score >= 0),
    reason varchar(500) NOT NULL,
    generated_at timestamptz NOT NULL DEFAULT now(),
    is_dismissed boolean NOT NULL DEFAULT false,
    UNIQUE (user_id, book_id)
);

CREATE TABLE audit_log (
    audit_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id bigint REFERENCES app_user(user_id) ON DELETE SET NULL,
    action_type varchar(100) NOT NULL,
    entity_name varchar(100) NOT NULL,
    entity_id bigint,
    old_values jsonb,
    new_values jsonb,
    ip_address inet,
    action_at timestamptz NOT NULL DEFAULT now()
);

-- Integrity and query-performance indexes.
CREATE UNIQUE INDEX uq_user_role_active ON user_role (user_id, role_id) WHERE revoked_at IS NULL;
CREATE UNIQUE INDEX uq_active_loan_per_copy ON loan (copy_id) WHERE loan_status IN ('ACTIVE', 'OVERDUE');
CREATE UNIQUE INDEX uq_active_reservation_per_user_book
    ON reservation (user_id, book_id)
    WHERE reservation_status IN ('PENDING', 'READY');
CREATE UNIQUE INDEX uq_active_reservation_position_per_book
    ON reservation (book_id, queue_position)
    WHERE reservation_status IN ('PENDING', 'READY');
CREATE INDEX ix_book_title ON book (title);
CREATE INDEX ix_book_copy_book_status ON book_copy (book_id, copy_status);
CREATE INDEX ix_loan_user_status ON loan (user_id, loan_status);
CREATE INDEX ix_reservation_book_status_position ON reservation (book_id, reservation_status, queue_position);
CREATE INDEX ix_notification_user_unread ON notification (user_id, created_at DESC) WHERE is_read = false;
CREATE INDEX ix_recommendation_user_score ON recommendation (user_id, recommendation_score DESC);

-- Keeps common modification timestamps correct.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_app_user_updated_at
BEFORE UPDATE ON app_user
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_book_updated_at
BEFORE UPDATE ON book
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_book_rating_updated_at
BEFORE UPDATE ON book_rating
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Seed the three roles specified for SmartShelf.
INSERT INTO app_role (role_name, description) VALUES
    ('STUDENT', 'Verified university student with normal library access.'),
    ('STAFF', 'Verified university staff member with normal library access.'),
    ('ADMIN', 'Approved administrator with library management privileges.');

COMMIT;

-- Business rules enforced by the application or a later trigger:
-- 1. A student/staff profile must match the active normal role.
-- 2. Only verified staff or postgraduate students may be approved as ADMIN.
-- 3. Only an existing ADMIN may approve an admin role request or record returns.
-- 4. A rating requires a current or historic loan for a copy of the rated book.
-- 5. A copy status changes with loan and reservation transitions.
