-- SQL file template for WSDA Video Engine
-- Section names must match query_ref values in production_card.yml
-- Format: -- [section_name] with no spaces

-- [query_1]
SELECT *
FROM your_table
WHERE your_condition
LIMIT 10;

-- [query_2]
SELECT column_a, column_b
FROM your_other_table
ORDER BY column_a DESC;
