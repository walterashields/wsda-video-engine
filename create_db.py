#!/usr/bin/env python3
"""
Create the NovaBridge Analytics demo database.
Run once: python create_db.py
"""

import sqlite3
import random
from pathlib import Path

DB_PATH = Path(__file__).parent / "courses/novabridge/video_1_1/assets/novabridge.db"

REGIONS = ["Northeast", "Southeast", "Midwest", "West", "Southwest"]

def create_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    if DB_PATH.exists():
        DB_PATH.unlink()
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # ── orders ──────────────────────────────────────────────────
    # This is the raw transaction table. order_total includes tax.
    cur.execute("""
        CREATE TABLE orders (
            order_id    INTEGER PRIMARY KEY,
            region      TEXT NOT NULL,
            order_date  TEXT NOT NULL,
            order_total REAL NOT NULL,    -- includes tax
            customer_id INTEGER NOT NULL
        )
    """)

    # ── order_details ────────────────────────────────────────────
    # Line items. unit_price * quantity = pre-tax line total.
    cur.execute("""
        CREATE TABLE order_details (
            detail_id  INTEGER PRIMARY KEY,
            order_id   INTEGER NOT NULL REFERENCES orders(order_id),
            product_id INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            quantity   INTEGER NOT NULL
        )
    """)

    # ── order_summary ────────────────────────────────────────────
    # Pre-aggregated monthly rollup. summary_total excludes returns.
    cur.execute("""
        CREATE TABLE order_summary (
            summary_id    INTEGER PRIMARY KEY,
            region        TEXT NOT NULL,
            month         TEXT NOT NULL,
            summary_total REAL NOT NULL,   -- excludes returns, pre-tax
            order_count   INTEGER NOT NULL
        )
    """)

    # ── seed orders ─────────────────────────────────────────────
    random.seed(42)
    orders = []
    for i in range(1, 201):
        region = random.choice(REGIONS)
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        subtotal = round(random.uniform(80, 2500), 2)
        tax = round(subtotal * 0.08, 2)
        order_total = round(subtotal + tax, 2)
        orders.append((
            i, region, f"2023-{month:02d}-{day:02d}",
            order_total, random.randint(1000, 1200)
        ))

    cur.executemany(
        "INSERT INTO orders VALUES (?,?,?,?,?)", orders
    )

    # ── seed order_details ───────────────────────────────────────
    detail_id = 1
    details = []
    for order_id, region, date, order_total, customer_id in orders:
        num_lines = random.randint(1, 4)
        for _ in range(num_lines):
            details.append((
                detail_id, order_id,
                random.randint(100, 150),
                round(random.uniform(10, 300), 2),
                random.randint(1, 5)
            ))
            detail_id += 1

    cur.executemany(
        "INSERT INTO order_details VALUES (?,?,?,?,?)", details
    )

    # ── seed order_summary ───────────────────────────────────────
    # Deliberately different from raw totals (excludes returns ~5%)
    region_month_totals = {}
    for _, region, date, order_total, _ in orders:
        month = date[:7]
        key = (region, month)
        region_month_totals[key] = region_month_totals.get(key, {"total": 0, "count": 0})
        region_month_totals[key]["total"] += order_total
        region_month_totals[key]["count"] += 1

    summaries = []
    for sid, ((region, month), data) in enumerate(region_month_totals.items(), 1):
        # Remove ~5% for returns — this is the intentional discrepancy
        adjusted = round(data["total"] * 0.95, 2)
        summaries.append((sid, region, month, adjusted, data["count"]))

    cur.executemany(
        "INSERT INTO order_summary VALUES (?,?,?,?,?)", summaries
    )

    conn.commit()
    conn.close()

    print(f"Created: {DB_PATH}")
    print(f"  orders:        {len(orders)} rows")
    print(f"  order_details: {len(details)} rows")
    print(f"  order_summary: {len(summaries)} rows")
    print()
    print("Intentional discrepancy seeded:")
    print("  orders.order_total     = subtotal + 8% tax")
    print("  order_details total    = unit_price * quantity (pre-tax)")
    print("  order_summary.total    = monthly rollup minus ~5% returns")
    print()
    print("All three tables answer 'revenue by region' differently.")
    print("That is the point of this lesson.")


if __name__ == "__main__":
    create_database()
