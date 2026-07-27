#!/usr/bin/env python3
"""
WSDA Topic Scout — on-demand, web-grounded topic suggestion tool.

No sales/analytics data is available to this system, so this does NOT
pretend to know what "sells." Instead it grounds suggestions in live,
citable web search results (current job postings, forum questions, trending
discussion) within a fixed category taxonomy that keeps results on-brand,
then cross-references against courses already built in this repo so
suggestions surface genuine gaps rather than duplicates. Every suggestion
must come with a real source URL — if the model can't back a topic with an
actual search result, it shouldn't suggest it.

Usage:
  python3 topic_scout.py --list-categories
  python3 topic_scout.py --category sql-fundamentals
"""
import json
import re
from pathlib import Path

import click
from anthropic import Anthropic
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
client = Anthropic()
ROOT = Path(__file__).parent

CATEGORIES = {
    "sql-fundamentals": {
        "label": "SQL fundamentals & debugging",
        "description": "Core SQL mistakes, debugging techniques, query correctness - "
                        "GROUP BY, JOINs, NULLs, duplicate keys, filters, aggregation traps",
    },
    "sql-ai-hybrid": {
        "label": "SQL + AI hybrid workflows",
        "description": "Using AI tools to write/verify SQL, prompting techniques for data "
                        "work, spot-checking AI-generated queries, the PVC "
                        "(Prompt-Validate-Communicate) methodology",
    },
    "data-quality": {
        "label": "Data quality & trust",
        "description": "Why two reports disagree, metric definition drift, data "
                        "validation, reconciling dashboards vs raw queries, trust in "
                        "data pipelines",
    },
    "career-interview": {
        "label": "Career & interview prep",
        "description": "SQL interview questions, portfolio-building, real on-the-job "
                        "scenarios, what hiring managers actually test for",
    },
}


def load_existing_catalog() -> list:
    """Scan local repo history (research briefs + drafted course lessons)
    for topics/titles already covered, so new suggestions don't duplicate
    what's already been built."""
    covered = []

    research_dir = ROOT / "research"
    if research_dir.exists():
        for brief_path in research_dir.glob("*/brief.json"):
            try:
                brief = json.loads(brief_path.read_text())
                if brief.get("topic"):
                    covered.append(brief["topic"])
            except Exception:
                continue

    courses_dir = ROOT / "courses"
    if courses_dir.exists():
        for manifest_path in courses_dir.glob("*/course_manifest.json"):
            try:
                manifest = json.loads(manifest_path.read_text())
                if manifest.get("course"):
                    covered.append(manifest["course"])
                for lesson_path in manifest.get("lessons", []):
                    p = Path(lesson_path)
                    if p.exists():
                        import yaml
                        card = yaml.safe_load(p.read_text())
                        if card and card.get("title"):
                            covered.append(card["title"])
            except Exception:
                continue

    seen, deduped = set(), []
    for c in covered:
        if c and c not in seen:
            seen.add(c)
            deduped.append(c)
    return deduped


SCOUT_SYSTEM = """You are a content strategist for WSDA (Walter Shields Data \
Academy), a data-skills education brand. Your job is to find CURRENT, REAL demand \
signals for new lesson topics using live web search — not guesses, actual \
researched findings.

For the given category, search the web for:
- Questions people are actually asking right now (Stack Overflow, Reddit, forums)
- Skills or keywords that show up repeatedly in current job postings
- Common pain points or confusions discussed in recent articles or discussions

Then propose 5 specific, NARROW lesson topics — not broad "learn SQL" topics, but
narrow angles like "why your GROUP BY total doesn't match the dashboard" — that
your research actually supports as genuinely in-demand right now.

For EVERY suggestion you MUST cite the specific source(s) that support it — a real
URL you found via search. Do not propose a topic you can't back with an actual
source. If you can't find real support for 5 topics in this category, return fewer
rather than padding with unsupported ones.

Do not suggest anything overlapping with the "already covered" list you're given.

Respond with ONLY valid JSON, no markdown fences, no preamble, in this exact
structure:
{
  "suggestions": [
    {
      "topic": "specific, narrow topic phrased as a title",
      "rationale": "one sentence on why this is in demand right now",
      "sources": ["https://...", "https://..."]
    }
  ]
}"""


def scout_category(category_key: str, existing_catalog: list) -> dict:
    cat = CATEGORIES[category_key]
    existing_text = "\n".join(f"- {c}" for c in existing_catalog) or "(none yet)"

    prompt = f"""Category: {cat['label']}
Category scope: {cat['description']}

Topics ALREADY COVERED in this catalog (do not suggest anything overlapping):
{existing_text}

Search the web now for current demand signals in this category, then propose up
to 5 specific, narrow, genuinely in-demand lesson topics not already covered above."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4000,
        system=SCOUT_SYSTEM,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    # When web search actually runs, response.content contains multiple
    # text blocks interleaved with server_tool_use/web_search_tool_result
    # blocks - Claude's "I'll search for..." commentary comes as its own
    # text block(s) BEFORE the final answer. Joining all text blocks
    # together prepends that commentary in front of the JSON and breaks
    # the parse. Only the LAST text block is the actual final answer.
    text_blocks = [b.text for b in response.content if getattr(b, "type", None) == "text"]
    full_text = text_blocks[-1].strip() if text_blocks else ""
    full_text = re.sub(r'^```json\s*', '', full_text, flags=re.MULTILINE)
    full_text = re.sub(r'```\s*$', '', full_text.strip())

    try:
        return json.loads(full_text)
    except json.JSONDecodeError:
        # Fallback: the model may have left stray commentary around the
        # JSON despite instructions - try to isolate just the {...} object.
        match = re.search(r'\{.*\}', full_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        console.print("[red]Could not parse scout response as JSON[/red]")
        console.print(full_text[:800])
        return {"suggestions": []}


@click.command()
@click.option("--category", "category_key",
              type=click.Choice(list(CATEGORIES.keys())), default=None)
@click.option("--list-categories", is_flag=True)
def scout(category_key, list_categories):
    if list_categories or not category_key:
        console.print(Panel("WSDA Topic Scout — Categories", border_style="cyan"))
        for key, cat in CATEGORIES.items():
            console.print(f"  [cyan]{key}[/cyan]  {cat['label']}")
            console.print(f"    [dim]{cat['description']}[/dim]\n")
        if not category_key:
            return

    console.print(Panel(f"Scouting: {CATEGORIES[category_key]['label']}", border_style="cyan"))

    existing = load_existing_catalog()
    console.print(f"[dim]Checked against {len(existing)} existing topics in catalog[/dim]\n")

    console.print("[bold]Searching the web for current demand signals...[/bold]")
    result = scout_category(category_key, existing)

    suggestions = result.get("suggestions", [])
    if not suggestions:
        console.print("[yellow]No suggestions returned — try again, or the "
                       "category may be fully covered already[/yellow]")
        return

    table = Table(title=f"Suggested Topics — {CATEGORIES[category_key]['label']}")
    table.add_column("#", width=3)
    table.add_column("Topic", style="cyan")
    table.add_column("Why", style="dim")
    table.add_column("Sources", style="blue")

    for i, s in enumerate(suggestions, 1):
        sources = "\n".join(s.get("sources", []))
        table.add_row(str(i), s.get("topic", ""), s.get("rationale", ""), sources)

    console.print(table)

    out_path = ROOT / "research" / f"_scout_{category_key}.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2))
    console.print(f"\n[green]Saved to {out_path}[/green]")


if __name__ == "__main__":
    scout()
