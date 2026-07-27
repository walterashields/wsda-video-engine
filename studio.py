#!/usr/bin/env python3
"""
WSDA Studio — web interface for content production

Run with: python3 studio.py
Opens at: http://localhost:7010

The user fills in a form. The system researches, drafts, and produces.
"""

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request

ROOT = Path(__file__).parent
app = Flask(__name__)

STUDIO_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WSDA Studio</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #0f1923;
    --surface: #1a2535;
    --border: #2a3a50;
    --text: #e8eef5;
    --text-dim: #6b8299;
    --green: #06c015;
    --blue: #4a9eff;
    --yellow: #ffd700;
    --red: #ff4a4a;
    --radius: 10px;
    --font: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }
  body { font-family: var(--font); background: var(--bg); color: var(--text);
         min-height: 100vh; padding: 40px 20px; }
  .container { max-width: 760px; margin: 0 auto; }

  .logo { display: flex; align-items: center; gap: 12px; margin-bottom: 32px; }
  .logo-mark { width: 36px; height: 36px; background: var(--green);
               border-radius: 8px; display: flex; align-items: center;
               justify-content: center; font-weight: 900; font-size: 18px; color: #000; }
  .logo-text { font-size: 20px; font-weight: 700; }
  .logo-sub { font-size: 12px; color: var(--text-dim); margin-top: 2px; }

  .card { background: var(--surface); border: 1px solid var(--border);
          border-radius: var(--radius); padding: 28px; margin-bottom: 20px; }
  .card-title { font-size: 13px; font-weight: 700; color: var(--text-dim);
                text-transform: uppercase; letter-spacing: .06em; margin-bottom: 20px; }

  .field { margin-bottom: 18px; }
  label { display: block; font-size: 13px; font-weight: 600; color: var(--text-dim);
          margin-bottom: 6px; }
  input[type=text], textarea, select {
    width: 100%; background: var(--bg); border: 1px solid var(--border);
    border-radius: 8px; padding: 10px 14px; color: var(--text);
    font-family: var(--font); font-size: 14px; outline: none;
    transition: border-color .15s;
  }
  input[type=text]:focus, textarea:focus, select:focus { border-color: var(--blue); }
  textarea { resize: vertical; min-height: 80px; }
  select option { background: var(--surface); }

  .row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .row-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }

  .chip-group { display: flex; flex-wrap: wrap; gap: 8px; }
  .chip { padding: 6px 14px; border-radius: 20px; border: 1px solid var(--border);
          font-size: 12px; cursor: pointer; transition: all .15s; user-select: none; }
  .chip:hover { border-color: var(--blue); }
  .chip.selected { background: var(--blue); border-color: var(--blue); color: #000;
                   font-weight: 700; }
  .chip.disabled { opacity: .35; cursor: not-allowed; }
  .chip.disabled:hover { border-color: var(--border); }

  .scout-card { border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px;
                margin-bottom: 8px; cursor: pointer; transition: all .15s; }
  .scout-card:hover { border-color: var(--blue); background: rgba(74,158,255,0.05); }
  .scout-card-selected { border-color: var(--green); background: rgba(6,192,21,0.08); }
  .scout-card-topic { font-weight: 700; font-size: 13px; margin-bottom: 4px; }
  .scout-card-rationale { font-size: 12px; color: var(--text-dim); margin-bottom: 6px; }
  .scout-card-sources { font-size: 10px; color: var(--text-dim); word-break: break-all; }
  .scout-card-sources a { color: var(--blue); text-decoration: none; }
  .scout-card-sources a:hover { text-decoration: underline; }

  .btn { display: inline-flex; align-items: center; gap: 8px; padding: 12px 24px;
         border-radius: 8px; font-size: 14px; font-weight: 700; cursor: pointer;
         border: none; transition: all .15s; }
  .btn-primary { background: var(--green); color: #000; width: 100%; justify-content: center; }
  .btn-primary:hover { background: #08d618; }
  .btn-primary:disabled { opacity: .4; cursor: not-allowed; }

  .progress { display: none; }
  .progress.visible { display: block; }
  .progress-bar-wrap { background: var(--bg); border-radius: 4px; height: 6px;
                       margin: 16px 0; overflow: hidden; }
  .progress-bar { height: 100%; background: var(--green); width: 0;
                  transition: width .4s ease; border-radius: 4px; }
  .progress-steps { display: flex; flex-direction: column; gap: 8px; }
  .step { display: flex; align-items: center; gap: 10px; font-size: 13px;
          color: var(--text-dim); }
  .step.active { color: var(--text); }
  .step.done { color: var(--green); }
  .step.error { color: var(--red); }
  .step-icon { width: 20px; height: 20px; border-radius: 50%; border: 2px solid var(--border);
               display: flex; align-items: center; justify-content: center;
               font-size: 10px; flex-shrink: 0; }
  .step.active .step-icon { border-color: var(--blue); background: rgba(74,158,255,.15); }
  .step.done .step-icon { border-color: var(--green); background: rgba(6,192,21,.15); }
  .step.error .step-icon { border-color: var(--red); }

  .log { background: var(--bg); border: 1px solid var(--border); border-radius: 8px;
         padding: 14px; font-family: monospace; font-size: 12px; color: var(--text-dim);
         max-height: 200px; overflow-y: auto; margin-top: 16px; display: none; }
  .log.visible { display: block; }
  .log-line { padding: 2px 0; line-height: 1.5; }
  .log-line.ok { color: var(--green); }
  .log-line.warn { color: var(--yellow); }
  .log-line.err { color: var(--red); }

  .result { display: none; }
  .result.visible { display: block; }
  .result-file { display: flex; align-items: center; justify-content: space-between;
                 padding: 12px 16px; background: var(--bg); border-radius: 8px;
                 border: 1px solid var(--border); margin-bottom: 8px; }
  .result-name { font-size: 13px; font-weight: 600; }
  .result-meta { font-size: 11px; color: var(--text-dim); margin-top: 2px; }
  .result-btn { padding: 6px 14px; border-radius: 6px; border: 1px solid var(--green);
                color: var(--green); background: transparent; font-size: 12px;
                font-weight: 700; cursor: pointer; transition: all .15s; }
  .result-btn:hover { background: var(--green); color: #000; }

  .hint { font-size: 11px; color: var(--text-dim); margin-top: 4px; }
  hr { border: none; border-top: 1px solid var(--border); margin: 4px 0 20px; }
</style>
</head>
<body>
<div class="container">

  <div class="logo">
    <div class="logo-mark">W</div>
    <div>
      <div class="logo-text">WSDA Studio</div>
      <div class="logo-sub">Content Production Engine</div>
    </div>
  </div>

  <!-- Input form -->
  <div class="card" id="form-card">
    <div class="card-title">What do you want to create?</div>

    <div class="field">
      <label>Not sure what to make? Pick a category and get web-grounded suggestions</label>
      <div class="chip-group" id="scout-category-chips">
        <div class="chip" data-val="sql-fundamentals">SQL fundamentals &amp; debugging</div>
        <div class="chip" data-val="sql-ai-hybrid">SQL + AI hybrid workflows</div>
        <div class="chip" data-val="data-quality">Data quality &amp; trust</div>
        <div class="chip" data-val="career-interview">Career &amp; interview prep</div>
      </div>
      <div style="margin-top:10px;">
        <button class="btn" id="scout-btn" type="button" style="font-size:12px;padding:8px 16px;">
          🔎 Suggest topics (live web search, sources cited)
        </button>
      </div>
      <div id="scout-status" style="display:none;margin-top:10px;font-size:12px;color:var(--text-dim);"></div>
      <div id="scout-results" style="display:none;margin-top:12px;"></div>
    </div>

    <div class="field">
      <label>Topic or title</label>
      <input type="text" id="topic" placeholder="e.g. SQL for data analysts, AI for beginners, Excel pivot tables" />
    </div>

    <div class="field">
      <label>Format</label>
      <div class="chip-group" id="format-chips">
        <div class="chip selected" data-val="course">Full course</div>
        <div class="chip" data-val="short-video">Short video</div>
        <div class="chip" data-val="tutorial">Tutorial</div>
        <div class="chip" data-val="lesson">Single lesson</div>
        <div class="chip" data-val="micro">Micro (1-3 min)</div>
      </div>
    </div>

    <div class="row">
      <div class="field">
        <label>Audience level</label>
        <select id="level">
          <option value="beginner">Beginner — no prior knowledge</option>
          <option value="intermediate">Intermediate — some experience</option>
          <option value="advanced">Advanced — professional use</option>
        </select>
      </div>
      <div class="field">
        <label>Lesson length</label>
        <select id="length">
          <option value="short">Short (3-5 min per lesson)</option>
          <option value="medium" selected>Medium (7-10 min per lesson)</option>
          <option value="long">Long (12-15 min per lesson)</option>
        </select>
      </div>
    </div>

    <div class="field">
      <label>Tools or software featured</label>
      <div class="chip-group" id="tools-chips">
        <div class="chip" data-val="chatgpt">ChatGPT</div>
        <div class="chip" data-val="sql">SQL / databases</div>
        <div class="chip disabled" data-val="excel" title="No Excel adapter yet — selecting this will not produce an accurate Excel demo">Excel (coming soon)</div>
        <div class="chip disabled" data-val="python" title="No Python adapter yet — selecting this will not produce an accurate Python demo">Python (coming soon)</div>
        <div class="chip disabled" data-val="powerbi" title="No Power BI adapter yet — selecting this will not produce an accurate Power BI demo">Power BI (coming soon)</div>
        <div class="chip" data-val="none">No specific tool</div>
      </div>
    </div>

    <div class="field">
      <label>Target audience <span style="color:var(--text-dim);font-weight:400">(optional — be specific)</span></label>
      <input type="text" id="audience" placeholder="e.g. marketing managers, HR professionals, small business owners" />
    </div>

    <div class="field">
      <label>Hands-on style</label>
      <div class="chip-group" id="handson-chips">
        <div class="chip" data-val="heavy">Heavy — exercises throughout</div>
        <div class="chip selected" data-val="moderate">Moderate — exercises at end</div>
        <div class="chip" data-val="light">Light — mostly watching</div>
      </div>
    </div>

    <div class="field">
      <label>Additional notes <span style="color:var(--text-dim);font-weight:400">(optional)</span></label>
      <textarea id="notes" placeholder="Any specific angle, story, or requirement for this content..."></textarea>
    </div>

    <button class="btn btn-primary" id="produce-btn" onclick="startProduction()">
      Produce Content
    </button>
  </div>

  <!-- Progress -->
  <div class="card progress" id="progress-card">
    <div class="card-title">Production in progress</div>
    <div class="progress-bar-wrap"><div class="progress-bar" id="progress-bar"></div></div>
    <div class="progress-steps" id="steps">
      <div class="step" id="step-research">
        <div class="step-icon">1</div>
        <span>Researching niche and structuring content</span>
      </div>
      <div class="step" id="step-draft">
        <div class="step-icon">2</div>
        <span>Drafting production cards</span>
      </div>
      <div class="step" id="step-record">
        <div class="step-icon">3</div>
        <span>Recording lesson videos</span>
      </div>
      <div class="step" id="step-narrate">
        <div class="step-icon">4</div>
        <span>Synthesizing narration</span>
      </div>
      <div class="step" id="step-qa">
        <div class="step-icon">5</div>
        <span>Quality check and trim</span>
      </div>
    </div>
    <div class="log" id="log"></div>
  </div>

  <!-- Results -->
  <div class="card result" id="result-card">
    <div class="card-title">Ready for Final Cut Pro</div>
    <div id="result-files"></div>
  </div>

</div>

<script>
// Chip toggle
document.querySelectorAll('.chip-group').forEach(group => {
  const multi = group.id === 'tools-chips' || group.id === 'handson-chips';
  group.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      if (chip.classList.contains('disabled')) return;
      if (!multi) {
        group.querySelectorAll('.chip').forEach(c => c.classList.remove('selected'));
        chip.classList.add('selected');
      } else {
        chip.classList.toggle('selected');
      }
      if (group.id === 'format-chips') updateLengthFieldState();
    });
  });
});

