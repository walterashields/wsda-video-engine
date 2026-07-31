
"""
WSDA v3 -- Schema Fix (Zero Frontend Changes)
Reads the SQLite DB from disk and generates schema HTML for injection.
"""

import sqlite3
from pathlib import Path


def find_db_file(name="novabridge.db"):
    """Search common locations for the SQLite DB file."""
    search_paths = [
        Path(name),
        Path("assets") / name,
        Path("web") / "public" / name,
        Path("web") / name,
        Path("public") / name,
        Path("engine") / name,
        Path("recording") / name,
    ]
    for p in search_paths:
        if p.exists():
            return p.resolve()
    raise FileNotFoundError(
        f"Could not find {name}. Searched: {[str(p) for p in search_paths]}. "
        f"Place it in repo root, assets/, web/public/, or set db_asset_path in config.py"
    )


def get_schema_html(db_path=None):
    """Read SQLite DB and generate schema panel HTML."""
    if db_path is None:
        db_path = find_db_file()

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    cur.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)
    tables = [row[0] for row in cur.fetchall()]

    parts = []
    for table in tables:
        cur.execute(f'PRAGMA table_info("{table}")')
        cols = cur.fetchall()

        cols_html = ""
        for c in cols:
            pk_badge = '<span class="col-pk">PK</span>' if c[5] else ""
            cols_html += (
                f'<li class="schema-column">'
                f'<span class="col-name">{c[1]}</span>'
                f'<span class="col-type">{c[2]}</span>'
                f'{pk_badge}'
                f'</li>'
            )

        table_html = (
            f'<div class="schema-table" data-testid="schema-table">\n'
            f'  <div class="schema-table-header">\n'
            f'    <span class="schema-icon">#</span>\n'
            f'    <span class="schema-name">{table}</span>\n'
            f'  </div>\n'
            f'  <ul class="schema-columns">{cols_html}</ul>\n'
            f'</div>'
        )
        parts.append(table_html)

    conn.close()
    return "\n".join(parts)
