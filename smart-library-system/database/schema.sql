-- SmartShelf final PostgreSQL database schema
-- This file is the complete database definition used by smart-library-system/app.py.
-- It replaces the earlier base-schema-plus-manual-migrations setup.

BEGIN;

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

CREATE TABLE category (
    id SERIAL PRIMARY KEY,
    category_name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE author (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    UNIQUE (first_name, last_name)
);

CREATE TABLE member_status (
    id SERIAL PRIMARY KEY,
    status_value VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE reservation_status (
    id SERIAL PRIMARY KEY,
    status_value VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE member (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    joined_date DATE NOT NULL DEFAULT CURRENT_DATE,
    active_status_id INTEGER NOT NULL REFERENCES member_status(id) ON DELETE RESTRICT,
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255),
    role VARCHAR(20) NOT NULL DEFAULT 'student'
        CHECK (role IN ('student', 'staff', 'admin')),
    faculty VARCHAR(100),
    CHECK (email IS NULL OR email = LOWER(email))
);

CREATE TABLE book (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    category_id INTEGER REFERENCES category(id) ON DELETE SET NULL,
    publication_date DATE,
    copies_owned INTEGER NOT NULL DEFAULT 1 CHECK (copies_owned >= 0)
);

CREATE TABLE book_author (
    book_id INTEGER NOT NULL REFERENCES book(id) ON DELETE CASCADE,
    author_id INTEGER NOT NULL REFERENCES author(id) ON DELETE RESTRICT,
    PRIMARY KEY (book_id, author_id)
);

CREATE TABLE book_copy (
    copy_id SERIAL PRIMARY KEY,
    book_id INTEGER NOT NULL REFERENCES book(id) ON DELETE RESTRICT,
    barcode VARCHAR(100) NOT NULL UNIQUE,
    copy_status VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE'
        CHECK (copy_status IN ('AVAILABLE', 'BORROWED', 'RESERVED', 'LOST', 'DAMAGED', 'MAINTENANCE'))
);

CREATE TABLE loan (
    id SERIAL PRIMARY KEY,
    book_id INTEGER NOT NULL REFERENCES book(id) ON DELETE RESTRICT,
    member_id INTEGER NOT NULL REFERENCES member(id) ON DELETE RESTRICT,
    copy_id INTEGER REFERENCES book_copy(copy_id) ON DELETE RESTRICT,
    loan_date DATE NOT NULL DEFAULT CURRENT_DATE,
    due_date DATE,
    returned_date DATE,
    CHECK (due_date IS NULL OR due_date >= loan_date),
    CHECK (returned_date IS NULL OR returned_date >= loan_date)
);

CREATE TABLE reservation (
    id SERIAL PRIMARY KEY,
    book_id INTEGER NOT NULL REFERENCES book(id) ON DELETE RESTRICT,
    member_id INTEGER NOT NULL REFERENCES member(id) ON DELETE RESTRICT,
    reservation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    reservation_status_id INTEGER NOT NULL REFERENCES reservation_status(id) ON DELETE RESTRICT,
    queue_position INTEGER CHECK (queue_position > 0),
    allocated_copy_id INTEGER REFERENCES book_copy(copy_id) ON DELETE RESTRICT,
    expires_at DATE,
    CHECK (expires_at IS NULL OR expires_at >= reservation_date)
);

CREATE TABLE fine (
    id SERIAL PRIMARY KEY,
    member_id INTEGER NOT NULL REFERENCES member(id) ON DELETE RESTRICT,
    loan_id INTEGER NOT NULL REFERENCES loan(id) ON DELETE RESTRICT,
    fine_date DATE NOT NULL DEFAULT CURRENT_DATE,
    fine_amount NUMERIC(10, 2) NOT NULL CHECK (fine_amount > 0)
);

CREATE TABLE fine_payment (
    id SERIAL PRIMARY KEY,
    member_id INTEGER NOT NULL REFERENCES member(id) ON DELETE RESTRICT,
    payment_date DATE NOT NULL DEFAULT CURRENT_DATE,
    payment_amount NUMERIC(10, 2) NOT NULL CHECK (payment_amount > 0)
);

CREATE TABLE member_interest (
    member_id INTEGER NOT NULL REFERENCES member(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES category(id) ON DELETE RESTRICT,
    PRIMARY KEY (member_id, category_id)
);

CREATE TABLE announcement (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES member(id) ON DELETE SET NULL
);

CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    member_id INTEGER REFERENCES member(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    details TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE purchase_request (
    id SERIAL PRIMARY KEY,
    member_id INTEGER NOT NULL REFERENCES member(id) ON DELETE RESTRICT,
    title VARCHAR(255) NOT NULL,
    author VARCHAR(255),
    reason TEXT,
    request_date DATE NOT NULL DEFAULT CURRENT_DATE,
    status VARCHAR(30) NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'ORDERED'))
);

CREATE TABLE password_reset (
    id SERIAL PRIMARY KEY,
    member_id INTEGER NOT NULL REFERENCES member(id) ON DELETE CASCADE,
    reset_token VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE book_review (
    id SERIAL PRIMARY KEY,
    book_id INTEGER NOT NULL REFERENCES book(id) ON DELETE CASCADE,
    member_id INTEGER NOT NULL REFERENCES member(id) ON DELETE CASCADE,
    rating SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    review_text TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (book_id, member_id)
);

CREATE TABLE notification (
    id SERIAL PRIMARY KEY,
    member_id INTEGER NOT NULL REFERENCES member(id) ON DELETE CASCADE,
    loan_id INTEGER REFERENCES loan(id) ON DELETE CASCADE,
    reservation_id INTEGER REFERENCES reservation(id) ON DELETE CASCADE,
    notification_type VARCHAR(30) NOT NULL
        CHECK (notification_type IN ('DUE_SOON', 'DUE_TODAY', 'OVERDUE', 'RESERVATION_READY', 'GENERAL')),
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (loan_id IS NOT NULL OR reservation_id IS NOT NULL OR notification_type = 'GENERAL')
);

CREATE UNIQUE INDEX uq_active_loan_per_copy
    ON loan (copy_id) WHERE returned_date IS NULL AND copy_id IS NOT NULL;
CREATE UNIQUE INDEX uq_active_reservation_per_member_book
    ON reservation (member_id, book_id)
    WHERE reservation_status_id IN (1, 4);
CREATE UNIQUE INDEX uq_pending_reservation_position
    ON reservation (book_id, queue_position)
    WHERE reservation_status_id = 1;
CREATE INDEX ix_book_copy_book_status ON book_copy (book_id, copy_status);
CREATE INDEX ix_loan_member_returned ON loan (member_id, returned_date);
CREATE INDEX ix_notification_member_created ON notification (member_id, created_at DESC);

COMMIT;

-- Application-enforced rules:
-- * Only an eligible logged-in role may borrow, administer, or manage records.
-- * A review requires a previous loan for the same member and book.
-- * Returning a copy releases it or allocates it to the next pending reservation.
