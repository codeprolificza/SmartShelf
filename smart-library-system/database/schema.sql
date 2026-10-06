-- ============================================================
-- UniLibrary / SmartShelf
-- FINAL PostgreSQL DATABASE SCHEMA
-- ============================================================
--
-- This is the complete database definition used by app.py.
--
-- IMPORTANT:
-- This script DROPS the existing tables and recreates them.
-- BACK UP YOUR DATABASE BEFORE RUNNING THIS IN PRODUCTION.
--
-- Fine policy:
--   Overdue  = R25.00 per overdue day
--   Lost     = book.market_value
--   Damaged  = book.market_value
--
-- Active overdue fines are calculated dynamically from CURRENT_DATE.
-- The application does NOT create a new fine row every day.
--
-- A fine is finalized when the book is:
--   1. Returned
--   2. Marked LOST
--   3. Marked DAMAGED
-- ============================================================


BEGIN;


-- ============================================================
-- DROP EXISTING TABLES
-- ============================================================

DROP TABLE IF EXISTS notification CASCADE;
DROP TABLE IF EXISTS book_review CASCADE;
DROP TABLE IF EXISTS password_reset CASCADE;
DROP TABLE IF EXISTS purchase_request CASCADE;
DROP TABLE IF EXISTS audit_log CASCADE;
DROP TABLE IF EXISTS announcement CASCADE;
DROP TABLE IF EXISTS member_interest CASCADE;
DROP TABLE IF EXISTS fine_payment CASCADE;
DROP TABLE IF EXISTS fine CASCADE;
DROP TABLE IF EXISTS reservation CASCADE;
DROP TABLE IF EXISTS reservation_status CASCADE;
DROP TABLE IF EXISTS loan CASCADE;
DROP TABLE IF EXISTS book_copy CASCADE;
DROP TABLE IF EXISTS book_author CASCADE;
DROP TABLE IF EXISTS book CASCADE;
DROP TABLE IF EXISTS author CASCADE;
DROP TABLE IF EXISTS category CASCADE;
DROP TABLE IF EXISTS member CASCADE;
DROP TABLE IF EXISTS member_status CASCADE;


-- ============================================================
-- CATEGORY
-- ============================================================

CREATE TABLE category (
    id SERIAL PRIMARY KEY,

    category_name VARCHAR(100) NOT NULL UNIQUE
);


-- ============================================================
-- AUTHOR
-- ============================================================

CREATE TABLE author (
    id SERIAL PRIMARY KEY,

    first_name VARCHAR(100) NOT NULL,

    last_name VARCHAR(100) NOT NULL,

    UNIQUE (first_name, last_name)
);


-- ============================================================
-- MEMBER STATUS
-- ============================================================

CREATE TABLE member_status (
    id SERIAL PRIMARY KEY,

    status_value VARCHAR(50) NOT NULL UNIQUE
);


-- ============================================================
-- RESERVATION STATUS
-- ============================================================

CREATE TABLE reservation_status (
    id SERIAL PRIMARY KEY,

    status_value VARCHAR(50) NOT NULL UNIQUE
);


-- ============================================================
-- MEMBER
-- ============================================================

CREATE TABLE member (
    id SERIAL PRIMARY KEY,

    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,

    joined_date DATE NOT NULL DEFAULT CURRENT_DATE,

    active_status_id INTEGER NOT NULL
        REFERENCES member_status(id)
        ON DELETE RESTRICT,

    email VARCHAR(255) UNIQUE,

    password_hash VARCHAR(255),

    role VARCHAR(20) NOT NULL DEFAULT 'student'
        CHECK (role IN ('student', 'staff', 'admin')),

    faculty VARCHAR(100),

    department VARCHAR(100),

    programme VARCHAR(150),

    CHECK (email IS NULL OR email = LOWER(email))
);


