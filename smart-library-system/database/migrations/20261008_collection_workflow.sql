-- Add collection workflow fields and statuses to existing SmartShelf databases.
BEGIN;

ALTER TABLE loan
    ADD COLUMN IF NOT EXISTS collection_expires_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS collected_at TIMESTAMP;

ALTER TABLE loan DROP CONSTRAINT IF EXISTS loan_loan_status_check;
ALTER TABLE loan
    ADD CONSTRAINT loan_loan_status_check
    CHECK (loan_status IN (
        'BORROWED',
        'READY_FOR_COLLECTION',
        'OUT',
        'EXPIRED',
        'OVERDUE',
        'RETURNED',
        'LOST',
        'DAMAGED'
    ));

COMMIT;
