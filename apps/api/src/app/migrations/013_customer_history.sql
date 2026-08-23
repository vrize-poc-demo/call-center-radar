ALTER TABLE calls ADD COLUMN customer_match_key TEXT;

UPDATE calls
SET customer_match_key = lower(trim(customer_name))
WHERE customer_name IS NOT NULL AND trim(customer_name) <> '';

CREATE INDEX IF NOT EXISTS idx_calls_customer_match_key_created
    ON calls(customer_match_key, created_at, id);