-- ============================================================
-- BOOK
-- ============================================================
CREATE TABLE book (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    category_id INTEGER REFERENCES category(id) ON DELETE SET NULL,
    publication_date DATE,
    copies_owned INTEGER NOT NULL DEFAULT 1 CHECK (copies_owned >= 0),

    -- Replacement / market value used when a book is lost
    -- or significantly damaged.
    market_value NUMERIC(10,2) NOT NULL DEFAULT 0.00
        CHECK (market_value >= 0)
);

-- ============================================================
-- BOOK AUTHOR
-- ============================================================

CREATE TABLE book_author (
    book_id INTEGER NOT NULL
        REFERENCES book(id)
        ON DELETE CASCADE,

    author_id INTEGER NOT NULL
        REFERENCES author(id)
        ON DELETE RESTRICT,

    PRIMARY KEY (book_id, author_id)
);


-- ============================================================
-- BOOK COPY
-- ============================================================

CREATE TABLE book_copy (
    copy_id SERIAL PRIMARY KEY,

    book_id INTEGER NOT NULL
        REFERENCES book(id)
        ON DELETE RESTRICT,

    barcode VARCHAR(100) NOT NULL UNIQUE,

    copy_status VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE'
        CHECK (
            copy_status IN (
                'AVAILABLE',
                'BORROWED',
                'RESERVED',
                'LOST',
                'DAMAGED',
                'MAINTENANCE'
            )
        )
);


-- ============================================================
-- LOAN
-- ============================================================

CREATE TABLE loan (
    id SERIAL PRIMARY KEY,

    book_id INTEGER NOT NULL
        REFERENCES book(id) ON DELETE RESTRICT,

    member_id INTEGER NOT NULL
        REFERENCES member(id) ON DELETE RESTRICT,

    copy_id INTEGER
        REFERENCES book_copy(copy_id) ON DELETE RESTRICT,

    loan_date DATE NOT NULL DEFAULT CURRENT_DATE,

    due_date DATE,

    returned_date DATE,

    loan_status VARCHAR(20) NOT NULL DEFAULT 'BORROWED'
        CHECK (
            loan_status IN (
                'BORROWED',
                'OVERDUE',
                'RETURNED',
                'LOST',
                'DAMAGED'
            )
        ),

    CHECK (
        due_date IS NULL
        OR due_date >= loan_date
    ),

    CHECK (
        returned_date IS NULL
        OR returned_date >= loan_date
    )
);

-- ============================================================
-- RESERVATION
-- ============================================================

CREATE TABLE reservation (
    id SERIAL PRIMARY KEY,

    book_id INTEGER NOT NULL
        REFERENCES book(id)
        ON DELETE RESTRICT,

    member_id INTEGER NOT NULL
        REFERENCES member(id)
        ON DELETE RESTRICT,

    reservation_date DATE NOT NULL DEFAULT CURRENT_DATE,

    reservation_status_id INTEGER NOT NULL
        REFERENCES reservation_status(id)
        ON DELETE RESTRICT,

    queue_position INTEGER
        CHECK (queue_position > 0),

    allocated_copy_id INTEGER
        REFERENCES book_copy(copy_id)
        ON DELETE RESTRICT,

    expires_at DATE,

    CHECK (
        expires_at IS NULL
        OR expires_at >= reservation_date
    )
);


-- ============================================================
-- FINE
-- ============================================================

CREATE TABLE fine (
    id SERIAL PRIMARY KEY,

    member_id INTEGER NOT NULL
        REFERENCES member(id) ON DELETE RESTRICT,

    loan_id INTEGER NOT NULL
        REFERENCES loan(id) ON DELETE RESTRICT,

    fine_date DATE NOT NULL DEFAULT CURRENT_DATE,

    fine_amount NUMERIC(10,2) NOT NULL
        CHECK (fine_amount > 0),

    fine_type VARCHAR(30) NOT NULL DEFAULT 'OVERDUE'
        CHECK (
            fine_type IN (
                'OVERDUE',
                'LOST',
                'DAMAGED'
            )
        ),

    status VARCHAR(20) NOT NULL DEFAULT 'OUTSTANDING'
        CHECK (
            status IN (
                'OUTSTANDING',
                'PAID',
                'WAIVED'
            )
        ),

    notes TEXT,

    finalized_at TIMESTAMP
);