function updateLengthFieldState() {
  const fmt = getSelected('format-chips')[0] || 'course';
  const lengthEl = document.getElementById('length');
  const isMicro = fmt === 'micro';
  lengthEl.disabled = isMicro;
  lengthEl.parentElement.style.opacity = isMicro ? '.4' : '1';
  lengthEl.parentElement.title = isMicro
    ? "Micro format has its own fixed 1-3 minute length — this doesn't apply"
    : '';
}
updateLengthFieldState();

function getSelected(groupId) {
  return [...document.querySelectorAll(`#${groupId} .chip.selected`)]
    .map(c => c.dataset.val);
}

document.getElementById('scout-btn').addEventListener('click', async () => {
  const category = getSelected('scout-category-chips')[0];
  const statusEl = document.getElementById('scout-status');
  const resultsEl = document.getElementById('scout-results');

  if (!category) {
    statusEl.style.display = 'block';
    statusEl.textContent = 'Pick a category first.';
    resultsEl.style.display = 'none';
    return;
  }

  statusEl.style.display = 'block';
  statusEl.textContent = 'Searching the web for current demand signals — this can take up to a minute...';
  resultsEl.style.display = 'none';
  resultsEl.innerHTML = '';

  try {
    const res = await fetch('/api/scout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category }),
    });
    const data = await res.json();

    if (data.error) {
      statusEl.textContent = 'Error: ' + data.error;
      return;
    }

    const suggestions = data.suggestions || [];
    if (!suggestions.length) {
      statusEl.textContent = 'No new suggestions found — this category may already be well covered.';
      return;
    }

    statusEl.textContent = `${suggestions.length} suggestion(s) found. Click one to use it.`;
    resultsEl.style.display = 'block';
    resultsEl.innerHTML = suggestions.map(s => `
      <div class="scout-card" data-topic="${escapeHtml(s.topic)}">
        <div class="scout-card-topic">${escapeHtml(s.topic)}</div>
        <div class="scout-card-rationale">${escapeHtml(s.rationale || '')}</div>
        <div class="scout-card-sources">
          ${(s.sources || []).map(u => `<a href="${escapeHtml(u)}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${escapeHtml(u)}</a>`).join('<br>')}
        </div>
      </div>
    `).join('');

    resultsEl.querySelectorAll('.scout-card').forEach(card => {
      card.addEventListener('click', () => {
        document.getElementById('topic').value = card.dataset.topic;
        resultsEl.querySelectorAll('.scout-card').forEach(c => c.classList.remove('scout-card-selected'));
        card.classList.add('scout-card-selected');
      });
    });
  } catch (err) {
    statusEl.textContent = 'Error reaching the scout endpoint: ' + err.message;
  }
});

function escapeHtml(s) {
  const div = document.createElement('div');
  div.textContent = s || '';
  return div.innerHTML;
}

let pollInterval = null;
let jobId = null;

function log(msg, type='') {
  const el = document.getElementById('log');
  el.classList.add('visible');
  const line = document.createElement('div');
  line.className = 'log-line ' + type;
  line.textContent = msg;
  el.appendChild(line);
  el.scrollTop = el.scrollHeight;
}

function setStep(id, state) {
  const el = document.getElementById(id);
  el.classList.remove('active', 'done', 'error');
  el.classList.add(state);
  const icons = { active: '…', done: '✓', error: '✗' };
  el.querySelector('.step-icon').textContent =
    state === 'active' ? '…' :
    state === 'done'   ? '✓' :
    state === 'error'  ? '✗' :
    el.querySelector('.step-icon').textContent;
}

function setProgress(pct) {
  document.getElementById('progress-bar').style.width = pct + '%';
}

async function startProduction() {
  const topic = document.getElementById('topic').value.trim();
  if (!topic) { alert('Please enter a topic'); return; }

  const payload = {
    topic,
    format:   getSelected('format-chips')[0] || 'course',
    level:    document.getElementById('level').value,
    length:   document.getElementById('length').value,
    tools:    getSelected('tools-chips'),
    audience: document.getElementById('audience').value.trim(),
    handson:  getSelected('handson-chips')[0] || 'moderate',
    notes:    document.getElementById('notes').value.trim(),
  };

  document.getElementById('produce-btn').disabled = true;
  document.getElementById('form-card').style.opacity = '.5';
  document.getElementById('progress-card').classList.add('visible');

  try {
    const res = await fetch('/api/produce', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    jobId = data.job_id;
    pollStatus();
  } catch (e) {
    log('Failed to start: ' + e, 'err');
  }
}

function pollStatus() {
  pollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/status/${jobId}`);
      const data = await res.json();

      setProgress(data.progress || 0);

      // Update steps
      const stepMap = {
        research: 'step-research',
        draft:    'step-draft',
        record:   'step-record',
        narrate:  'step-narrate',
        qa:       'step-qa',
      };
      Object.entries(data.steps || {}).forEach(([k, v]) => {
        if (stepMap[k]) setStep(stepMap[k], v);
      });

      // Log new messages
      (data.new_logs || []).forEach(l => log(l));

      if (data.status === 'done') {
        clearInterval(pollInterval);
        showResults(data.outputs);
      } else if (data.status === 'error') {
        clearInterval(pollInterval);
        log('Production failed: ' + data.error, 'err');
        setProgress(100);
      }
    } catch (e) {
      log('Poll error: ' + e, 'warn');
    }
  }, 2000);
}

