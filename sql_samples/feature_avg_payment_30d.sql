SELECT
    p.client_id,
    SUM(p.amount) / COUNT(DISTINCT p.payment_id) AS avg_payment_30d
FROM dm_payments p
WHERE p.payment_status = 'PAID'
  AND p.payment_dt >= DATE '2026-03-01'
  AND p.payment_dt < DATE '2026-04-01'
GROUP BY p.client_id