-- ============================================================
-- FINE PAYMENT
-- ============================================================

CREATE TABLE fine_payment (
    id SERIAL PRIMARY KEY,

    member_id INTEGER NOT NULL
        REFERENCES member(id)
        ON DELETE RESTRICT,

    payment_date DATE NOT NULL DEFAULT CURRENT_DATE,

    payment_amount NUMERIC(10,2) NOT NULL
        CHECK (payment_amount > 0)
);


-- ============================================================
-- MEMBER INTEREST
-- ============================================================

CREATE TABLE member_interest (
    member_id INTEGER NOT NULL
        REFERENCES member(id)
        ON DELETE CASCADE,

    category_id INTEGER NOT NULL
        REFERENCES category(id)
        ON DELETE RESTRICT,

    PRIMARY KEY (member_id, category_id)
);


-- ============================================================
-- ANNOUNCEMENT
-- ============================================================

CREATE TABLE announcement (
    id SERIAL PRIMARY KEY,

    title VARCHAR(255) NOT NULL,

    body TEXT NOT NULL,

    created_at TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_by INTEGER
        REFERENCES member(id)
        ON DELETE SET NULL
);


-- ============================================================
-- AUDIT LOG
-- ============================================================

CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,

    member_id INTEGER
        REFERENCES member(id)
        ON DELETE SET NULL,

    action VARCHAR(100) NOT NULL,

    details TEXT,

    created_at TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- PURCHASE REQUEST
-- ============================================================

CREATE TABLE purchase_request (
    id SERIAL PRIMARY KEY,

    member_id INTEGER NOT NULL
        REFERENCES member(id)
        ON DELETE RESTRICT,

    title VARCHAR(255) NOT NULL,

    author VARCHAR(255),

    reason TEXT,

    request_date DATE NOT NULL DEFAULT CURRENT_DATE,

    status VARCHAR(30) NOT NULL DEFAULT 'PENDING'
        CHECK (
            status IN (
                'PENDING',
                'APPROVED',
                'REJECTED',
                'ORDERED'
            )
        )
);


-- ============================================================
-- PASSWORD RESET
-- ============================================================

