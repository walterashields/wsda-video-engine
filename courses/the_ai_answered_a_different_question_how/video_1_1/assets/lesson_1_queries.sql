-- Customers table
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    customer_name TEXT NOT NULL
);

-- Orders table: each row is one order placed by a customer
CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    order_total REAL NOT NULL,
    order_date TEXT NOT NULL
);

-- Order items table: line items within each order (multiple per order)
CREATE TABLE order_items (
    item_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(order_id),
    product_name TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL
);

-- Seed 10 customers
INSERT INTO customers (customer_id, customer_name) VALUES
(1, 'Alvarez Construction'),
(2, 'Beacon Health'),
(3, 'CityWide Logistics'),
(4, 'DataBridge Corp'),
(5, 'Evergreen Supplies'),
(6, 'FreshCart Inc'),
(7, 'Granite Systems'),
(8, 'Hillside Dental'),
(9, 'InnoTech Labs'),
(10, 'JetStream Media');

-- Seed 12 orders across these customers (some customers have multiple orders)
INSERT INTO orders (order_id, customer_id, order_total, order_date) VALUES
(101, 1, 4250.00, '2024-01-15'),
(102, 1, 3175.00, '2024-02-08'),
(103, 2, 8900.00, '2024-01-22'),
(104, 3, 1450.00, '2024-03-01'),
(105, 4, 6720.00, '2024-01-30'),
(106, 4, 2380.00, '2024-02-14'),
(107, 5, 5100.00, '2024-03-10'),
(108, 6, 3890.00, '2024-02-20'),
(109, 7, 7250.00, '2024-01-18'),
(110, 8, 2960.00, '2024-03-05'),
(111, 9, 4415.00, '2024-02-28'),
(112, 10, 1890.00, '2024-03-12');

-- Seed order_items: 3 line items per order (this causes fan-out)
INSERT INTO order_items (item_id, order_id, product_name, quantity, unit_price) VALUES
(1,  101, 'Steel Beams',       10, 250.00),
(2,  101, 'Concrete Mix',      25,  45.00),
(3,  101, 'Safety Helmets',    50,  23.00),
(4,  102, 'Lumber Planks',     40,  55.00),
(5,  102, 'Nails 5lb Box',     15,  18.50),
(6,  102, 'Paint Gallons',     12,  42.00),
(7,  103, 'MRI Filters',        5, 980.00),
(8,  103, 'Surgical Gloves',  200,   8.50),
(9,  103, 'Disinfectant',      60,  35.00),
(10, 104, 'Packing Tape',     100,   4.50),
(11, 104, 'Shipping Labels',  500,   0.90),
(12, 104, 'Bubble Wrap Rolls',  8,  62.50),
(13, 105, 'Server Rack',        2, 1850.00),
(14, 105, 'Ethernet Cables',  100,   12.20),
(15, 105, 'UPS Battery',        4,  380.00),
(16, 106, 'USB-C Hubs',        20,  65.00),
(17, 106, 'Monitor Stands',    10,  88.00),
(18, 106, 'Cable Organizers',  30,  15.00),
(19, 107, 'Organic Fertilizer', 80,  28.75),
(20, 107, 'Garden Hose 50ft',  15,  34.00),
(21, 107, 'Pruning Shears',    40,  22.50),
(22, 108, 'Produce Crates',    60,  18.50),
(23, 108, 'Cooler Packs',      40,  32.00),
(24, 108, 'Barcode Scanner',    3, 245.00),
(25, 109, 'Granite Slabs',      8, 620.00),
(26, 109, 'Epoxy Resin',       20,  75.50),
(27, 109, 'Diamond Blades',     5, 198.00),
(28, 110, 'Dental Chairs',      1, 1850.00),
(29, 110, 'X-Ray Film',        50,  12.20),
(30, 110, 'Sterilizer Fluid',  25,  18.00),
(31, 111, 'Oscilloscope',       2, 1240.00),
(32, 111, 'Soldering Kit',     10,  89.50),
(33, 111, 'Resistor Pack',    100,   4.50),
(34, 112, 'Camera Lens',        2, 475.00),
(35, 112, 'Tripod',             3, 130.00),
(36, 112, 'Memory Card 128GB',  8,  42.50);


-- [fan_out_comparison]
-- Shows the WRONG inflated total (from joining to order_items, which triples
-- each order_total) side-by-side with the CORRECT total (aggregated without
-- the item join). The "inflation_factor" column reveals the 3x fan-out.
SELECT
    correct.customer_name,
    correct.correct_revenue,
    buggy.inflated_revenue,
    ROUND(buggy.inflated_revenue / correct.correct_revenue, 1) AS inflation_factor
FROM (
    SELECT c.customer_id, c.customer_name,
           SUM(o.order_total) AS correct_revenue
    FROM customers c
    JOIN orders o ON o.customer_id = c.customer_id
    GROUP BY c.customer_id, c.customer_name
) correct
JOIN (
    SELECT c.customer_id,
           SUM(o.order_total) AS inflated_revenue
    FROM customers c
    JOIN orders o ON o.customer_id = c.customer_id
    JOIN order_items oi ON oi.order_id = o.order_id
    GROUP BY c.customer_id
) buggy ON buggy.customer_id = correct.customer_id
ORDER BY correct.correct_revenue DESC;