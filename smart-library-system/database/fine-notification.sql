BEGIN;

-- ============================================
-- BOOK
-- ============================================

ALTER TABLE book
ADD COLUMN IF NOT EXISTS market_value NUMERIC(10,2)
NOT NULL DEFAULT 0.00;


-- ============================================
-- LOAN
-- ============================================

ALTER TABLE loan
ADD COLUMN IF NOT EXISTS loan_status VARCHAR(20)
NOT NULL DEFAULT 'BORROWED';


-- Normalize existing loans
UPDATE loan
SET loan_status =
    CASE
        WHEN returned_date IS NOT NULL THEN 'RETURNED'
        WHEN due_date < CURRENT_DATE THEN 'OVERDUE'
        ELSE 'BORROWED'
    END;


-- ============================================
-- FINE
-- ============================================

ALTER TABLE fine
ADD COLUMN IF NOT EXISTS fine_type VARCHAR(30)
NOT NULL DEFAULT 'OVERDUE';

ALTER TABLE fine
ADD COLUMN IF NOT EXISTS status VARCHAR(20)
NOT NULL DEFAULT 'OUTSTANDING';

ALTER TABLE fine
ADD COLUMN IF NOT EXISTS notes TEXT;

ALTER TABLE fine
ADD COLUMN IF NOT EXISTS finalized_at TIMESTAMP;


-- ============================================
-- LOAN STATUS INDEX
-- ============================================

CREATE INDEX IF NOT EXISTS ix_loan_status
ON loan(loan_status);

CREATE INDEX IF NOT EXISTS ix_loan_due_date
ON loan(due_date);


-- ============================================
-- FINE INDEX
-- ============================================

CREATE INDEX IF NOT EXISTS ix_fine_member_status
ON fine(member_id, status);


-- ============================================
-- NOTIFICATION INDEX
-- ============================================

CREATE INDEX IF NOT EXISTS ix_notification_member_created
ON notification(member_id, created_at DESC);


-- ============================================
-- FIX NOTIFICATION TYPE CONSTRAINT
-- ============================================

ALTER TABLE notification
DROP CONSTRAINT IF EXISTS notification_notification_type_check;

ALTER TABLE notification
ADD CONSTRAINT notification_notification_type_check
CHECK (
    notification_type IN (
        'BOOK_BORROWED',
        'DUE_TOMORROW',
        'DUE_TODAY',
        'OVERDUE',
        'RESERVATION_READY',
        'GENERAL'
    )
);


-- ============================================
-- FINE TYPE CONSTRAINT
-- ============================================

ALTER TABLE fine
DROP CONSTRAINT IF EXISTS fine_fine_type_check;

ALTER TABLE fine
ADD CONSTRAINT fine_fine_type_check
CHECK (
    fine_type IN (
        'OVERDUE',
        'LOST',
        'DAMAGED'
    )
);


-- ============================================
-- FINE STATUS CONSTRAINT
-- ============================================

ALTER TABLE fine
DROP CONSTRAINT IF EXISTS fine_status_check;

ALTER TABLE fine
ADD CONSTRAINT fine_status_check
CHECK (
    status IN (
        'OUTSTANDING',
        'PAID',
        'WAIVED'
    )
);


-- ============================================
-- LOAN STATUS CONSTRAINT
-- ============================================

ALTER TABLE loan
DROP CONSTRAINT IF EXISTS loan_loan_status_check;

ALTER TABLE loan
ADD CONSTRAINT loan_loan_status_check
CHECK (
    loan_status IN (
        'BORROWED',
        'OVERDUE',
        'RETURNED',
        'LOST',
        'DAMAGED'
    )
);

COMMIT;