SELECT
    p.client_id,
    SUM(p.amount) AS total_paid_amount_active_30d
FROM dm_payments p
JOIN dm_clients c
    ON p.client_id = c.client_id
WHERE p.payment_status = 'PAID'
  AND p.payment_dt >= DATE '2026-03-01'
  AND p.payment_dt < DATE '2026-04-01'
  AND c.is_active = 1
GROUP BY p.client_id
