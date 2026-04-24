WITH payment_base AS (
    SELECT
        p.client_id,
        p.payment_id,
        p.payment_dt,
        p.amount,
        p.payment_status,
        p.channel,
        CASE
            WHEN p.payment_status = 'PAID' THEN p.amount
            ELSE 0
        END AS paid_amount,
        CASE
            WHEN p.payment_dt >= DATE '2026-03-01'
             AND p.payment_dt < DATE '2026-04-01'
            THEN 1
            ELSE 0
        END AS is_march_flag
    FROM dm_payments p
    WHERE p.payment_dt >= DATE '2026-01-01'
      AND p.payment_dt < DATE '2026-04-01'
),

client_profile AS (
    SELECT
        c.client_id,
        CASE
            WHEN c.segment IN ('VIP', 'PREMIUM') THEN 1
            ELSE 0
        END AS premium_client_flag,
        CASE
            WHEN c.registration_dt <= DATE '2025-12-31' THEN 1
            ELSE 0
        END AS mature_client_flag
    FROM dm_clients c
    WHERE c.is_active = 1
),

risky_events_union AS (
    SELECT
        pb.client_id,
        pb.payment_id,
        pb.payment_dt AS event_dt,
        pb.amount AS event_amount,
        'FAILED_PAYMENT' AS event_type,
        CASE
            WHEN pb.channel = 'CASH' THEN 2
            ELSE 1
        END AS event_weight
    FROM payment_base pb
    WHERE pb.is_march_flag = 1
      AND pb.payment_status = 'FAILED'

    UNION ALL

    SELECT
        ch.client_id,
        ch.payment_id,
        ch.chargeback_dt AS event_dt,
        ch.chargeback_amount AS event_amount,
        'CHARGEBACK' AS event_type,
        3 AS event_weight
    FROM dm_chargebacks ch
    WHERE ch.chargeback_dt >= DATE '2026-03-01'
      AND ch.chargeback_dt < DATE '2026-04-01'
),

risky_events_agg AS (
    SELECT
        re.client_id,
        COUNT(DISTINCT re.payment_id) AS risky_payment_cnt_30d,
        SUM(re.event_weight) AS risky_event_weight_30d,
        MAX(
            CASE
                WHEN re.event_type = 'CHARGEBACK' THEN 1
                ELSE 0
            END
        ) AS has_chargeback_flag
    FROM risky_events_union re
    GROUP BY re.client_id
),

payment_client_enriched AS (
    SELECT
        pb.client_id,
        pb.payment_id,
        pb.paid_amount,
        pb.channel,
        pb.payment_status,
        pb.is_march_flag,
        cp.premium_client_flag,
        cp.mature_client_flag,
        COALESCE(rea.risky_payment_cnt_30d, 0) AS risky_payment_cnt_30d,
        COALESCE(rea.risky_event_weight_30d, 0) AS risky_event_weight_30d,
        COALESCE(rea.has_chargeback_flag, 0) AS has_chargeback_flag,
        CASE
            WHEN pb.channel = 'ONLINE' AND pb.paid_amount >= 5000 THEN 2
            WHEN pb.channel = 'CASH' AND pb.paid_amount >= 1000 THEN 1
            ELSE 0
        END AS large_payment_risk_points
    FROM payment_base pb
    JOIN client_profile cp
        ON pb.client_id = cp.client_id
    LEFT JOIN risky_events_agg rea
        ON pb.client_id = rea.client_id
    WHERE pb.is_march_flag = 1
),

client_feature_components AS (
    SELECT
        pce.client_id,
        SUM(pce.paid_amount) AS paid_amount_30d,
        COUNT(DISTINCT CASE WHEN pce.payment_status = 'PAID' THEN pce.payment_id END) AS paid_payment_cnt_30d,
        MAX(pce.large_payment_risk_points) AS max_large_payment_risk_points,
        MAX(pce.premium_client_flag) AS premium_client_flag,
        MAX(pce.mature_client_flag) AS mature_client_flag,
        MAX(pce.risky_payment_cnt_30d) AS risky_payment_cnt_30d,
        MAX(pce.risky_event_weight_30d) AS risky_event_weight_30d,
        MAX(pce.has_chargeback_flag) AS has_chargeback_flag
    FROM payment_client_enriched pce
    GROUP BY pce.client_id
),

scored_clients AS (
    SELECT
        cfc.client_id,
        CASE
            WHEN cfc.paid_payment_cnt_30d = 0 THEN 0
            ELSE cfc.paid_amount_30d / cfc.paid_payment_cnt_30d
        END AS avg_paid_amount_30d,
        cfc.risky_payment_cnt_30d,
        cfc.risky_event_weight_30d,
        cfc.has_chargeback_flag,
        cfc.max_large_payment_risk_points,
        cfc.premium_client_flag,
        cfc.mature_client_flag,
        CASE
            WHEN cfc.has_chargeback_flag = 1 THEN 5
            ELSE 0
        END
        + CASE
            WHEN cfc.risky_event_weight_30d >= 5 THEN 3
            WHEN cfc.risky_event_weight_30d >= 2 THEN 1
            ELSE 0
          END
        + cfc.max_large_payment_risk_points
        + CASE
            WHEN cfc.premium_client_flag = 1 THEN -1
            ELSE 0
          END
        + CASE
            WHEN cfc.mature_client_flag = 1 THEN -1
            ELSE 0
          END AS client_payment_risk_score_30d
    FROM client_feature_components cfc
)

SELECT
    sc.client_id,
    CASE
        WHEN sc.client_payment_risk_score_30d < 0 THEN 0
        ELSE sc.client_payment_risk_score_30d
    END AS client_payment_risk_score_30d
FROM scored_clients sc
