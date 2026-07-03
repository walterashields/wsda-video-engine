"""
WSDA SQL Viewer — Flask App v3

New in v3:
  GET  /audio/narration          serve narration WAV for in-browser playback
  GET  /api/audio-time           return current audio playback position (ms)
  POST /api/audio-load           tell viewer which audio file to load
  POST /api/audio-play           start playback
  POST /api/audio-seek           seek to position
"""

import sqlite3
import json
import re
import os
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, Response

app = Flask(__name__)

state = {
    "db_path":          None,
    "schema":           {},
    "last_result":      None,
    "result_history":   {},
    "sql_content":      None,
    "sql_sections":     {},
    "audio_path":       None,
}


def get_schema(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # Tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    schema = {}
    for t in tables:
        cur.execute(f"PRAGMA table_info({t})")
        cols = [{"name": r[1], "type": r[2]} for r in cur.fetchall()]
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        schema[t] = {"columns": cols, "row_count": cur.fetchone()[0], "is_view": False}
    # Views — shown separately with definition
    cur.execute("SELECT name, sql FROM sqlite_master WHERE type='view' ORDER BY name")
    for name, sql in cur.fetchall():
        schema[name] = {
            "columns": [],
            "row_count": None,
            "is_view": True,
            "definition": sql or ""
        }
    conn.close()
    return schema


def run_sql(db_path, sql):
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        conn.close()
        return {"success": True, "columns": cols,
                "rows": [list(r) for r in rows], "row_count": len(rows)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def parse_sections(content):
    sections, cur, lines = {}, None, []
    for line in content.splitlines():
        m = re.match(r"--\s*\[(\w+)\]", line)
        if m:
            if cur and lines:
                sections[cur] = "\n".join(lines).strip()
            cur, lines = m.group(1), []
        elif cur is not None:
            lines.append(line)
    if cur and lines:
        sections[cur] = "\n".join(lines).strip()
    return sections


# ── Standard API ───────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("viewer.html")

@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/api/load-db", methods=["POST"])
def load_db():
    path = request.json.get("path")
    if not path or not Path(path).exists():
        return jsonify({"success": False, "error": f"Not found: {path}"}), 400
    state["db_path"] = path
    state["schema"] = get_schema(path)
    state["result_history"] = {}
    return jsonify({"success": True, "schema": state["schema"]})

@app.route("/api/load-sql", methods=["POST"])
def load_sql():
    path = request.json.get("path")
    if not path or not Path(path).exists():
        return jsonify({"success": False, "error": f"Not found: {path}"}), 400
    content = Path(path).read_text()
    state["sql_content"] = content
    state["sql_sections"] = parse_sections(content)
    return jsonify({"success": True, "content": content,
                    "sections": list(state["sql_sections"].keys())})

@app.route("/api/run-query", methods=["POST"])
def run_query():
    if not state["db_path"]:
        return jsonify({"success": False, "error": "No database loaded"}), 400
    data = request.json
    sql = data.get("sql", "").strip()
    ref = data.get("query_ref", "")
    if not sql and ref:
        sql = state["sql_sections"].get(ref, "")
    if not sql:
        return jsonify({"success": False, "error": "No SQL"}), 400
    result = run_sql(state["db_path"], sql)
    if result["success"]:
        state["result_history"][ref] = result
        state["last_result"] = result
    return jsonify(result)

@app.route("/api/highlight-section", methods=["POST"])
def highlight_section():
    section = request.json.get("section", "")
    return jsonify({"success": True, "section": section})

@app.route("/api/get-view-sql", methods=["POST"])
def get_view_sql():
    """Return the CREATE VIEW SQL for a named view."""
    view_name = request.json.get("view", "")
    db_path = state.get("db_path")
    if not db_path or not view_name:
        return jsonify({"sql": ""})
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='view' AND name=?",
        (view_name,)
    ).fetchone()
    conn.close()
    return jsonify({"sql": row[0] if row else ""})

@app.route("/api/show-schema", methods=["POST"])
def show_schema():
    return jsonify({"success": True, "schema": state["schema"]})

@app.route("/api/attention", methods=["POST"])
def attention():
    return jsonify({"success": True, "applied": request.json})

@app.route("/api/state")
def get_state():
    return jsonify({
        "db_path":    state["db_path"],
        "schema":     state["schema"],
        "result_count": len(state["result_history"]),
        "audio_path": state["audio_path"],
    })

# ── Audio endpoints ────────────────────────────────────────────

@app.route("/api/audio-load", methods=["POST"])
def audio_load():
    path = request.json.get("path")
    if not path or not Path(path).exists():
        return jsonify({"success": False, "error": f"Audio not found: {path}"}), 400
    state["audio_path"] = path
    return jsonify({"success": True, "path": path})

@app.route("/audio/narration")
def serve_audio():
    """Serve the narration WAV file for in-browser playback."""
    if not state["audio_path"] or not Path(state["audio_path"]).exists():
        return Response("No audio loaded", status=404)
    return send_file(
        state["audio_path"],
        mimetype="audio/wav",
        conditional=True,   # supports range requests for seeking
    )

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=False)
