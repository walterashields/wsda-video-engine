-- =============================================================
-- Lesson: The GROUP BY lie your database tells you every day
-- =============================================================
-- SQLite silently picks an ARBITRARY value for non-aggregated
-- columns not in GROUP BY. This query exposes that lie by
-- comparing what GROUP BY "chose" against every actual row.
-- =============================================================

-- Orders table: each row is one line-item purchase
CREATE TABLE orders (
    order_id    INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    product     TEXT    NOT NULL,
    amount      REAL    NOT NULL
);

INSERT INTO orders (order_id, customer_id, product, amount) VALUES
(1,  101, 'Wireless Mouse',      29.99),
(2,  101, 'USB-C Hub',           54.50),
(3,  101, 'Laptop Stand',        89.95),
(4,  102, 'Mechanical Keyboard', 134.99),
(5,  102, 'Desk Pad',            24.95),
(6,  103, 'Webcam HD',           74.50),
(7,  103, 'Ring Light',          39.99),
(8,  103, 'USB Microphone',      119.00),
(9,  103, 'Pop Filter',          12.49),
(10, 104, 'Monitor 27"',         349.99),
(11, 104, 'HDMI Cable',          11.99),
(12, 105, 'Noise-Cancel Headphones', 249.95);

-- [group_by_lie_exposed]
-- For each actual order row, we show which single product the
-- GROUP BY silently "chose" for that customer. Rows marked
-- HIDDEN were real purchases that the lying query threw away.
SELECT o.customer_id,
       o.product                     AS actual_product,
       o.amount                      AS line_amount,
       g.picked_product              AS group_by_showed,
       CASE WHEN o.product = g.picked_product
            THEN 'shown' ELSE 'HIDDEN' END AS status
FROM   orders o
JOIN   (SELECT customer_id,
               product AS picked_product
        FROM   orders
        GROUP BY customer_id) g
  ON   o.customer_id = g.customer_id
ORDER BY o.customer_id, o.order_id;