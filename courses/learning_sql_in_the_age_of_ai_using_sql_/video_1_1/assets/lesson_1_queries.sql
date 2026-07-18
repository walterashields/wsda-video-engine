-- Sales transactions table for a company's quarterly revenue analysis
CREATE TABLE sales (
    sale_id INTEGER PRIMARY KEY,
    rep_name TEXT NOT NULL,
    client TEXT NOT NULL,
    quarter TEXT NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    sale_date DATE NOT NULL
);

-- Seed realistic sales data across Q1-Q4
INSERT INTO sales (sale_id, rep_name, client, quarter, amount, sale_date) VALUES
(1,  'Dana Reeves',   'Meridian Corp',      'Q1', 8750.00,  '2024-02-14'),
(2,  'Marcus Chen',   'Blueshift Labs',     'Q1', 12300.00, '2024-03-02'),
(3,  'Dana Reeves',   'Northvale Inc',      'Q2', 9425.00,  '2024-04-18'),
(4,  'Sofia Patel',   'Crestline Media',    'Q2', 14200.00, '2024-05-09'),
(5,  'Marcus Chen',   'Blueshift Labs',     'Q2', 6800.00,  '2024-06-21'),
(6,  'Sofia Patel',   'Tidalwave Partners', 'Q3', 11350.00, '2024-07-30'),
(7,  'Dana Reeves',   'Meridian Corp',      'Q3', 7625.00,  '2024-08-15'),
(8,  'Marcus Chen',   'Apex Dynamics',      'Q3', 9100.00,  '2024-09-03'),
(9,  'Sofia Patel',   'Crestline Media',    'Q4', 18900.00, '2024-10-11'),
(10, 'Dana Reeves',   'Northvale Inc',      'Q4', 22475.00, '2024-11-05'),
(11, 'Marcus Chen',   'Blueshift Labs',     'Q4', 15750.00, '2024-11-22'),
(12, 'Sofia Patel',   'Tidalwave Partners', 'Q4', 23680.00, '2024-12-09');

-- [where_clause_impact]
-- Shows each quarter's contribution so you can see exactly what a WHERE filter keeps vs. excludes
SELECT
    quarter,
    COUNT(*)       AS deals,
    SUM(amount)    AS quarter_revenue
FROM sales
GROUP BY quarter
ORDER BY quarter;