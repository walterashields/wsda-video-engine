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
-- Your turn: write the query for 'group_by_lie_exposed' here
