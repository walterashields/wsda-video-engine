#!/usr/bin/env python3
"""
WSDA DB Builder — Creates SQLite databases from AI-generated schemas.
"""

import sqlite3
import json
from pathlib import Path


class DBBuilder:
    """Builds a SQLite database from schema + data definitions."""

    def __init__(self, output_path: Path):
        self.output_path = output_path
        self.conn = None

    def build(self, create_statements: list, insert_statements: list) -> Path:
        """Create database, run DDL, insert data."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        if self.output_path.exists():
            self.output_path.unlink()

        self.conn = sqlite3.connect(str(self.output_path))
        cur = self.conn.cursor()

        # Run CREATE statements
        for stmt in create_statements:
            cur.execute(stmt)

        # Run INSERT statements
        for stmt in insert_statements:
            try:
                cur.execute(stmt)
            except sqlite3.Error as e:
                print(f"[db] INSERT error: {e}")
                print(f"[db] Statement: {stmt[:100]}...")

        self.conn.commit()
        self.conn.close()
        print(f"[db] Created: {self.output_path}")
        return self.output_path

    def verify_queries(self, queries: list) -> list:
        """Run each query and return results. Returns list of {ref, columns, rows}."""
        self.conn = sqlite3.connect(str(self.output_path))
        self.conn.row_factory = sqlite3.Row
        cur = self.conn.cursor()
        verified = []

        for q in queries:
            ref = q.get("ref", "unknown")
            sql = q.get("sql", "")
            try:
                cur.execute(sql)
                rows = cur.fetchall()
                columns = [d[0] for d in cur.description] if cur.description else []
                data = [[row[c] for c in columns] for row in rows]
                verified.append({
                    "ref": ref,
                    "sql": sql,
                    "columns": columns,
                    "rows": data
                })
                print(f"[db] {ref}: {len(data)} rows, {len(columns)} cols")
            except Exception as e:
                print(f"[db] {ref} FAILED: {e}")
                print(f"[db] SQL: {sql[:200]}")
                verified.append({"ref": ref, "sql": sql, "columns": [], "rows": []})

        self.conn.close()
        return verified
