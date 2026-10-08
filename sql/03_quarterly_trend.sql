-- On-time delivery by supplier and quarter, with the change from the prior
-- quarter. Catches suppliers whose yearly average still looks fine but who
-- are getting worse.
WITH quarterly AS (
    SELECT
        s.supplier_name,
        STRFTIME('%Y', po.order_date) || '-Q'
            || ((CAST(STRFTIME('%m', po.order_date) AS INTEGER) + 2) / 3) AS quarter,
        COUNT(*)                                                          AS po_count,
        100.0 * AVG(r.received_date <= po.promised_date)                  AS on_time_pct
    FROM purchase_orders po
    JOIN suppliers s ON s.supplier_id = po.supplier_id
    JOIN receipts  r ON r.po_id = po.po_id
    GROUP BY s.supplier_name, quarter
)
SELECT
    supplier_name,
    quarter,
    po_count,
    ROUND(on_time_pct, 1) AS on_time_pct,
    ROUND(on_time_pct - LAG(on_time_pct) OVER (
        PARTITION BY supplier_name ORDER BY quarter), 1) AS change_vs_prior_qtr,
    ROUND(on_time_pct - FIRST_VALUE(on_time_pct) OVER (
        PARTITION BY supplier_name ORDER BY quarter), 1) AS change_vs_first_qtr
FROM quarterly
ORDER BY supplier_name, quarter;
