WITH payment_base AS (
    SELECT
        p.client_id,
        p.payment_id,
        p.amount,
        p.payment_dt,
        p.payment_status,
        CASE
            WHEN p.payment_status = 'PAID'
             AND p.payment_dt >= DATE '2026-03-01'
             AND p.payment_dt < DATE '2026-04-01'
            THEN 1
            ELSE 0
        END AS is_paid_recent_flag,
        CASE
            WHEN p.payment_status = 'PAID'
            THEN p.amount
            ELSE 0
        END AS paid_amount
    FROM dm_payments p
),
filtered_payments AS (
    SELECT
        client_id,
        payment_id,
        paid_amount,
        is_paid_recent_flag
    FROM payment_base
    WHERE is_paid_recent_flag = 1
)
SELECT
    fp.client_id,
    SUM(fp.paid_amount) / COUNT(DISTINCT fp.payment_id) AS avg_paid_amount_recent_30d
FROM filtered_payments fp
GROUP BY fp.client_id
