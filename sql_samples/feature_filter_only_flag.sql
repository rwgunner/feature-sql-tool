WITH payment_base AS (
    SELECT
        p.client_id,
        p.amount,
        p.payment_id,
        CASE
            WHEN p.payment_status = 'PAID'
             AND p.payment_dt >= DATE '2026-03-01'
             AND p.payment_dt < DATE '2026-04-01'
            THEN 1 ELSE 0
        END AS is_paid_recent_flag
    FROM dm_payments p
),
filtered_payments AS (
    SELECT client_id, amount, payment_id, is_paid_recent_flag
    FROM payment_base
    WHERE is_paid_recent_flag = 1
)
SELECT
    fp.client_id,
    SUM(fp.amount) / COUNT(DISTINCT fp.payment_id) AS avg_payment_30d
FROM filtered_payments fp
GROUP BY fp.client_id
