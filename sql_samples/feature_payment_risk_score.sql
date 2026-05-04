WITH payment_union AS (
    SELECT
        p.client_id,
        p.payment_id,
        p.payment_dt,
        p.amount,
        p.payment_status,
        p.channel
    FROM dm_payments_current p
    WHERE p.payment_dt >= DATE '2026-03-01'
      AND p.payment_dt < DATE '2026-04-01'

    UNION

    SELECT
        a.client_id,
        a.payment_id,
        a.payment_dt,
        a.amount,
        a.payment_status,
        a.channel
    FROM dm_payments_archive a
    WHERE a.payment_dt >= DATE '2026-03-01'
      AND a.payment_dt < DATE '2026-04-01'
),

payment_agg AS (
    SELECT
        pu.client_id,
        pu.payment_id,
        SUM(pu.amount) AS total_amount_30d,
        COUNT(*) AS payment_event_cnt_30d,
        MAX(pu.payment_dt) AS last_payment_dt,
        CASE
            WHEN MAX(CASE WHEN pu.payment_status = 'FAILED' THEN 1 ELSE 0 END) = 1 THEN 1
            ELSE 0
        END AS has_failed_status_flag,
        CASE
            WHEN MAX(CASE WHEN pu.channel = 'CASH' THEN 1 ELSE 0 END) = 1 THEN 1
            ELSE 0
        END AS has_cash_channel_flag
    FROM payment_union pu
    GROUP BY
        pu.client_id,
        pu.payment_id
),

payment_filtered AS (
    SELECT
        pa.client_id,
        pa.payment_id,
        pa.total_amount_30d,
        pa.payment_event_cnt_30d,
        pa.last_payment_dt,
        pa.has_failed_status_flag,
        pa.has_cash_channel_flag,
        CASE
            WHEN pa.total_amount_30d >= 10000 THEN 3
            WHEN pa.total_amount_30d >= 3000 THEN 2
            ELSE 1
        END AS amount_bucket,
        CASE
            WHEN pa.has_failed_status_flag = 1 OR pa.has_cash_channel_flag = 1 THEN 1
            ELSE 0
        END AS risky_payment_flag
    FROM payment_agg pa
    WHERE pa.payment_event_cnt_30d > 0
)

SELECT
    pf.client_id,
    pf.payment_id,
    pf.amount_bucket
    + pf.risky_payment_flag
    + CASE
        WHEN pf.payment_event_cnt_30d >= 3 THEN 2
        ELSE 0
      END AS payment_risk_score
FROM payment_filtered pf
