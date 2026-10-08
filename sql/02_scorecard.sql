-- Weighted supplier scorecard, ranked and assigned a tier.
-- Each KPI is converted to a 0-100 score against a target, then weighted:
--   on-time delivery 40%, quality 30%, fill rate 20%, price 10%.
WITH kpis AS (
    SELECT
        s.supplier_id,
        s.supplier_name,
        SUM(po.qty_ordered * po.unit_price)                        AS total_spend,
        100.0 * AVG(r.received_date <= po.promised_date)           AS on_time_pct,
        1000000.0 * SUM(r.qty_rejected) / SUM(r.qty_received)      AS defect_ppm,
        100.0 * SUM(r.qty_received) / SUM(po.qty_ordered)          AS fill_rate_pct,
        100.0 * (SUM(po.qty_ordered * po.unit_price)
               - SUM(po.qty_ordered * po.contract_price))
               / SUM(po.qty_ordered * po.contract_price)           AS price_variance_pct
    FROM purchase_orders po
    JOIN suppliers s ON s.supplier_id = po.supplier_id
    JOIN receipts  r ON r.po_id = po.po_id
    GROUP BY s.supplier_id, s.supplier_name
),
scores AS (
    SELECT
        *,
        -- 100 at 95%+ on time, falling to 0 at 65%
        MIN(100, MAX(0, (on_time_pct - 65) / 30.0 * 100))               AS delivery_score,
        -- 100 at 0 PPM, falling to 0 at 30,000 PPM (3% rejected)
        MIN(100, MAX(0, 100 - defect_ppm / 300.0))                      AS quality_score,
        -- 100 at 100% fill, falling to 0 at 95%
        MIN(100, MAX(0, (fill_rate_pct - 95) / 5.0 * 100))              AS fill_score,
        -- 100 at or below contract price, falling to 0 at 5% over
        MIN(100, MAX(0, 100 - MAX(price_variance_pct, 0) / 5.0 * 100))  AS price_score
    FROM kpis
),
weighted AS (
    SELECT
        *,
        0.40 * delivery_score + 0.30 * quality_score
      + 0.20 * fill_score     + 0.10 * price_score AS total_score
    FROM scores
)
SELECT
    RANK() OVER (ORDER BY total_score DESC)                       AS rank,
    supplier_name,
    ROUND(total_score, 1)                                         AS total_score,
    CASE
        WHEN total_score >= 85 THEN 'Preferred'
        WHEN total_score >= 70 THEN 'Approved'
        WHEN total_score >= 55 THEN 'Watchlist'
        ELSE 'At risk'
    END                                                           AS tier,
    ROUND(delivery_score, 0)                                      AS delivery_score,
    ROUND(quality_score, 0)                                       AS quality_score,
    ROUND(fill_score, 0)                                          AS fill_score,
    ROUND(price_score, 0)                                         AS price_score,
    ROUND(on_time_pct, 1)                                         AS on_time_pct,
    ROUND(defect_ppm, 0)                                          AS defect_ppm,
    ROUND(fill_rate_pct, 1)                                       AS fill_rate_pct,
    ROUND(price_variance_pct, 2)                                  AS price_variance_pct,
    ROUND(100.0 * total_spend / SUM(total_spend) OVER (), 1)      AS spend_share_pct
FROM weighted
ORDER BY total_score DESC;
