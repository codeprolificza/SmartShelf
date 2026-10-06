-- UniLibrary fine system
-- Run this once against the library_system PostgreSQL database.

BEGIN;

ALTER TABLE book
    ADD COLUMN IF NOT EXISTS market_value NUMERIC(10,2);

ALTER TABLE loan
    ADD COLUMN IF NOT EXISTS loan_status VARCHAR(20) NOT NULL DEFAULT 'BORROWED';

ALTER TABLE fine
    ADD COLUMN IF NOT EXISTS fine_type VARCHAR(30) NOT NULL DEFAULT 'OVERDUE';

ALTER TABLE fine
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'OUTSTANDING';

ALTER TABLE fine
    ADD COLUMN IF NOT EXISTS notes TEXT;

ALTER TABLE fine
    ADD COLUMN IF NOT EXISTS finalized_at TIMESTAMP;

-- Normalize existing active loans before the application starts using the new status.
UPDATE loan
SET loan_status = CASE
    WHEN returned_date IS NOT NULL THEN 'RETURNED'
    WHEN due_date < CURRENT_DATE THEN 'OVERDUE'
    ELSE 'BORROWED'
END
WHERE loan_status IS NULL
   OR loan_status NOT IN ('BORROWED', 'OVERDUE', 'RETURNED', 'LOST', 'DAMAGED');

-- Helpful indexes for fine/overdue lookups.
CREATE INDEX IF NOT EXISTS idx_loan_member_active
    ON loan(member_id, returned_date, due_date);

CREATE INDEX IF NOT EXISTS idx_fine_member_status
    ON fine(member_id, status);

COMMIT;

-- Policy used by the application:
--   Overdue: R25.00 per day after the due date.
--   Lost: book.market_value.
--   Significantly damaged: book.market_value.
--
-- The application calculates active overdue fines from CURRENT_DATE instead of
-- inserting a new fine row every day. A fine is finalized when the book is
-- returned, lost, or significantly damaged.


-- Optional database helper for live overdue calculations.
CREATE OR REPLACE FUNCTION calculate_overdue_fine(p_loan_id INTEGER)
RETURNS NUMERIC(10,2)
LANGUAGE plpgsql
AS $$
DECLARE
    v_due_date DATE;
    v_returned_date DATE;
    v_status VARCHAR(20);
    v_overdue_days INTEGER;
BEGIN
    SELECT due_date, returned_date, loan_status
    INTO v_due_date, v_returned_date, v_status
    FROM loan
    WHERE id = p_loan_id;

    IF v_due_date IS NULL OR v_status IN ('LOST', 'DAMAGED') THEN
        RETURN 0;
    END IF;

    IF v_returned_date IS NOT NULL THEN
        v_overdue_days := GREATEST(v_returned_date - v_due_date, 0);
    ELSE
        v_overdue_days := GREATEST(CURRENT_DATE - v_due_date, 0);
    END IF;

    RETURN v_overdue_days * 25.00;
END;
$$;