function showResults(outputs) {
  const card = document.getElementById('result-card');
  const files = document.getElementById('result-files');
  card.classList.add('visible');
  files.innerHTML = '';
  (outputs || []).forEach(f => {
    files.innerHTML += `
      <div class="result-file">
        <div>
          <div class="result-name">${f.name}</div>
          <div class="result-meta">${f.meta}</div>
        </div>
        <button class="result-btn" onclick="window.open('${f.path}')">Open</button>
      </div>`;
  });
}
</script>
</body>
</html>'''


# ── Job state ──────────────────────────────────────────────────────────────
jobs: dict = {}


def run_production(job_id: str, payload: dict):
    """Run the full production pipeline in a background thread."""
    job = jobs[job_id]

    def update(step: str, state: str, log: str = None, progress: int = None):
        job['steps'][step] = state
        if log:
            job['logs'].append(log)
            job['new_logs'].append(log)
        if progress is not None:
            job['progress'] = progress

    def run_cmd(cmd: list, cwd: str = None) -> tuple[int, str]:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=cwd or str(ROOT)
        )
        output = result.stdout + result.stderr
        for line in output.splitlines():
            if line.strip():
                job['logs'].append(line)
                job['new_logs'].append(line)
        return result.returncode, output

    try:
        topic   = payload['topic']
        fmt     = payload.get('format', 'course')
        level   = payload.get('level', 'beginner')
        length  = payload.get('length', 'medium')
        tools   = payload.get('tools', [])
        audience= payload.get('audience', '')
        notes   = payload.get('notes', '')
        handson = payload.get('handson', 'moderate')

        # Build enriched topic string for research
        enriched = topic
        if audience:
            enriched += f" for {audience}"
        if tools and 'none' not in tools:
            enriched += f" using {', '.join(tools)}"

        length_labels = {
            "short": "keep it on the shorter end of the format's typical range",
            "medium": "a moderate, typical-length treatment for this format",
            "long": "a longer, more thorough treatment on the deeper end of the format's range",
        }
        level_labels = {
            "beginner": "written for a complete beginner with no prior knowledge",
            "intermediate": "written for someone with some hands-on experience already",
            "advanced": "written for an advanced, professional-level audience",
        }
        handson_labels = {
            "heavy": "hands-on exercises woven throughout, not just at the end",
            "moderate": "a hands-on exercise at the end",
            "light": "mostly watching, minimal hands-on requirement",
        }

        guidance_parts = []
        if level in level_labels:
            guidance_parts.append(level_labels[level])
        if fmt != "micro" and length in length_labels:
            # Length guidance doesn't apply to micro - that format has its
            # own hard 1-3 minute cap regardless of this dropdown.
            guidance_parts.append(length_labels[length])
        if handson in handson_labels:
            guidance_parts.append(handson_labels[handson])
        if guidance_parts:
            enriched += f" ({'; '.join(guidance_parts)})"
        if notes:
            enriched += f". Additional guidance: {notes}"

        # ── Step 1: Research ────────────────────────────────────────
        update('research', 'active', f'Researching: {topic}', 5)

        code, out = run_cmd([
            sys.executable, 'research.py', enriched,
            '--format', fmt,
        ])
        if code != 0:
            update('research', 'error', 'Research failed')
            job['status'] = 'error'
            job['error'] = 'Research step failed'
            return

        # Find brief
        import re as _re
        slug = _re.sub(r'[^a-z0-9]+', '_', enriched.lower()).strip('_')[:40]
        brief_path = ROOT / 'research' / slug / 'brief.json'
        if not brief_path.exists():
            # Try original topic slug
            slug = _re.sub(r'[^a-z0-9]+', '_', topic.lower()).strip('_')[:40]
            brief_path = ROOT / 'research' / slug / 'brief.json'

        if not brief_path.exists():
            update('research', 'error', 'Could not find brief file')
            job['status'] = 'error'
            job['error'] = 'Brief not found after research'
            return

        update('research', 'done', f'Brief ready: {brief_path.name}', 20)

        # ── Step 2+: Draft + Produce, once per lesson ────────────────
        with open(brief_path) as f:
            import json as _json
            brief = _json.load(f)

        lessons = brief.get('content_structure', {}).get('lessons', [])
        if not lessons:
            update('draft', 'error', 'No lessons in brief')
            job['status'] = 'error'
            return

        course_slug = _re.sub(r'[^a-z0-9]+', '_', brief['topic'].lower()).strip('_')[:40]
        total = len(lessons)
        succeeded, failed = [], []

        for idx, lesson in enumerate(lessons):
            lesson_num = lesson['lesson_number']
            label = f"Lesson {idx + 1}/{total}"
            # Progress: research already took 0-20%. Remaining 80% split
            # evenly across lessons, each split roughly 1/3 draft, 2/3 produce.
            base = 20 + int(80 * idx / total)
            draft_pct = 20 + int(80 * (idx + 0.3) / total)
            done_pct = 20 + int(80 * (idx + 1) / total)

            for step in ('draft', 'record', 'narrate', 'qa'):
                job['steps'][step] = 'pending'

            update('draft', 'active', f'{label}: drafting production card...', base)

            code, out = run_cmd([
                sys.executable, 'draft.py', str(brief_path),
                '--lesson', str(lesson_num),
            ])
            if code != 0:
                update('draft', 'error', f'{label}: draft failed — skipping', draft_pct)
                failed.append(lesson_num)
                continue

            update('draft', 'done', f'{label}: production card ready', draft_pct)

            card_path = ROOT / 'courses' / course_slug / f'video_1_{lesson_num}' / 'production_card.yml'
            if not card_path.exists():
                update('draft', 'error', f'{label}: card not found at {card_path}', draft_pct)
                failed.append(lesson_num)
                continue

            update('record', 'active', f'{label}: recording + narrating...', draft_pct)

            el_key = os.environ.get("ELEVENLABS_API_KEY")
            el_voice = os.environ.get("ELEVENLABS_VOICE_ID", "E5wNdHqDxPAZRB8qRbQh")
            produce_cmd = [
                sys.executable, 'produce.py', str(card_path),
                '--format', fmt,
            ]
            if el_key:
                produce_cmd += ['--el-key', el_key, '--el-voice', el_voice]
            else:
                job['logs'].append(
                    f'{label}: WARNING - ELEVENLABS_API_KEY not set in this '
                    f'environment, falling back to a different (non-cloned) '
                    f'voice for narration.'
                )
                job['new_logs'].append(job['logs'][-1])

            code, out = run_cmd(produce_cmd)

            if 'Production complete' in out or 'final.mp4' in out:
                update('record',  'done', None, done_pct)
                update('narrate', 'done', None, done_pct)
                update('qa',      'done', f'{label}: QA passed', done_pct)
                succeeded.append(lesson_num)

                # Grab the most recently created final video — this specific
                # lesson's produce.py run just wrote it, so it's the newest
                # match at this point in time.
                final_mp4s = sorted(
                    (ROOT / 'output').glob('*_final.mp4'),
                    key=lambda p: p.stat().st_mtime,
                )
                if final_mp4s:
                    mp4 = final_mp4s[-1]
                    job['outputs'].append({
                        'name': mp4.name,
                        'path': f'/output/{mp4.name}',
                        'meta': f'{label} — {mp4.stat().st_size // 1024} KB — ready for Final Cut Pro',
                    })
            else:
                update('record', 'error', f'{label}: production failed', done_pct)
                failed.append(lesson_num)

        if succeeded and not failed:
            job['status'] = 'done'
        elif succeeded and failed:
            job['status'] = 'done'
            job['error'] = f'Lessons {failed} failed — see logs. Lessons {succeeded} completed.'
        else:
            job['status'] = 'error'
            job['error'] = f'All lessons failed: {failed}'

    except Exception as e:
        job['status'] = 'error'
        job['error'] = str(e)
        job['logs'].append(f'ERROR: {e}')


@app.route('/')
def index():
    return render_template_string(STUDIO_HTML)


@app.route('/api/scout', methods=['POST'])
def scout():
    payload = request.json or {}
    category_key = payload.get('category')
    if not category_key:
        return jsonify({'error': 'No category specified'}), 400

    result = subprocess.run(
        [sys.executable, 'topic_scout.py', '--category', category_key],
        capture_output=True, text=True, cwd=str(ROOT), timeout=120,
    )

    if result.returncode != 0:
        return jsonify({
            'error': 'Topic scout failed',
            'detail': (result.stdout + result.stderr)[-2000:],
        }), 500

    out_path = ROOT / 'research' / f'_scout_{category_key}.json'
    if not out_path.exists():
        return jsonify({'error': 'No suggestions produced', 'suggestions': []})

    try:
        data = json.loads(out_path.read_text())
    except Exception:
        return jsonify({'error': 'Could not parse scout output', 'suggestions': []})

    return jsonify(data)


@app.route('/api/produce', methods=['POST'])
def produce():
    import uuid
    job_id = str(uuid.uuid4())[:8]
    payload = request.json

    jobs[job_id] = {
        'status':   'running',
        'progress': 0,
        'steps':    {k: 'pending' for k in ['research', 'draft', 'record', 'narrate', 'qa']},
        'logs':     [],
        'new_logs': [],
        'outputs':  [],
        'error':    None,
    }

    thread = threading.Thread(target=run_production, args=(job_id, payload), daemon=True)
    thread.start()

    return jsonify({'job_id': job_id})


@app.route('/api/status/<job_id>')
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    new_logs = job['new_logs'].copy()
    job['new_logs'] = []

    return jsonify({
        'status':   job['status'],
        'progress': job['progress'],
        'steps':    job['steps'],
        'new_logs': new_logs,
        'outputs':  job['outputs'],
        'error':    job['error'],
    })


if __name__ == '__main__':
    print('\nWSDA Studio')
    print('Open: http://localhost:7010\n')
    app.run(host='127.0.0.1', port=7010, debug=False)
