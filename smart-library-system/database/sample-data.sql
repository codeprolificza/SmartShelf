-- ================================================
-- Smart Library Management System
-- Sample Data (for testing/demo purposes)
-- Run this AFTER schema.sql has created the tables
-- ================================================

-- 1. Categories
INSERT INTO category (category_name) VALUES
('Computer Science'),
('Mathematics'),
('Science'),
('Novels'),
('History');

-- 2. Authors
INSERT INTO author (first_name, last_name) VALUES
('John', 'Smith'),
('Raymond', 'Chang'),
('Jake', 'VanderPlas'),
('James', 'Stewart'),
('Chinua', 'Achebe');

-- 3. Books (category_id refers to the order categories were inserted above: 1=CS, 2=Maths, 3=Science, 4=Novels, 5=History)
INSERT INTO book (title, category_id, publication_date, copies_owned) VALUES
('Introduction to Programming', 1, '2020-01-15', 5),
('General Chemistry', 3, '2019-06-10', 3),
('Data Science', 1, '2021-03-22', 4),
('Advanced Mathematics', 2, '2018-09-01', 2),
('Things Fall Apart', 4, '1958-06-17', 6);

-- 3a. Physical copies (the application borrows and reserves individual copies)
INSERT INTO book_copy (book_id, barcode, copy_status) VALUES
(1, 'BOOK-1-COPY-1', 'AVAILABLE'),
(1, 'BOOK-1-COPY-2', 'AVAILABLE'),
(1, 'BOOK-1-COPY-3', 'AVAILABLE'),
(1, 'BOOK-1-COPY-4', 'AVAILABLE'),
(1, 'BOOK-1-COPY-5', 'AVAILABLE'),
(2, 'BOOK-2-COPY-1', 'AVAILABLE'),
(3, 'BOOK-3-COPY-1', 'AVAILABLE'),
(4, 'BOOK-4-COPY-1', 'AVAILABLE'),
(5, 'BOOK-5-COPY-1', 'AVAILABLE');

-- 4. Link books to their authors (book_id, author_id refer to insert order above)
INSERT INTO book_author (book_id, author_id) VALUES
(1, 1),  -- Introduction to Programming -> John Smith
(2, 2),  -- General Chemistry -> Raymond Chang
(3, 3),  -- Data Science -> Jake VanderPlas
(4, 4),  -- Advanced Mathematics -> James Stewart
(5, 5);  -- Things Fall Apart -> Chinua Achebe

-- 5. Member statuses
INSERT INTO member_status (status_value) VALUES
('Active'),
('Inactive'),
('Suspended');

-- 6. A sample member (active_status_id = 1, which is 'Active')
INSERT INTO member (first_name, last_name, active_status_id) VALUES
('Luthando', 'Rungqu', 1);

-- 7. Reservation statuses
INSERT INTO reservation_status (status_value) VALUES
('Pending'),
('Fulfilled'),
('Cancelled'),
('Ready');

-- 8. A sample loan (member 1 borrows book 1)
INSERT INTO loan (book_id, member_id, copy_id, loan_date, due_date) VALUES
(1, 1, 1, CURRENT_DATE, CURRENT_DATE + INTERVAL '14 days');

UPDATE book_copy SET copy_status = 'BORROWED' WHERE copy_id = 1;

-- 9. A sample reservation (member 1 reserves book 4, status = Pending)
INSERT INTO reservation (book_id, member_id, reservation_status_id) VALUES
(4, 1, 1);

-- ================================================
-- Done! Run this in pgAdmin's Query Tool after
-- schema.sql to fill your tables with test data.
-- ================================================
