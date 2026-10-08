-- One row per supplier with the five KPIs used in the scorecard.
SELECT
    s.supplier_id,
    s.supplier_name,
    s.region,
    s.category,
    COUNT(*)                                                             AS po_count,
    ROUND(SUM(po.qty_ordered * po.unit_price), 0)                        AS total_spend,
    -- Delivery: share of orders received on or before the promised date
    ROUND(100.0 * AVG(r.received_date <= po.promised_date), 1)           AS on_time_pct,
    ROUND(AVG(JULIANDAY(r.received_date) - JULIANDAY(po.order_date)), 1) AS avg_lead_time_days,
    ROUND(AVG(MAX(JULIANDAY(r.received_date) - JULIANDAY(po.promised_date), 0)), 2)
                                                                         AS avg_days_late,
    -- Quality: rejected units per million received
    ROUND(1000000.0 * SUM(r.qty_rejected) / SUM(r.qty_received), 0)      AS defect_ppm,
    -- Quantity: units received as a share of units ordered
    ROUND(100.0 * SUM(r.qty_received) / SUM(po.qty_ordered), 1)          AS fill_rate_pct,
    -- Cost: spend above (+) or below (-) the contract price
    ROUND(100.0 * (SUM(po.qty_ordered * po.unit_price)
                 - SUM(po.qty_ordered * po.contract_price))
                 / SUM(po.qty_ordered * po.contract_price), 2)           AS price_variance_pct
FROM purchase_orders po
JOIN suppliers s ON s.supplier_id = po.supplier_id
JOIN receipts  r ON r.po_id = po.po_id
GROUP BY s.supplier_id, s.supplier_name, s.region, s.category;