CREATE TABLE password_reset (
    id SERIAL PRIMARY KEY,

    member_id INTEGER NOT NULL
        REFERENCES member(id)
        ON DELETE CASCADE,

    reset_token VARCHAR(255) NOT NULL UNIQUE,

    expires_at TIMESTAMP NOT NULL,

    used BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- BOOK REVIEW
-- ============================================================

CREATE TABLE book_review (
    id SERIAL PRIMARY KEY,

    book_id INTEGER NOT NULL
        REFERENCES book(id)
        ON DELETE CASCADE,

    member_id INTEGER NOT NULL
        REFERENCES member(id)
        ON DELETE CASCADE,

    rating SMALLINT NOT NULL
        CHECK (rating BETWEEN 1 AND 5),

    review_text TEXT,

    created_at TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (book_id, member_id)
);


-- ============================================================
-- NOTIFICATION
-- ============================================================
--
-- Notifications are linked to either:
--
--   loan
--   reservation
--   or are GENERAL notifications.
--
-- Supported notification types:
--
--   BORROWED
--   DUE_SOON
--   DUE_TODAY
--   OVERDUE
--   LOST
--   DAMAGED
--   RESERVATION_READY
--   GENERAL
--
-- DUE_SOON is used for the formal reminder one day before
-- the book's due date.
-- ============================================================

CREATE TABLE notification (
    id SERIAL PRIMARY KEY,

    member_id INTEGER NOT NULL
        REFERENCES member(id) ON DELETE CASCADE,

    loan_id INTEGER
        REFERENCES loan(id) ON DELETE CASCADE,

    reservation_id INTEGER
        REFERENCES reservation(id) ON DELETE CASCADE,

    notification_type VARCHAR(30) NOT NULL
        CHECK (
            notification_type IN (
                'BOOK_BORROWED',
                'DUE_TOMORROW',
                'DUE_TODAY',
                'OVERDUE',
                'RESERVATION_READY',
                'GENERAL'
            )
        ),

    title VARCHAR(255) NOT NULL,

    message TEXT NOT NULL,

    is_read BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (
        loan_id IS NOT NULL
        OR reservation_id IS NOT NULL
        OR notification_type = 'GENERAL'
    )
);


-- ============================================================
-- INDEXES
-- ============================================================

-- Prevent a physical copy from being borrowed twice
-- at the same time.
CREATE INDEX ix_book_copy_book_status
    ON book_copy (book_id, copy_status);

CREATE INDEX ix_loan_member_returned
    ON loan (member_id, returned_date);

CREATE INDEX ix_loan_status
    ON loan (loan_status);

CREATE INDEX ix_loan_due_date
    ON loan (due_date);

CREATE INDEX ix_notification_member_created
    ON notification (member_id, created_at DESC);

CREATE INDEX ix_notification_member_type
    ON notification (member_id, notification_type);

CREATE INDEX ix_fine_member_status
    ON fine (member_id, status);


-- ============================================================
-- OVERDUE FINE CALCULATION FUNCTION
-- ============================================================
--
-- R25.00 per overdue day.
--
-- Example:
--
--   1 day late  = R25
--   2 days late = R50
--   3 days late = R75
--   7 days late = R175
--
-- Lost/damaged books do not accrue normal overdue fines.
-- Their replacement charge is handled separately using
-- book.market_value.
-- ============================================================

CREATE OR REPLACE FUNCTION calculate_overdue_fine(
    p_loan_id INTEGER
)
RETURNS NUMERIC(10,2)
LANGUAGE plpgsql
AS $$
DECLARE

    v_due_date DATE;

    v_returned_date DATE;

    v_status VARCHAR(20);

    v_overdue_days INTEGER;

BEGIN

    SELECT
        due_date,
        returned_date,
        loan_status

    INTO
        v_due_date,
        v_returned_date,
        v_status

    FROM loan

    WHERE id = p_loan_id;


    -- Loan does not exist or has no due date.
    IF v_due_date IS NULL THEN
        RETURN 0.00;
    END IF;


    -- Lost and damaged books use market/replacement value
    -- rather than continuing the normal overdue calculation.
    IF v_status IN ('LOST', 'DAMAGED') THEN
        RETURN 0.00;
    END IF;


    -- Returned book:
    -- calculate the number of days between the due date
    -- and the actual return date.
    IF v_returned_date IS NOT NULL THEN

        v_overdue_days :=
            GREATEST(
                v_returned_date - v_due_date,
                0
            );

    ELSE

        -- Active loan:
        -- calculate against today's date.
        v_overdue_days :=
            GREATEST(
                CURRENT_DATE - v_due_date,
                0
            );

    END IF;


    -- R25.00 per overdue day.
    RETURN v_overdue_days * 25.00;

END;
$$;


-- ============================================================
-- COMMIT
-- ============================================================

COMMIT;


-- ============================================================
-- APPLICATION-ENFORCED RULES
-- ============================================================
--
-- * Only an eligible logged-in role may borrow, administer,
--   or manage records.
--
-- * Students/staff receive a formal borrowing notification
--   after a successful loan.
--
-- * Students/staff receive a DUE_SOON notification one day
--   before the due date.
--
-- * Overdue books accrue R25.00 per overdue day.
--
-- * The application calculates active overdue fines from
--   CURRENT_DATE instead of inserting a new fine row every day.
--
-- * When an overdue book is returned, the overdue fine is
--   finalized.
--
-- * When a book is marked LOST, normal overdue charging stops
--   and the book.market_value becomes the replacement charge.
--
-- * When a book is marked DAMAGED, normal overdue charging
--   stops and the book.market_value becomes the replacement
--   charge.
--
-- * A review requires a previous loan for the same member
--   and book.
--
-- * Returning a copy releases it or allocates it to the
--   next pending reservation.
--
-- * Notifications are displayed through the member dashboard.
--
-- ============================================================