-- ================================================
-- Smart Library Management System
-- PostgreSQL Database Schema
-- Matches the ER diagram provided by the team
-- ================================================

-- Drop tables if they already exist (useful when re-running during testing)
DROP TABLE IF EXISTS fine_payment CASCADE;
DROP TABLE IF EXISTS fine CASCADE;
DROP TABLE IF EXISTS reservation CASCADE;
DROP TABLE IF EXISTS reservation_status CASCADE;
DROP TABLE IF EXISTS loan CASCADE;
DROP TABLE IF EXISTS book_author CASCADE;
DROP TABLE IF EXISTS book CASCADE;
DROP TABLE IF EXISTS author CASCADE;
DROP TABLE IF EXISTS category CASCADE;
DROP TABLE IF EXISTS member CASCADE;
DROP TABLE IF EXISTS member_status CASCADE;


-- ================================================
-- 1. Standalone lookup tables (no dependencies)
-- ================================================

CREATE TABLE category (
    id SERIAL PRIMARY KEY,
    category_name VARCHAR(100) NOT NULL
);

CREATE TABLE author (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL
);

CREATE TABLE member_status (
    id SERIAL PRIMARY KEY,
    status_value VARCHAR(50) NOT NULL  -- e.g. 'Active', 'Inactive', 'Suspended'
);

CREATE TABLE reservation_status (
    id SERIAL PRIMARY KEY,
    status_value VARCHAR(50) NOT NULL  -- e.g. 'Pending', 'Fulfilled', 'Cancelled'
);


-- ================================================
-- 2. Tables that depend on the lookup tables above
-- ================================================

CREATE TABLE book (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    category_id INTEGER REFERENCES category(id),
    publication_date DATE,
    copies_owned INTEGER DEFAULT 1
);

CREATE TABLE member (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    joined_date DATE DEFAULT CURRENT_DATE,
    active_status_id INTEGER REFERENCES member_status(id)
);


-- ================================================
-- 3. Link table: books can have multiple authors,
--    and an author can write multiple books
-- ================================================

CREATE TABLE book_author (
    book_id INTEGER REFERENCES book(id),
    author_id INTEGER REFERENCES author(id),
    PRIMARY KEY (book_id, author_id)
);


-- ================================================
-- 4. Loans - who borrowed which book, and when
-- ================================================

CREATE TABLE loan (
    id SERIAL PRIMARY KEY,
    book_id INTEGER REFERENCES book(id),
    member_id INTEGER REFERENCES member(id),
    loan_date DATE DEFAULT CURRENT_DATE,
    returned_date DATE  -- NULL until the book is actually returned
);


-- ================================================
-- 5. Reservations - a member reserving a book
--    before it's available to borrow
-- ================================================

CREATE TABLE reservation (
    id SERIAL PRIMARY KEY,
    book_id INTEGER REFERENCES book(id),
    member_id INTEGER REFERENCES member(id),
    reservation_date DATE DEFAULT CURRENT_DATE,
    reservation_status_id INTEGER REFERENCES reservation_status(id)
);


-- ================================================
-- 6. Fines - charges for a member linked to a loan
--    (e.g. for returning a book late)
-- ================================================

CREATE TABLE fine (
    id SERIAL PRIMARY KEY,
    member_id INTEGER REFERENCES member(id),
    loan_id INTEGER REFERENCES loan(id),
    fine_date DATE DEFAULT CURRENT_DATE,
    fine_amount NUMERIC(10, 2) NOT NULL
);


-- ================================================
-- 7. Fine payments - records of a fine being paid
-- ================================================

CREATE TABLE fine_payment (
    id SERIAL PRIMARY KEY,
    member_id INTEGER REFERENCES member(id),
    payment_date DATE DEFAULT CURRENT_DATE,
    payment_amount NUMERIC(10, 2) NOT NULL
);


-- ================================================
-- Done! Run this whole file in pgAdmin's Query Tool
-- to create all 11 tables in one go.
-- ================================================
